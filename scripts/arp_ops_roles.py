"""
arp_convert_addon에서 분리한 Role editing 오퍼레이터.

Step 3 Role Editing 단계에서 사용. Source Hierarchy 트리에서 본을
선택, 부모 변경, 역할 변경을 담당한다.
"""

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy.types import Operator

from arp_foot_guides import (
    FOOT_ROLES,
    _create_foot_guides_for_role,
    _set_preview_pose_bone_role,
)
from arp_ops_preview import _populate_hierarchy_collection

# ───────────────────────────────────────────────────────────────
# 역할 드롭다운 (arp_convert_addon에서 이동 + re-export)
# ───────────────────────────────────────────────────────────────

ROLE_ITEMS = [
    ("root", "Root", "루트 본"),
    ("spine", "Spine", "스파인 체인"),
    ("neck", "Neck", "목"),
    ("head", "Head", "머리"),
    ("back_leg_l", "Back Leg L", "뒷다리 좌"),
    ("back_leg_r", "Back Leg R", "뒷다리 우"),
    ("back_foot_l", "Back Foot L", "뒷발 좌"),
    ("back_foot_r", "Back Foot R", "뒷발 우"),
    ("front_leg_l", "Front Leg L", "앞다리 좌"),
    ("front_leg_r", "Front Leg R", "앞다리 우"),
    ("front_foot_l", "Front Foot L", "앞발 좌"),
    ("front_foot_r", "Front Foot R", "앞발 우"),
    ("ear_l", "Ear L", "귀 좌"),
    ("ear_r", "Ear R", "귀 우"),
    ("tail", "Tail", "꼬리"),
    ("unmapped", "Unmapped", "미매핑 (cc_ 커스텀 본)"),
]
ROLE_IDS = {item[0] for item in ROLE_ITEMS}


class ARPCONV_OT_SelectBone(Operator):
    """하이어라키 트리에서 본 클릭 시 Preview armature에서 선택"""

    bl_idname = "arp_convert.select_bone"
    bl_label = "본 선택"
    bl_options = {"REGISTER", "UNDO"}

    bone_name: StringProperty()

    def execute(self, context):
        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)
        if not preview_obj:
            self.report({"WARNING"}, "Preview armature 없음")
            return {"CANCELLED"}

        # Preview 활성화 + Pose 모드에서 본 선택
        context.view_layer.objects.active = preview_obj
        preview_obj.select_set(True)
        if context.mode != "POSE":
            bpy.ops.object.mode_set(mode="POSE")
        bpy.ops.pose.select_all(action="DESELECT")
        bone = preview_obj.data.bones.get(self.bone_name)
        if bone:
            bone.select = True
            preview_obj.data.bones.active = bone
        else:
            self.report({"INFO"}, f"{self.bone_name}: 제외된 본 (Preview에 없음)")
        return {"FINISHED"}


class ARPCONV_OT_SetParent(Operator):
    """선택된 본의 부모를 변경"""

    bl_idname = "arp_convert.set_parent"
    bl_label = "부모 변경"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)
        if not preview_obj:
            self.report({"ERROR"}, "Preview armature 없음")
            return {"CANCELLED"}

        # 활성 본 확인
        active_bone = preview_obj.data.bones.active
        if not active_bone:
            self.report({"WARNING"}, "본을 먼저 선택하세요")
            return {"CANCELLED"}

        bone_name = active_bone.name
        new_parent_name = props.pending_parent.strip()

        # 자기 자신을 부모로 설정 방지
        if new_parent_name == bone_name:
            self.report({"WARNING"}, "자기 자신을 부모로 설정할 수 없습니다")
            return {"CANCELLED"}

        # Edit Mode 진입
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        context.view_layer.objects.active = preview_obj
        preview_obj.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")

        edit_bones = preview_obj.data.edit_bones
        eb = edit_bones.get(bone_name)
        if not eb:
            bpy.ops.object.mode_set(mode="OBJECT")
            self.report({"ERROR"}, f"'{bone_name}' edit bone을 찾을 수 없습니다")
            return {"CANCELLED"}

        # 부모 변경
        if new_parent_name:
            new_parent_eb = edit_bones.get(new_parent_name)
            if not new_parent_eb:
                bpy.ops.object.mode_set(mode="OBJECT")
                self.report({"ERROR"}, f"부모 '{new_parent_name}'를 찾을 수 없습니다")
                return {"CANCELLED"}
            eb.parent = new_parent_eb
        else:
            eb.parent = None
        eb.use_connect = False

        old_parent = active_bone.parent.name if active_bone.parent else "(없음)"
        new_parent_display = new_parent_name if new_parent_name else "(없음)"

        # Pose Mode 복귀
        bpy.ops.object.mode_set(mode="POSE")

        # 하이어라키 트리 갱신
        from arp_convert_addon import _ensure_scripts_path

        _ensure_scripts_path()
        from skeleton_analyzer import extract_bone_data

        bone_data = extract_bone_data(preview_obj)
        deform_bones = {name: bone_data[name] for name in bone_data if bone_data[name]["is_deform"]}
        analysis_for_tree = {
            "bone_data": deform_bones,
            "excluded_zero_weight": [],
        }
        _populate_hierarchy_collection(context, analysis_for_tree)

        # pending_parent 초기화
        props.pending_parent = ""

        self.report(
            {"INFO"},
            f"{bone_name}: 부모 {old_parent} → {new_parent_display}",
        )
        return {"FINISHED"}


class ARPCONV_OT_SetRole(Operator):
    """선택된 본의 역할을 변경"""

    bl_idname = "arp_convert.set_role"
    bl_label = "역할 설정"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(name="역할", items=ROLE_ITEMS)

    def execute(self, context):
        from arp_convert_addon import _ensure_scripts_path

        _ensure_scripts_path()
        from skeleton_analyzer import ROLE_COLORS, ROLE_PROP_KEY

        preview_obj = context.active_object
        if not preview_obj or preview_obj.type != "ARMATURE":
            self.report({"ERROR"}, "Preview Armature를 선택하세요.")
            return {"CANCELLED"}

        # 선택된 본에 역할 적용
        changed = 0
        foot_bones = []  # foot 역할로 변경된 본 이름 수집

        if context.mode == "POSE":
            selected = context.selected_pose_bones
        else:
            selected = []
            for bone in preview_obj.data.bones:
                if bone.select:
                    pbone = preview_obj.pose.bones.get(bone.name)
                    if pbone:
                        selected.append(pbone)

        for pbone in selected:
            _set_preview_pose_bone_role(pbone, self.role, ROLE_COLORS, ROLE_PROP_KEY)
            changed += 1

            if self.role in FOOT_ROLES:
                foot_bones.append(pbone.name)

        if changed == 0:
            self.report({"WARNING"}, "본이 선택되지 않았습니다.")
            return {"FINISHED"}

        # foot 역할이면 bank/heel 가이드 본 자동 생성
        if foot_bones:
            guide_count = _create_foot_guides_for_role(
                context, preview_obj, foot_bones, self.role, ROLE_PROP_KEY
            )
            self.report({"INFO"}, f"{changed}개 본 → {self.role} + 가이드 {guide_count}개 생성")
        else:
            self.report({"INFO"}, f"{changed}개 본 → {self.role}")

        return {"FINISHED"}

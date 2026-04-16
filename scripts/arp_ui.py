"""
ARP Convert N-panel UI.

메인 패널 + 5개 서브패널 + 도구 패널로 구성.
"""

import os
import sys

import bpy
from bpy.types import Panel


def _ensure_scripts_path():
    """scripts/ 폴더를 sys.path에 추가"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "skeleton_analyzer.py")):
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        return script_dir
    try:
        blend_filepath = bpy.data.filepath
    except AttributeError:
        blend_filepath = ""
    if blend_filepath:
        d = os.path.dirname(blend_filepath)
        for _ in range(10):
            candidate = os.path.join(d, "scripts")
            if os.path.exists(os.path.join(candidate, "skeleton_analyzer.py")):
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                return candidate
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return ""


def _get_step_status(props):
    """현재 워크플로 진행 상태 반환.

    Returns dict: step_number → "done" | "current" | "pending"
    """
    status = {1: "pending", 2: "pending", 3: "pending", 4: "pending", 5: "pending"}
    if props.is_analyzed:
        status[1] = "done"
        status[2] = "current"
    if props.build_completed:
        status[2] = "done"
        status[3] = "done"
        status[4] = "current"
    if props.retarget_setup_done:
        status[4] = "done"
        status[5] = "current"
    return status


_STATUS_ICONS = {"done": "CHECKMARK", "current": "PLAY", "pending": "RADIOBUT_OFF"}


class ARPCONV_PT_MainPanel(Panel):
    """ARP 리그 변환 메인 패널"""

    bl_label = "ARP 리그 변환"
    bl_idname = "ARPCONV_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"

    def draw(self, context):
        layout = self.layout
        from arp_convert_addon import bl_info

        layout.label(text=f"v{'.'.join(str(v) for v in bl_info['version'])}")


class ARPCONV_PT_Step1_Analysis(Panel):
    """1. 분석"""

    bl_label = "1. 분석"
    bl_idname = "ARPCONV_PT_step1"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[1]])
        if props.is_analyzed:
            self.layout.label(text=f"신뢰도 {props.confidence:.0%}")

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props
        if props.source_armature:
            layout.label(text=f"소스: {props.source_armature}")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("arp_convert.create_preview", icon="ARMATURE_DATA")
        if not props.is_analyzed:
            layout.label(text="소스 아마추어를 선택하고 분석을 실행하세요.", icon="INFO")
        elif props.preview_armature:
            layout.label(text=f"프리뷰: {props.preview_armature}")


class ARPCONV_PT_Step2_Roles(Panel):
    """2. 역할 수정"""

    bl_label = "2. 역할 수정"
    bl_idname = "ARPCONV_PT_step2"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[2]])
        if props.total_bone_count > 0:
            self.layout.label(text=f"{props.mapped_bone_count}/{props.total_bone_count} 매핑됨")

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props

        _ensure_scripts_path()
        from arp_role_icons import get_icon_id
        from skeleton_analyzer import ROLE_PROP_KEY
        from skeleton_detection import ROLE_LABELS

        # Source Hierarchy (접이식)
        hier_coll = getattr(context.scene, "arp_source_hierarchy", None)
        if hier_coll and len(hier_coll) > 0:
            row = layout.row()
            row.prop(
                props,
                "show_source_hierarchy",
                icon="TRIA_DOWN" if props.show_source_hierarchy else "TRIA_RIGHT",
                text=f"소스 계층 트리 ({len(hier_coll)})",
                emboss=False,
            )
            if props.show_source_hierarchy:
                preview_obj = bpy.data.objects.get(props.preview_armature)
                hier_box = layout.box()
                col = hier_box.column(align=True)
                for item in hier_coll:
                    row = col.row(align=True)
                    pbone = preview_obj.pose.bones.get(item.name) if preview_obj else None
                    if pbone is None:
                        icon_val = 0
                        blender_icon = "RADIOBUT_OFF"
                        role = "unmapped"
                        label = f"{item.tree_prefix}{item.name} (w=0)"
                    else:
                        role = pbone.get(ROLE_PROP_KEY, "unmapped")
                        icon_val = get_icon_id(role)
                        blender_icon = ""
                        role_label = ROLE_LABELS.get(role, "")
                        label = f"{item.tree_prefix}{item.name}"
                        if role_label and role != "unmapped":
                            label += f"  {role_label}"

                    if icon_val:
                        op = row.operator(
                            "arp_convert.select_bone",
                            text=label,
                            icon_value=icon_val,
                            emboss=False,
                        )
                    else:
                        op = row.operator(
                            "arp_convert.select_bone",
                            text=label,
                            icon=blender_icon or "DOT",
                            emboss=False,
                        )
                    op.bone_name = item.name

        layout.label(text="본 선택 후 역할을 변경하세요:")

        # 역할 버튼 — 카테고리별
        # 몸통
        sub = layout.column(align=True)
        sub.label(text="몸통:")
        grid = sub.grid_flow(columns=3, align=True)
        for role_id in ["root", "spine", "neck", "head", "tail"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator("arp_convert.set_role", text=label, icon_value=icon_val)
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 다리
        sub = layout.column(align=True)
        sub.label(text="다리:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator("arp_convert.set_role", text=label, icon_value=icon_val)
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 발
        sub = layout.column(align=True)
        sub.label(text="발:")
        sub.label(text="(bank/heel 가이드 자동 생성)", icon="INFO")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in [
            "back_foot_l",
            "back_foot_r",
            "front_foot_l",
            "front_foot_r",
        ]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator("arp_convert.set_role", text=label, icon_value=icon_val)
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 머리 부속
        sub = layout.column(align=True)
        sub.label(text="머리 부속:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["ear_l", "ear_r"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator("arp_convert.set_role", text=label, icon_value=icon_val)
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 기타
        sub = layout.column(align=True)
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["trajectory", "unmapped"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator("arp_convert.set_role", text=label, icon_value=icon_val)
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 선택 본 정보
        if context.active_object and context.active_object.type == "ARMATURE":
            arm_obj = context.active_object
            selected_bones = [b for b in arm_obj.data.bones if b.select]

            if selected_bones:
                layout.separator()
                if len(selected_bones) == 1:
                    bone = selected_bones[0]
                    pbone = arm_obj.pose.bones.get(bone.name)
                    current_role = pbone.get(ROLE_PROP_KEY, "unmapped") if pbone else "?"
                    role_label = ROLE_LABELS.get(current_role, current_role)
                    layout.label(text=f"선택: {bone.name}", icon="BONE_DATA")
                    layout.label(text=f"현재 역할: {role_label}")
                    parent_name = bone.parent.name if bone.parent else "(없음)"
                    layout.label(text=f"부모: {parent_name}", icon="LINKED")
                else:
                    layout.label(
                        text=f"선택: {len(selected_bones)}개 본",
                        icon="BONE_DATA",
                    )
                    names = ", ".join(b.name for b in selected_bones[:4])
                    if len(selected_bones) > 4:
                        names += f" 외 {len(selected_bones) - 4}개"
                    layout.label(text=names)

                preview_obj = bpy.data.objects.get(props.preview_armature)
                if preview_obj:
                    row2 = layout.row(align=True)
                    row2.prop_search(
                        props,
                        "pending_parent",
                        preview_obj.data,
                        "bones",
                        text="새 부모",
                    )

            if not selected_bones:
                layout.separator()
                layout.label(text="Shift+클릭으로 복수 선택 가능", icon="INFO")


class ARPCONV_PT_Step3_Build(Panel):
    """3. 리그 생성"""

    bl_label = "3. 리그 생성"
    bl_idname = "ARPCONV_PT_step3"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[3]])

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props
        layout.prop(props, "front_3bones_ik", slider=True)
        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.build_rig", icon="MOD_ARMATURE")


class ARPCONV_PT_Step4_Retarget(Panel):
    """4. 리타겟"""

    bl_label = "4. 리타겟"
    bl_idname = "ARPCONV_PT_step4"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[4]])

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.setup_retarget", icon="LINKED")

        has_bones_map = hasattr(scn, "bones_map_v2") and len(scn.bones_map_v2) > 0

        if has_bones_map:
            target_rig = bpy.data.objects.get(getattr(scn, "target_rig", ""))

            layout.separator()
            row = layout.row(align=True)
            split = row.split(factor=0.5)
            split.label(text="소스 본:")
            split.label(text="타겟 본:")

            row = layout.row(align=True)
            try:
                row.template_list(
                    "ARP_UL_items",
                    "",
                    scn,
                    "bones_map_v2",
                    scn,
                    "bones_map_index",
                    rows=4,
                )
            except Exception:
                row.label(text="ARP Remap UIList를 불러올 수 없습니다.", icon="ERROR")

            idx = getattr(scn, "bones_map_index", -1)
            if 0 <= idx < len(scn.bones_map_v2):
                item = scn.bones_map_v2[idx]
                prop_box = layout.box()

                row = prop_box.row(align=True)
                row.label(text=item.source_bone + ":")
                if target_rig and target_rig.type == "ARMATURE":
                    row.prop_search(item, "name", target_rig.data, "bones", text="")
                else:
                    row.prop(item, "name", text="")

                row = prop_box.row(align=True)
                row.prop(item, "set_as_root", text="루트 지정")
                sub = row.row()
                sub.enabled = not item.ik and not item.set_as_root
                sub.prop(item, "location", text="위치")

                row = prop_box.row(align=True)
                split = row.split(factor=0.2)
                split.enabled = not item.set_as_root
                split.prop(item, "ik", text="IK")
                if item.ik and target_rig and target_rig.type == "ARMATURE":
                    sub = split.split(factor=0.9, align=True)
                    sub.prop_search(item, "ik_pole", target_rig.data, "bones", text="폴 벡터")

        layout.separator()

        if hasattr(scn, "batch_retarget"):
            row = layout.row(align=True)
            row.prop(scn, "batch_retarget", text="다중 소스 애니메이션")
            if getattr(scn, "batch_retarget", False):
                marked = sum(1 for act in bpy.data.actions if act.get("arp_remap", False))
                row.label(text=f"({marked}개 액션)")

        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.execute_retarget", icon="PLAY")

        row = layout.row()
        row.operator("arp_convert.copy_custom_scale", icon="CON_SIZELIKE")


class ARPCONV_PT_Step5_Cleanup(Panel):
    """5. 정리"""

    bl_label = "5. 정리"
    bl_idname = "ARPCONV_PT_step5"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[5]])

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.cleanup", icon="TRASH")


class ARPCONV_PT_Tools(Panel):
    """도구"""

    bl_label = "도구"
    bl_idname = "ARPCONV_PT_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props
        layout.prop(props, "regression_fixture", text="Fixture")
        layout.prop(props, "regression_report_dir", text="리포트 폴더")
        row = layout.row()
        row.scale_y = 1.2
        row.operator("arp_convert.run_regression", icon="CHECKMARK")

"""
arp_convert_addon에서 분리한 N-panel UI.

ARPCONV_PT_MainPanel만 담는다. 3D Viewport N-panel의 "ARP Convert"
탭에 Step 1~4 버튼과 Source Hierarchy 트리를 표시한다.
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

    # bpy.data가 restricted context (애드온 등록 중)면 filepath 접근 불가 → 조용히 skip
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


class ARPCONV_PT_MainPanel(Panel):
    """ARP 리그 변환 메인 패널"""

    bl_label = "ARP 리그 변환"
    bl_idname = "ARPCONV_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props

        # Step 1: 분석 + Preview
        box = layout.box()
        box.label(text="Step 1: 분석", icon="VIEWZOOM")
        if props.source_armature:
            box.label(text=f"소스: {props.source_armature}")
        row = box.row()
        row.scale_y = 1.5
        row.operator("arp_convert.create_preview", icon="ARMATURE_DATA")

        if not props.is_analyzed:
            layout.separator()
            layout.label(text="소스 아마추어를 선택하고 분석을 실행하세요.", icon="INFO")
            return

        # 신뢰도
        layout.label(text=f"신뢰도: {props.confidence:.0%}", icon="CHECKMARK")
        if props.preview_armature:
            layout.label(text=f"Preview: {props.preview_armature}")

        layout.separator()

        # Step 2: 역할 수정
        box = layout.box()
        box.label(text="Step 2: 역할 수정", icon="BONE_DATA")

        # Source Hierarchy (접이식)
        hier_coll = getattr(context.scene, "arp_source_hierarchy", None)
        if hier_coll and len(hier_coll) > 0:
            row = box.row()
            row.prop(
                props,
                "show_source_hierarchy",
                icon="TRIA_DOWN" if props.show_source_hierarchy else "TRIA_RIGHT",
                text=f"Source Hierarchy ({len(hier_coll)})",
                emboss=False,
            )
            if props.show_source_hierarchy:
                _ensure_scripts_path()
                from skeleton_analyzer import ROLE_PROP_KEY

                preview_obj = bpy.data.objects.get(props.preview_armature)
                hier_box = box.box()
                col = hier_box.column(align=True)
                for item in hier_coll:
                    row = col.row(align=True)
                    # 들여쓰기
                    if item.depth > 0:
                        indent = row.row()
                        indent.ui_units_x = item.depth * 0.8
                        indent.label(text="")
                    # 아이콘: Preview에 있으면 role 읽기, 없으면 제외 본
                    pbone = preview_obj.pose.bones.get(item.name) if preview_obj else None
                    if pbone is None:
                        icon = "RADIOBUT_OFF"
                        label = f"{item.name} (w=0)"
                    else:
                        role = pbone.get(ROLE_PROP_KEY, "unmapped")
                        icon = "CHECKMARK" if role != "unmapped" else "DOT"
                        label = f"{item.name} [{role}]" if role != "unmapped" else item.name
                    op = row.operator(
                        "arp_convert.select_bone",
                        text=label,
                        icon=icon,
                        emboss=False,
                    )
                    op.bone_name = item.name

        box.label(text="본 선택 후 역할을 변경하세요:")

        # 역할 버튼 — 카테고리별 정리
        # Body
        sub = box.column(align=True)
        sub.label(text="Body:")
        grid = sub.grid_flow(columns=3, align=True)
        for role_id in ["root", "spine", "neck", "head", "tail"]:
            op = grid.operator("arp_convert.set_role", text=role_id.capitalize())
            op.role = role_id

        # Legs
        sub = box.column(align=True)
        sub.label(text="Legs:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
            label = (
                role_id.replace("_", " ")
                .title()
                .replace("Back Leg", "BLeg")
                .replace("Front Leg", "FLeg")
            )
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Feet (★)
        sub = box.column(align=True)
        sub.label(text="Feet (★ bank/heel 자동 생성):")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["back_foot_l", "back_foot_r", "front_foot_l", "front_foot_r"]:
            label = (
                role_id.replace("_", " ")
                .title()
                .replace("Back Foot", "BFoot")
                .replace("Front Foot", "FFoot")
            )
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Head features
        sub = box.column(align=True)
        sub.label(text="Head:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["ear_l", "ear_r"]:
            label = {"ear_l": "Ear L", "ear_r": "Ear R"}[role_id]
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Unmapped (cc_ custom bones)
        row = box.row()
        op = row.operator("arp_convert.set_role", text="Unmapped (cc_)")
        op.role = "unmapped"

        # 현재 선택된 본의 역할 표시
        if context.active_object and context.active_object.type == "ARMATURE":
            arm_obj = context.active_object
            # 선택된 본 목록
            selected_bones = [b for b in arm_obj.data.bones if b.select]

            if selected_bones:
                _ensure_scripts_path()
                from skeleton_analyzer import ROLE_PROP_KEY

                box.separator()
                if len(selected_bones) == 1:
                    bone = selected_bones[0]
                    pbone = arm_obj.pose.bones.get(bone.name)
                    current_role = pbone.get(ROLE_PROP_KEY, "unmapped") if pbone else "?"
                    box.label(text=f"선택: {bone.name}", icon="BONE_DATA")
                    box.label(text=f"현재 역할: {current_role}")
                    parent_name = bone.parent.name if bone.parent else "(없음)"
                    box.label(text=f"부모: {parent_name}", icon="LINKED")
                else:
                    box.label(
                        text=f"선택: {len(selected_bones)}개 본",
                        icon="BONE_DATA",
                    )
                    names = ", ".join(b.name for b in selected_bones[:4])
                    if len(selected_bones) > 4:
                        names += f" 외 {len(selected_bones) - 4}개"
                    box.label(text=names)

                # 부모 변경 UI — 선택 시 자동 적용
                preview_obj = bpy.data.objects.get(props.preview_armature)
                if preview_obj:
                    row2 = box.row(align=True)
                    row2.prop_search(
                        props,
                        "pending_parent",
                        preview_obj.data,
                        "bones",
                        text="새 부모",
                    )

            if not selected_bones:
                box.separator()
                box.label(text="Shift+클릭으로 복수 선택 가능", icon="INFO")

        layout.separator()

        # Step 3: 리그 생성
        box = layout.box()
        box.label(text="Step 3: Build Rig", icon="MOD_ARMATURE")
        box.prop(props, "front_3bones_ik", slider=True)
        row = box.row()
        row.scale_y = 1.3
        row.operator("arp_convert.build_rig", icon="MOD_ARMATURE")

        layout.separator()

        # Step 4: 리타겟 설정
        box = layout.box()
        box.label(text="Step 4: Setup Retarget", icon="ACTION")
        row = box.row()
        row.scale_y = 1.3
        row.operator("arp_convert.setup_retarget", icon="LINKED")
        box.label(text="ARP Remap 패널에서 매핑 확인 후 Re-Retarget 실행", icon="INFO")
        row = box.row()
        row.operator("arp_convert.copy_custom_scale", icon="CON_SIZELIKE")

        layout.separator()

        # Step 5: Cleanup
        box = layout.box()
        box.label(text="Step 5: Cleanup", icon="TRASH")
        row = box.row()
        row.scale_y = 1.3
        row.operator("arp_convert.cleanup", icon="TRASH")

        layout.separator()

        box = layout.box()
        box.label(text="Regression", icon="FILE_TEXT")
        box.prop(props, "regression_fixture", text="Fixture")
        box.prop(props, "regression_report_dir", text="Report Dir")
        row = box.row()
        row.scale_y = 1.2
        row.operator("arp_convert.run_regression", icon="CHECKMARK")

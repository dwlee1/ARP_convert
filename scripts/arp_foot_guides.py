"""
arp_convert_addon에서 분리한 foot guide 헬퍼.

Preview Armature에서 foot 역할 본의 heel/bank 가이드 생성,
가이드 종류·사이드 검출, 기본/자동 위치 계산 함수들을 담는다.
"""

import bpy
from mathutils import Vector

# ── foot 가이드 관련 상수 ─────────────────────────────────────────
FOOT_ROLES = {"back_foot_l", "back_foot_r", "front_foot_l", "front_foot_r"}
GUIDE_SUFFIX_HEEL = "_heel"
GUIDE_SUFFIX_BANK = "_bank"

HEEL_OFFSET_Z = -0.02  # 바닥 방향
HEEL_OFFSET_Y = -0.01  # 뒤쪽
BANK_OFFSET_X = 0.015  # 좌우
GUIDE_DEFAULT_TOLERANCE = 0.002
AUTO_HEEL_BACK_RATIO = 0.18
AUTO_HEEL_DOWN_RATIO = 0.08
AUTO_BANK_SIDE_RATIO = 0.14
AUTO_BANK_DOWN_RATIO = 0.04
AUTO_GUIDE_MAX_OFFSET = 0.03


def _set_preview_pose_bone_role(pbone, role, role_colors, role_prop_key):
    color = role_colors.get(role, role_colors["unmapped"])
    pbone[role_prop_key] = role
    pbone.color.palette = "CUSTOM"
    pbone.color.custom.normal = color
    pbone.color.custom.select = tuple(min(c + 0.3, 1.0) for c in color)
    pbone.color.custom.active = tuple(min(c + 0.5, 1.0) for c in color)


def _create_foot_guides_for_role(context, preview_obj, foot_bone_names, role, role_prop_key):
    """
    foot 역할 본에 대해 heel/bank 가이드 본을 Preview에 자동 생성.
    SetRole 오퍼레이터와 회귀 테스트 러너에서 공통 사용한다.
    """
    prev_mode = context.mode
    if prev_mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    preview_obj.select_set(True)
    context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = preview_obj.data.edit_bones
    created = 0

    side = role.rsplit("_", 1)[-1]
    prefix = role.rsplit("_", 2)[0]
    prefix_short = prefix.replace("_foot", "")

    for foot_name in foot_bone_names:
        foot_eb = edit_bones.get(foot_name)
        if foot_eb is None:
            continue

        foot_head = foot_eb.head.copy()

        heel_name = f"{foot_name}{GUIDE_SUFFIX_HEEL}"
        old_heel = edit_bones.get(heel_name)
        if old_heel:
            edit_bones.remove(old_heel)

        heel_eb = edit_bones.new(heel_name)
        heel_eb.head = foot_head + Vector((0, HEEL_OFFSET_Y, HEEL_OFFSET_Z))
        heel_eb.tail = heel_eb.head + Vector((0, 0, 0.005))
        heel_eb.use_deform = False
        heel_eb.parent = foot_eb
        created += 1

        bank_name = f"{foot_name}{GUIDE_SUFFIX_BANK}"
        old_bank = edit_bones.get(bank_name)
        if old_bank:
            edit_bones.remove(old_bank)

        bank_x = BANK_OFFSET_X if side == "l" else -BANK_OFFSET_X
        bank_eb = edit_bones.new(bank_name)
        bank_eb.head = foot_head + Vector((bank_x, 0, HEEL_OFFSET_Z))
        bank_eb.tail = bank_eb.head + Vector((0, 0, 0.005))
        bank_eb.use_deform = False
        bank_eb.parent = foot_eb
        created += 1

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="POSE")
    guide_color = (0.9, 0.9, 0.0)

    for foot_name in foot_bone_names:
        for suffix, guide_role in [
            (GUIDE_SUFFIX_HEEL, f"{prefix_short}_heel_{side}"),
            (GUIDE_SUFFIX_BANK, f"{prefix_short}_bank_{side}"),
        ]:
            guide_name = f"{foot_name}{suffix}"
            pbone = preview_obj.pose.bones.get(guide_name)
            if pbone:
                pbone[role_prop_key] = guide_role
                pbone.color.palette = "CUSTOM"
                pbone.color.custom.normal = guide_color
                pbone.color.custom.select = (1.0, 1.0, 0.3)
                pbone.color.custom.active = (1.0, 1.0, 0.5)

    bpy.ops.object.mode_set(mode="OBJECT")
    if prev_mode == "POSE":
        bpy.ops.object.mode_set(mode="POSE")

    return created


def _detect_guide_kind(role_label, bone_name):
    if "_heel_" in role_label or bone_name.endswith(GUIDE_SUFFIX_HEEL):
        return "heel"
    if "_bank_" in role_label or bone_name.endswith(GUIDE_SUFFIX_BANK):
        return "bank"
    return None


def _detect_guide_side(role_label, foot_name):
    if role_label.endswith("_l") or foot_name.endswith("_L") or foot_name.endswith(".l"):
        return "l"
    if role_label.endswith("_r") or foot_name.endswith("_R") or foot_name.endswith(".r"):
        return "r"
    return "l"


def _guide_default_local_head(foot_head, kind, side):
    if kind == "heel":
        return foot_head + Vector((0.0, HEEL_OFFSET_Y, HEEL_OFFSET_Z))

    bank_x = BANK_OFFSET_X if side == "l" else -BANK_OFFSET_X
    return foot_head + Vector((bank_x, 0.0, HEEL_OFFSET_Z))


def _is_default_foot_guide(preview_local_positions, guide_name, foot_name, kind, side):
    guide_local = preview_local_positions.get(guide_name)
    foot_local = preview_local_positions.get(foot_name)
    if not guide_local or not foot_local:
        return False

    expected_head = _guide_default_local_head(foot_local[0], kind, side)
    current_head = guide_local[0]
    return (current_head - expected_head).length <= GUIDE_DEFAULT_TOLERANCE


def _compute_auto_foot_guide_world(
    foot_world_head, foot_world_tail, kind, side, toe_world_tail=None
):
    foot_length = (foot_world_tail - foot_world_head).length
    toe_length = (toe_world_tail - foot_world_tail).length if toe_world_tail else 0
    total_length = max(foot_length + toe_length, 0.001)

    forward = foot_world_tail - foot_world_head
    forward.z = 0.0  # XY 평면에서 방향 계산
    if forward.length < 0.0001:
        forward = Vector((0.0, 1.0, 0.0))
    forward.normalize()

    lateral = Vector((0.0, 0.0, 1.0)).cross(forward)
    if lateral.length < 0.0001:
        lateral = Vector((1.0, 0.0, 0.0))
    else:
        lateral.normalize()

    if side == "r":
        lateral.negate()

    back_offset = min(total_length * AUTO_HEEL_BACK_RATIO, AUTO_GUIDE_MAX_OFFSET)
    side_offset = min(total_length * AUTO_BANK_SIDE_RATIO, AUTO_GUIDE_MAX_OFFSET)

    base = Vector((foot_world_head.x, foot_world_head.y, 0.0))

    if kind == "heel":
        head = base - forward * back_offset
    else:  # bank
        head = base + lateral * side_offset
    head.z = 0.0

    bone_len = max(total_length * 0.50, 0.015)
    tail = head + forward * bone_len
    tail.z = 0.0
    return head, tail

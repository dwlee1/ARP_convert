"""
arp_convert_addon에서 분리한 cc bone 생성 + constraint 헬퍼.

커스텀(unmapped) 본의 이름 변환, 연결 판단, 길이 보정, ARP 아마추어에
cc_ 본 생성, constraint 복제 등 Build Rig Step 3/4에서 쓰이는 함수들.
"""

import bpy
from mathutils import Vector


def _make_cc_bone_name(source_bone_name):
    """source 본 이름을 커스텀 본 이름으로 변환. 원본 이름 유지 (cc_ 접두사 없음)."""
    return source_bone_name


def _should_connect_cc_bone(
    source_bone_name, resolved_parent_name, preview_hierarchy, custom_bone_names
):
    bone_info = preview_hierarchy.get(source_bone_name)
    if not bone_info or not bone_info.get("use_connect"):
        return False

    direct_parent_name = bone_info.get("parent")
    if direct_parent_name not in custom_bone_names:
        return False

    return resolved_parent_name == _make_cc_bone_name(direct_parent_name)


def _ensure_nonzero_bone_length(local_head, local_tail):
    """길이가 0에 가까운 본은 미세 오프셋을 줘서 Blender 오류를 피한다."""
    if (local_tail - local_head).length >= 0.0001:
        return local_tail

    offset = Vector((0.0, 0.01, 0.0))
    if local_head.length > 0.0001:
        offset = local_head.normalized() * 0.01
    return local_head + offset


def _create_cc_bones_from_preview(
    arp_obj,
    preview_obj,
    preview_positions,
    custom_bone_names,
    deform_to_ref,
    arp_chains,
    log,
):
    """
    Preview의 unmapped 역할 본을 기반으로 cc_ 본을 직접 생성하거나 갱신한다.
    custom 체인은 Preview 계층을 그대로 따르고, non-custom 조상은 ARP deform 본에 붙인다.
    """
    from arp_convert_addon import (
        _build_cc_parent_targets,
        _build_preview_hierarchy,
        _resolve_cc_parent_name,
    )

    if not custom_bone_names:
        return 0, {}

    preview_hierarchy = _build_preview_hierarchy(preview_obj)
    custom_bone_names = list(custom_bone_names)
    custom_bone_set = set(custom_bone_names)
    source_to_deform_parent, root_parent_name = _build_cc_parent_targets(
        arp_obj,
        arp_chains,
        deform_to_ref,
        log,
    )

    from skeleton_analyzer import order_bones_by_hierarchy

    ordered_custom_bones = order_bones_by_hierarchy(custom_bone_names, preview_hierarchy)

    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = arp_obj.data.edit_bones
    arp_matrix_inv = arp_obj.matrix_world.inverted()
    created = 0
    cc_bone_map = {}

    for bone_name in ordered_custom_bones:
        if bone_name not in preview_positions:
            log(f"  cc_ 생성 스킵 ({bone_name}): Preview 위치 없음", "WARN")
            continue

        world_head, world_tail, roll = preview_positions[bone_name]
        local_head = arp_matrix_inv @ world_head
        local_tail = arp_matrix_inv @ world_tail
        local_tail = _ensure_nonzero_bone_length(local_head, local_tail)

        cc_name = _make_cc_bone_name(bone_name)
        cc_eb = edit_bones.get(cc_name)
        if cc_eb is None:
            cc_eb = edit_bones.new(cc_name)
            created += 1
            log(f"  cc_ 생성: {bone_name} -> {cc_name}")
        else:
            log(f"  cc_ 갱신: {bone_name} -> {cc_name}")

        cc_eb.head = local_head
        cc_eb.tail = local_tail
        cc_eb.roll = roll
        cc_eb.use_connect = False

        parent_name = _resolve_cc_parent_name(
            bone_name,
            preview_hierarchy,
            custom_bone_set,
            source_to_deform_parent,
            root_parent_name,
        )
        parent_eb = edit_bones.get(parent_name)
        if parent_eb:
            cc_eb.parent = parent_eb
            cc_eb.use_connect = _should_connect_cc_bone(
                bone_name,
                parent_name,
                preview_hierarchy,
                custom_bone_set,
            )
        else:
            cc_eb.parent = None
            log(f"  cc_ 부모 없음 ({cc_name}): {parent_name}", "WARN")

        cc_bone_map[bone_name] = cc_name
        log(f"  cc_ 계층 적용: {bone_name} -> {cc_name} (parent={parent_name})")

    bpy.ops.object.mode_set(mode="OBJECT")

    for bone_name in ordered_custom_bones:
        cc_name = _make_cc_bone_name(bone_name)
        bone = arp_obj.data.bones.get(cc_name)
        if bone:
            bone.use_deform = True
        # ARP 커스텀 본 태깅: custom_bone 프로퍼티 추가 (cc_ 접두사 대체)
        pose_bone = arp_obj.pose.bones.get(cc_name)
        if pose_bone:
            pose_bone["custom_bone"] = 1

    return created, cc_bone_map


SUPPORTED_CUSTOM_CONSTRAINTS = {
    "COPY_ROTATION",
    "COPY_LOCATION",
    "COPY_SCALE",
    "DAMPED_TRACK",
    "LIMIT_ROTATION",
    "LIMIT_LOCATION",
    "LIMIT_SCALE",
    "STRETCH_TO",
    "TRACK_TO",
    "LOCKED_TRACK",
    "CHILD_OF",
    "COPY_TRANSFORMS",
    "TRANSFORMATION",
}


def _copy_constraint_settings(src_constraint, dst_constraint):
    common_props = [
        # 기본
        "name",
        "mute",
        "influence",
        "owner_space",
        "target_space",
        "mix_mode",
        # 축 사용/반전
        "use_x",
        "use_y",
        "use_z",
        "invert_x",
        "invert_y",
        "invert_z",
        "use_offset",
        "head_tail",
        # 트래킹
        "track_axis",
        "up_axis",
        "lock_axis",
        # 제한
        "use_limit_x",
        "use_limit_y",
        "use_limit_z",
        "use_min_x",
        "use_min_y",
        "use_min_z",
        "use_max_x",
        "use_max_y",
        "use_max_z",
        "min_x",
        "max_x",
        "min_y",
        "max_y",
        "min_z",
        "max_z",
        "use_transform_limit",
        # 스케일/변환
        "power",
        "use_make_uniform",
        # STRETCH_TO
        "rest_length",
        "bulge",
        "volume",
        "keep_axis",
        # CHILD_OF
        "use_location_x",
        "use_location_y",
        "use_location_z",
        "use_rotation_x",
        "use_rotation_y",
        "use_rotation_z",
        "use_scale_x",
        "use_scale_y",
        "use_scale_z",
        # COPY_TRANSFORMS
        "remove_target_shear",
        # TRANSFORMATION
        "use_motion_extrapolate",
        "map_from",
        "map_to",
        "from_min_x",
        "from_max_x",
        "from_min_y",
        "from_max_y",
        "from_min_z",
        "from_max_z",
        "to_min_x",
        "to_max_x",
        "to_min_y",
        "to_max_y",
        "to_min_z",
        "to_max_z",
        "map_to_x_from",
        "map_to_y_from",
        "map_to_z_from",
    ]

    for prop_name in common_props:
        if hasattr(src_constraint, prop_name) and hasattr(dst_constraint, prop_name):
            try:
                setattr(dst_constraint, prop_name, getattr(src_constraint, prop_name))
            except Exception:
                pass


def _copy_custom_bone_constraints(
    source_obj,
    arp_obj,
    custom_bone_names,
    deform_to_ref,
    log,
):
    """
    source custom bone(face/unmapped) 제약 조건을 ARP의 cc_ 본으로 복제한다.
    """
    from arp_weight_xfer import _map_source_bone_to_target_bone

    if not custom_bone_names:
        return 0

    created = 0
    source_custom_bones = set(custom_bone_names)

    bpy.ops.object.mode_set(mode="POSE")
    src_pose_bones = source_obj.pose.bones
    dst_pose_bones = arp_obj.pose.bones

    for source_bone_name in custom_bone_names:
        src_pbone = src_pose_bones.get(source_bone_name)
        dst_pbone = dst_pose_bones.get(_make_cc_bone_name(source_bone_name))
        if src_pbone is None or dst_pbone is None:
            continue

        for src_constraint in src_pbone.constraints:
            if src_constraint.type not in SUPPORTED_CUSTOM_CONSTRAINTS:
                log(
                    f"  constraint 건너뜀 (미지원): {source_bone_name} / {src_constraint.type}",
                    "WARN",
                )
                continue

            try:
                dst_constraint = dst_pbone.constraints.new(src_constraint.type)
                _copy_constraint_settings(src_constraint, dst_constraint)

                if hasattr(src_constraint, "target") and hasattr(dst_constraint, "target"):
                    target_obj = src_constraint.target
                    if target_obj == source_obj:
                        dst_constraint.target = arp_obj
                    else:
                        dst_constraint.target = target_obj

                if hasattr(src_constraint, "subtarget") and hasattr(dst_constraint, "subtarget"):
                    mapped_subtarget = _map_source_bone_to_target_bone(
                        src_constraint.subtarget,
                        source_custom_bones,
                        deform_to_ref,
                    )
                    dst_constraint.subtarget = mapped_subtarget or src_constraint.subtarget

                created += 1
                log(f"  constraint 복제: {source_bone_name} / {src_constraint.type}")
            except Exception as e:
                log(
                    f"  constraint 복제 실패 ({source_bone_name}, {src_constraint.type}): {e}",
                    "WARN",
                )

    bpy.ops.object.mode_set(mode="OBJECT")
    return created

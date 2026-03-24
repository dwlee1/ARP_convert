"""
ARP Rig Convert 애드온
======================
소스 deform 본 → Preview Armature 생성 → 역할 배정/수정 → ARP 리그 생성.

설치:
  Edit > Preferences > Add-ons > Install > 이 파일 선택
  또는 Blender Scripting 탭에서 직접 실행 (Run Script)
"""

bl_info = {
    "name": "ARP Rig Convert",
    "author": "BlenderRigConvert",
    "version": (2, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > ARP Convert",
    "description": "Preview Armature 기반 ARP 리그 변환",
    "category": "Rigging",
}

import bpy
import json
import os
import sys
import time
import traceback
from mathutils import Vector
from bpy.props import (
    StringProperty, FloatProperty, IntProperty,
    BoolProperty, EnumProperty, PointerProperty,
)
from bpy.types import PropertyGroup, Operator, Panel


# ═══════════════════════════════════════════════════════════════
# scripts/ 경로 설정
# ═══════════════════════════════════════════════════════════════

def _ensure_scripts_path():
    """scripts/ 폴더를 sys.path에 추가"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "skeleton_analyzer.py")):
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        return script_dir

    if bpy.data.filepath:
        d = os.path.dirname(bpy.data.filepath)
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


def _reload_modules():
    """개발 중 모듈 리로드"""
    import importlib
    for mod_name in ['skeleton_analyzer', 'arp_utils']:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


def _make_cc_bone_name(source_bone_name):
    """source 본 이름을 Remap 규칙과 맞는 cc_ 이름으로 변환."""
    return f"cc_{source_bone_name.lower()}"


def _find_cc_parent_name(source_bone_name, preview_obj, custom_bone_names, deform_to_ref):
    """
    custom 체인 내부 부모가 있으면 해당 cc_ 본에 연결.
    아니면 이미 매핑된 ARP ref 부모를 사용하고, 마지막 fallback은 root/head ref다.
    """
    preview_bone = preview_obj.data.bones.get(source_bone_name)
    if preview_bone and preview_bone.parent:
        parent_name = preview_bone.parent.name
        if parent_name in custom_bone_names:
            return _make_cc_bone_name(parent_name)
        if parent_name in deform_to_ref:
            return deform_to_ref[parent_name]
        if "head" in parent_name.lower() or "jaw" in parent_name.lower() or "eye" in parent_name.lower():
            return "head_ref.x"
    return "root_ref.x"


def _ensure_nonzero_bone_length(local_head, local_tail):
    """길이가 0에 가까운 본은 미세 오프셋을 줘서 Blender 오류를 피한다."""
    if (local_tail - local_head).length >= 0.0001:
        return local_tail

    offset = Vector((0.0, 0.01, 0.0))
    if local_head.length > 0.0001:
        offset = local_head.normalized() * 0.01
    return local_head + offset


# ═══════════════════════════════════════════════════════════════
# ARP 네이티브 체인 조정 래퍼
# ═══════════════════════════════════════════════════════════════

def _get_arp_set_functions():
    """ARP 내부 set_spine/set_neck/set_tail/set_ears 함수를 import."""
    try:
        from bl_ext.user_default.auto_rig_pro.src.auto_rig import (
            set_spine, set_neck, set_tail, set_ears,
        )
        return set_spine, set_neck, set_tail, set_ears
    except ImportError:
        return None, None, None, None


def _select_edit_bone(arp_obj, bone_name):
    """Edit Mode에서 특정 본을 선택하고 active로 설정."""
    edit_bones = arp_obj.data.edit_bones
    bpy.ops.armature.select_all(action='DESELECT')
    eb = edit_bones.get(bone_name)
    if eb:
        eb.select = True
        eb.select_head = True
        eb.select_tail = True
        arp_obj.data.edit_bones.active = eb
        return True
    return False


def _adjust_chain_counts(arp_obj, roles, arp_chains, log):
    """
    소스 체인 개수에 맞춰 ARP ref 본 개수를 조정.
    ARP 네이티브 함수(set_spine/set_neck/set_tail/set_ears)를 사용.

    Returns:
        True if any adjustment was made (ref 재탐색 필요), False otherwise
    """
    set_spine, set_neck, set_tail, set_ears = _get_arp_set_functions()
    if set_spine is None:
        log("  [WARN] ARP 네이티브 함수 import 실패 — 체인 매칭 건너뜀")
        return False

    adjusted = False

    # 조정 대상: (역할, ARP 함수, 파라미터 이름, 선택할 ref 본 찾기 키워드)
    adjustments = [
        ('spine', set_spine, 'count', 'spine_01_ref'),
        ('neck',  set_neck,  'neck_count', 'neck_ref'),
        ('tail',  set_tail,  'tail_count', 'tail_00_ref'),
    ]

    for chain_role, set_func, param_name, ref_search_key in adjustments:
        source_bones = roles.get(chain_role, [])
        arp_refs = arp_chains.get(chain_role, [])

        if not source_bones or not arp_refs:
            continue

        src_count = len(source_bones)
        arp_count = len(arp_refs)

        if src_count == arp_count:
            continue

        log(f"  [체인 매칭] {chain_role}: 소스 {src_count} vs ARP {arp_count}")

        # 해당 ref 본 찾아서 선택
        ref_bone_name = None
        for ref_name in arp_refs:
            if ref_search_key in ref_name:
                ref_bone_name = ref_name
                break
        if ref_bone_name is None:
            ref_bone_name = arp_refs[0]

        if not _select_edit_bone(arp_obj, ref_bone_name):
            log(f"    [WARN] ref 본 '{ref_bone_name}' 선택 실패")
            continue

        try:
            # ARP set_spine은 root를 포함한 카운트 → ref 본 수 = count - 1
            call_count = src_count + 1 if chain_role == 'spine' else src_count
            kwargs = {param_name: call_count}
            set_func(**kwargs)
            log(f"    → ARP {chain_role} 개수를 {call_count}으로 변경 완료 (소스 {src_count}본)")
            adjusted = True
        except Exception as e:
            log(f"    [ERROR] {chain_role} 개수 변경 실패: {e}")

    # ear: L/R 개별 호출
    if set_ears:
        for side_key, side_arg in [('ear_l', '.l'), ('ear_r', '.r')]:
            source_bones = roles.get(side_key, [])
            arp_refs = arp_chains.get(side_key, [])

            if not source_bones or not arp_refs:
                continue

            src_count = len(source_bones)
            arp_count = len(arp_refs)

            if src_count == arp_count:
                continue

            log(f"  [체인 매칭] {side_key}: 소스 {src_count} vs ARP {arp_count}")

            if not _select_edit_bone(arp_obj, arp_refs[0]):
                log(f"    [WARN] ref 본 '{arp_refs[0]}' 선택 실패")
                continue

            try:
                set_ears(ears_amount=src_count, side_arg=side_arg)
                log(f"    → ARP {side_key} 개수를 {src_count}으로 변경 완료")
                adjusted = True
            except Exception as e:
                log(f"    [ERROR] {side_key} 개수 변경 실패: {e}")

    return adjusted


def _create_cc_bones_from_preview(
    arp_obj,
    preview_obj,
    preview_positions,
    custom_bone_names,
    deform_to_ref,
    log,
):
    """
    Preview의 unmapped 역할 본을 기반으로 cc_ 본을 직접 생성한다.

    Returns:
        tuple: (생성 개수, cc_bone_map {소스본이름: cc_본이름})
    """
    if not custom_bone_names:
        return 0, {}

    bpy.ops.object.mode_set(mode='EDIT')
    edit_bones = arp_obj.data.edit_bones
    arp_matrix_inv = arp_obj.matrix_world.inverted()

    created = 0
    cc_bone_map = {}
    ordered_custom_bones = []
    pending = set(custom_bone_names)

    # 부모가 먼저 생성되도록 간단한 위상 순서를 만든다.
    while pending:
        progressed = False
        for bone_name in list(pending):
            preview_bone = preview_obj.data.bones.get(bone_name)
            parent_name = preview_bone.parent.name if preview_bone and preview_bone.parent else None
            if parent_name not in pending:
                ordered_custom_bones.append(bone_name)
                pending.remove(bone_name)
                progressed = True
        if not progressed:
            ordered_custom_bones.extend(sorted(pending))
            break

    for bone_name in ordered_custom_bones:
        if bone_name not in preview_positions:
            log(f"  cc_ 생성 스킵 ({bone_name}): Preview 위치 없음", "WARN")
            continue

        cc_name = _make_cc_bone_name(bone_name)
        if edit_bones.get(cc_name):
            log(f"  cc_ 이미 존재: {cc_name}")
            cc_bone_map[bone_name] = cc_name
            continue

        world_head, world_tail, roll = preview_positions[bone_name]
        local_head = arp_matrix_inv @ world_head
        local_tail = arp_matrix_inv @ world_tail
        local_tail = _ensure_nonzero_bone_length(local_head, local_tail)

        new_eb = edit_bones.new(cc_name)
        new_eb.head = local_head
        new_eb.tail = local_tail
        new_eb.roll = roll
        new_eb.use_connect = False

        parent_name = _find_cc_parent_name(
            bone_name,
            preview_obj,
            set(custom_bone_names),
            deform_to_ref,
        )
        parent_eb = edit_bones.get(parent_name)
        if parent_eb:
            new_eb.parent = parent_eb
        else:
            log(f"  cc_ 부모 없음 ({cc_name}): {parent_name}", "WARN")

        created += 1
        cc_bone_map[bone_name] = cc_name
        log(f"  cc_ 생성: {bone_name} -> {cc_name} (parent={parent_name})")

    bpy.ops.object.mode_set(mode='OBJECT')

    # bone.use_deform은 Object Mode에서만 설정 가능
    for bone_name in ordered_custom_bones:
        cc_name = _make_cc_bone_name(bone_name)
        bone = arp_obj.data.bones.get(cc_name)
        if bone:
            bone.use_deform = True

    return created, cc_bone_map


def _get_bone_side(name):
    """본 이름에서 사이드 추출 (.l/_L → L, .r/_R → R, .x/기타 → X)"""
    if name.endswith('.l'):
        return 'L'
    if name.endswith('.r'):
        return 'R'
    if name.endswith('.x'):
        return 'X'
    if name.endswith('_L') or name.endswith('_l'):
        return 'L'
    if name.endswith('_R') or name.endswith('_r'):
        return 'R'
    return 'X'


def _build_position_weight_map(source_obj, arp_obj, cc_bone_map, log):
    """
    독점 소스 중심 매칭 + orphan 재배정으로 소스 → ARP 웨이트 매핑 생성.

    Phase 1: 사이드 필터 + 거리순 독점 매칭 (각 소스/ARP 본 1:1)
    Phase 2: 미배정 ARP orphan → 가장 가까운 소스에 추가 (사이드 필터)
    Phase 3: 소스에 여러 ARP 본이 배정되면 본 길이 비율로 분할

    cc_ 본은 이름 기반 1:1 유지.

    Returns:
        dict: {소스본이름: [(ARP본이름, 비율), ...]}
    """
    weight_map = {}

    # ARP Deform 컬렉션에서 후보 수집 (stretch/twist 포함)
    deform_col = arp_obj.data.collections_all.get('Deform')
    if not deform_col:
        log("  Deform 컬렉션 미발견", "ERROR")
        return weight_map

    arp_matrix = arp_obj.matrix_world
    candidates = {}      # {name: world_head_pos}
    cand_lengths = {}    # {name: bone_length}

    for bone in arp_obj.data.bones:
        if deform_col not in bone.collections.values():
            continue
        if '_ref' in bone.name:
            continue
        head_w = arp_matrix @ bone.head_local
        tail_w = arp_matrix @ bone.tail_local
        candidates[bone.name] = head_w
        cand_lengths[bone.name] = (tail_w - head_w).length

    log(f"  Deform 매칭 후보: {len(candidates)}개")

    # 소스 deform 본 위치 수집
    src_matrix = source_obj.matrix_world
    source_deform = {}
    for bone in source_obj.data.bones:
        if bone.use_deform:
            source_deform[bone.name] = src_matrix @ bone.head_local

    # Phase 1: 독점 소스 중심 매칭 (사이드 필터 + 거리순)
    match_pairs = []
    for src_name, src_pos in source_deform.items():
        if src_name in cc_bone_map:
            continue
        src_side = _get_bone_side(src_name)
        for cand_name, cand_pos in candidates.items():
            if _get_bone_side(cand_name) != src_side:
                continue
            dist = (src_pos - cand_pos).length
            match_pairs.append((dist, src_name, cand_name))

    match_pairs.sort(key=lambda x: (x[0], x[1]))

    initial_map = {}
    claimed_arp = set()
    claimed_src = set()

    for dist, src_name, cand_name in match_pairs:
        if src_name in claimed_src or cand_name in claimed_arp:
            continue
        initial_map[src_name] = cand_name
        claimed_src.add(src_name)
        claimed_arp.add(cand_name)

    # Phase 2: orphan ARP 본 → ARP 공간 위치 기반으로 가장 가까운 claimed 본에 추가
    orphans = [n for n in candidates if n not in claimed_arp]
    src_to_arp = {src: [arp] for src, arp in initial_map.items()}
    initial_map_inv = {arp: src for src, arp in initial_map.items()}

    for orphan in orphans:
        orphan_pos = candidates[orphan]
        orphan_side = _get_bone_side(orphan)
        best_claimed = None
        best_dist = float('inf')
        for claimed_name in claimed_arp:
            if _get_bone_side(claimed_name) != orphan_side:
                continue
            dist = (orphan_pos - candidates[claimed_name]).length
            if dist < best_dist:
                best_dist = dist
                best_claimed = claimed_name
        if best_claimed and best_claimed in initial_map_inv:
            owner_src = initial_map_inv[best_claimed]
            src_to_arp[owner_src].append(orphan)

    # Phase 3: 본 길이 비율 계산 + 로깅
    for src_name, arp_list in src_to_arp.items():
        if len(arp_list) == 1:
            dist = (source_deform[src_name] - candidates[arp_list[0]]).length
            weight_map[src_name] = [(arp_list[0], 1.0)]
            log(f"  위치 매칭: {src_name} → {arp_list[0]} (거리={dist:.4f})")
        else:
            total_len = sum(cand_lengths.get(a, 0.01) for a in arp_list)
            ratios = [(a, cand_lengths.get(a, 0.01) / total_len) for a in arp_list]
            split_str = " + ".join(f"{a}({r:.0%})" for a, r in ratios)
            weight_map[src_name] = ratios
            log(f"  길이 분할: {src_name} → {split_str}")

    # cc_ 매핑 추가
    for src_name, cc_name in cc_bone_map.items():
        weight_map[src_name] = [(cc_name, 1.0)]
        log(f"  cc_ 매핑: {src_name} → {cc_name}")

    return weight_map


def _transfer_all_weights(source_obj, arp_obj, weight_map, log):
    """
    소스 메시의 vertex group weight를 ARP 본 이름으로 복사하고,
    Armature modifier를 ARP 아마추어로 변경한다.
    1:N 분할 매핑 시 weight * ratio 로 적용.

    Args:
        source_obj: 소스 Armature 오브젝트
        arp_obj: ARP Armature 오브젝트
        weight_map: {소스본이름: [(ARP본이름, 비율), ...]}
        log: 로그 함수
    """
    from arp_utils import find_mesh_objects
    meshes = find_mesh_objects(source_obj)
    total_groups = 0

    for mesh_obj in meshes:
        log(f"  메시 '{mesh_obj.name}' 처리 중...")

        # ARP vertex group 초기화
        all_targets = set()
        for mappings in weight_map.values():
            for arp_name, _ in mappings:
                all_targets.add(arp_name)
        for arp_name in all_targets:
            existing = mesh_obj.vertex_groups.get(arp_name)
            if existing:
                mesh_obj.vertex_groups.remove(existing)

        for src_name, mappings in weight_map.items():
            src_vg = mesh_obj.vertex_groups.get(src_name)
            if not src_vg:
                continue

            for arp_name, ratio in mappings:
                arp_vg = mesh_obj.vertex_groups.get(arp_name)
                if not arp_vg:
                    arp_vg = mesh_obj.vertex_groups.new(name=arp_name)

                for v in mesh_obj.data.vertices:
                    for g in v.groups:
                        if g.group == src_vg.index:
                            arp_vg.add([v.index], g.weight * ratio, 'REPLACE')
                            break

            total_groups += 1

        # 소스 vertex group 정리
        removed = 0
        for src_name, mappings in weight_map.items():
            is_target = any(src_name == arp_name for arp_name, _ in mappings)
            if is_target:
                continue
            src_vg = mesh_obj.vertex_groups.get(src_name)
            if src_vg:
                mesh_obj.vertex_groups.remove(src_vg)
                removed += 1
        if removed:
            log(f"  소스 vertex group 정리: {removed}개 삭제")

        # Armature modifier를 ARP로 변경
        for mod in mesh_obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == source_obj:
                mod.object = arp_obj
                log(f"  Armature modifier 변경: {source_obj.name} → {arp_obj.name}")
                break

    log(f"  weight 전송 완료: {total_groups} groups, {len(meshes)} meshes")
    return total_groups


SUPPORTED_CUSTOM_CONSTRAINTS = {
    'COPY_ROTATION',
    'COPY_LOCATION',
    'COPY_SCALE',
    'DAMPED_TRACK',
    'LIMIT_ROTATION',
    'LIMIT_LOCATION',
    'LIMIT_SCALE',
    'STRETCH_TO',
    'TRACK_TO',
    'LOCKED_TRACK',
    'CHILD_OF',
    'COPY_TRANSFORMS',
    'TRANSFORMATION',
}


def _map_source_bone_to_target_bone(source_bone_name, custom_bone_names, deform_to_ref):
    if source_bone_name in custom_bone_names:
        return _make_cc_bone_name(source_bone_name)
    return deform_to_ref.get(source_bone_name)


def _copy_constraint_settings(src_constraint, dst_constraint):
    common_props = [
        # 기본
        'name', 'mute', 'influence',
        'owner_space', 'target_space',
        'mix_mode',
        # 축 사용/반전
        'use_x', 'use_y', 'use_z',
        'invert_x', 'invert_y', 'invert_z',
        'use_offset',
        'head_tail',
        # 트래킹
        'track_axis', 'up_axis', 'lock_axis',
        # 제한
        'use_limit_x', 'use_limit_y', 'use_limit_z',
        'use_min_x', 'use_min_y', 'use_min_z',
        'use_max_x', 'use_max_y', 'use_max_z',
        'min_x', 'max_x', 'min_y', 'max_y', 'min_z', 'max_z',
        'use_transform_limit',
        # 스케일/변환
        'power',
        'use_make_uniform',
        # STRETCH_TO
        'rest_length', 'bulge', 'volume',
        'keep_axis',
        # CHILD_OF
        'use_location_x', 'use_location_y', 'use_location_z',
        'use_rotation_x', 'use_rotation_y', 'use_rotation_z',
        'use_scale_x', 'use_scale_y', 'use_scale_z',
        # COPY_TRANSFORMS
        'remove_target_shear',
        # TRANSFORMATION
        'use_motion_extrapolate',
        'map_from', 'map_to',
        'from_min_x', 'from_max_x', 'from_min_y', 'from_max_y',
        'from_min_z', 'from_max_z',
        'to_min_x', 'to_max_x', 'to_min_y', 'to_max_y',
        'to_min_z', 'to_max_z',
        'map_to_x_from', 'map_to_y_from', 'map_to_z_from',
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
    if not custom_bone_names:
        return 0

    created = 0
    source_custom_bones = set(custom_bone_names)

    bpy.ops.object.mode_set(mode='POSE')
    src_pose_bones = source_obj.pose.bones
    dst_pose_bones = arp_obj.pose.bones

    for source_bone_name in custom_bone_names:
        src_pbone = src_pose_bones.get(source_bone_name)
        dst_pbone = dst_pose_bones.get(_make_cc_bone_name(source_bone_name))
        if src_pbone is None or dst_pbone is None:
            continue

        for src_constraint in src_pbone.constraints:
            if src_constraint.type not in SUPPORTED_CUSTOM_CONSTRAINTS:
                log(f"  constraint 건너뜀 (미지원): {source_bone_name} / {src_constraint.type}", "WARN")
                continue

            try:
                dst_constraint = dst_pbone.constraints.new(src_constraint.type)
                _copy_constraint_settings(src_constraint, dst_constraint)

                if hasattr(src_constraint, 'target') and hasattr(dst_constraint, 'target'):
                    target_obj = src_constraint.target
                    if target_obj == source_obj:
                        dst_constraint.target = arp_obj
                    else:
                        dst_constraint.target = target_obj

                if hasattr(src_constraint, 'subtarget') and hasattr(dst_constraint, 'subtarget'):
                    mapped_subtarget = _map_source_bone_to_target_bone(
                        src_constraint.subtarget,
                        source_custom_bones,
                        deform_to_ref,
                    )
                    dst_constraint.subtarget = mapped_subtarget or src_constraint.subtarget

                created += 1
                log(f"  constraint 복제: {source_bone_name} / {src_constraint.type}")
            except Exception as e:
                log(f"  constraint 복제 실패 ({source_bone_name}, {src_constraint.type}): {e}", "WARN")

    bpy.ops.object.mode_set(mode='OBJECT')
    return created


# ═══════════════════════════════════════════════════════════════
# 역할 드롭다운
# ═══════════════════════════════════════════════════════════════

ROLE_ITEMS = [
    ('root', "Root", "루트 본"),
    ('spine', "Spine", "스파인 체인"),
    ('neck', "Neck", "목"),
    ('head', "Head", "머리"),
    ('back_leg_l', "Back Leg L", "뒷다리 좌"),
    ('back_leg_r', "Back Leg R", "뒷다리 우"),
    ('back_foot_l', "Back Foot L", "뒷발 좌"),
    ('back_foot_r', "Back Foot R", "뒷발 우"),
    ('front_leg_l', "Front Leg L", "앞다리 좌"),
    ('front_leg_r', "Front Leg R", "앞다리 우"),
    ('front_foot_l', "Front Foot L", "앞발 좌"),
    ('front_foot_r', "Front Foot R", "앞발 우"),
    ('ear_l', "Ear L", "귀 좌"),
    ('ear_r', "Ear R", "귀 우"),
    ('tail', "Tail", "꼬리"),
    ('unmapped', "Unmapped", "미매핑 (cc_ 커스텀 본)"),
]
ROLE_IDS = {item[0] for item in ROLE_ITEMS}


# ═══════════════════════════════════════════════════════════════
# 프로퍼티
# ═══════════════════════════════════════════════════════════════

class ARPCONV_Props(PropertyGroup):
    """전역 프로퍼티"""
    preview_armature: StringProperty(name="Preview Armature", default="")
    source_armature: StringProperty(name="소스 Armature", default="")
    is_analyzed: BoolProperty(name="분석 완료", default=False)
    confidence: FloatProperty(name="신뢰도", default=0.0)
    regression_fixture: StringProperty(
        name="Fixture JSON",
        default="",
        subtype='FILE_PATH',
    )
    regression_report_dir: StringProperty(
        name="Report Dir",
        default="",
        subtype='DIR_PATH',
    )
    regression_run_retarget: BoolProperty(
        name="Retarget 포함",
        default=True,
    )


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 1 — 분석 + Preview 생성
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_CreatePreview(Operator):
    """소스 deform 본 추출 → Preview Armature 생성"""
    bl_idname = "arp_convert.create_preview"
    bl_label = "리그 분석 + Preview 생성"
    bl_description = "소스 deform 본을 분석하여 역할별 색상이 적용된 Preview Armature를 생성"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                analyze_skeleton, create_preview_armature,
                generate_verification_report,
            )
        except ImportError as e:
            self.report({'ERROR'}, f"skeleton_analyzer 임포트 실패: {e}")
            return {'CANCELLED'}

        # 소스 아마추어 찾기
        source_obj = self._find_source(context)
        if source_obj is None:
            self.report({'ERROR'}, "소스 아마추어를 찾을 수 없습니다.")
            return {'CANCELLED'}

        # 기존 Preview 제거
        props = context.scene.arp_convert_props
        old_preview = bpy.data.objects.get(props.preview_armature)
        if old_preview:
            bpy.data.objects.remove(old_preview, do_unlink=True)

        # Object 모드 확보
        if bpy.context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        # 분석
        analysis = analyze_skeleton(source_obj)
        if 'error' in analysis:
            self.report({'ERROR'}, analysis['error'])
            return {'CANCELLED'}

        # 검증 리포트 출력
        print(generate_verification_report(analysis))

        # Preview Armature 생성
        preview_obj = create_preview_armature(source_obj, analysis)
        if preview_obj is None:
            self.report({'ERROR'}, "Preview Armature 생성 실패")
            return {'CANCELLED'}

        # 프로퍼티 저장
        props.source_armature = source_obj.name
        props.preview_armature = preview_obj.name
        props.is_analyzed = True
        props.confidence = analysis.get('confidence', 0)

        # Preview 선택
        bpy.ops.object.select_all(action='DESELECT')
        preview_obj.select_set(True)
        context.view_layer.objects.active = preview_obj

        self.report({'INFO'},
            f"Preview 생성 완료 (신뢰도: {props.confidence:.0%}). "
            f"본 선택 → 사이드바에서 역할 변경 가능.")
        return {'FINISHED'}

    def _find_source(self, context):
        """소스 아마추어 찾기: 선택된 것 우선, 없으면 자동"""
        if context.active_object and context.active_object.type == 'ARMATURE':
            c_count = len([b for b in context.active_object.data.bones
                          if b.name.startswith('c_')])
            if c_count <= 5 and '_preview' not in context.active_object.name:
                return context.active_object

        best_obj = None
        best_count = 0
        for obj in bpy.data.objects:
            if obj.type != 'ARMATURE':
                continue
            if '_preview' in obj.name:
                continue
            c_count = len([b for b in obj.data.bones if b.name.startswith('c_')])
            if c_count > 5:
                continue
            total = len(obj.data.bones)
            if total > best_count:
                best_count = total
                best_obj = obj
        return best_obj


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: 역할 변경
# ═══════════════════════════════════════════════════════════════

FOOT_ROLES = {'back_foot_l', 'back_foot_r', 'front_foot_l', 'front_foot_r'}
# bank/heel 가이드 본 접미사
GUIDE_SUFFIX_HEEL = "_heel"
GUIDE_SUFFIX_BANK = "_bank"
# 기본 오프셋 (foot 본 head 기준, 로컬 좌표)
HEEL_OFFSET_Z = -0.02    # 바닥 방향
HEEL_OFFSET_Y = -0.01    # 뒤쪽
BANK_OFFSET_X = 0.015    # 좌우
GUIDE_DEFAULT_TOLERANCE = 0.002
AUTO_HEEL_BACK_RATIO = 0.18
AUTO_HEEL_DOWN_RATIO = 0.08
AUTO_BANK_SIDE_RATIO = 0.14
AUTO_BANK_DOWN_RATIO = 0.04
AUTO_GUIDE_MAX_OFFSET = 0.03


def _set_preview_pose_bone_role(pbone, role, role_colors, role_prop_key):
    color = role_colors.get(role, role_colors['unmapped'])
    pbone[role_prop_key] = role
    pbone.color.palette = 'CUSTOM'
    pbone.color.custom.normal = color
    pbone.color.custom.select = tuple(min(c + 0.3, 1.0) for c in color)
    pbone.color.custom.active = tuple(min(c + 0.5, 1.0) for c in color)


def _create_foot_guides_for_role(context, preview_obj, foot_bone_names, role, role_prop_key):
    """
    foot 역할 본에 대해 heel/bank 가이드 본을 Preview에 자동 생성.
    SetRole 오퍼레이터와 회귀 테스트 러너에서 공통 사용한다.
    """
    prev_mode = context.mode
    if prev_mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')
    preview_obj.select_set(True)
    context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode='EDIT')

    edit_bones = preview_obj.data.edit_bones
    created = 0

    side = role.rsplit('_', 1)[-1]
    prefix = role.rsplit('_', 2)[0]
    prefix_short = prefix.replace('_foot', '')

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

        bank_x = BANK_OFFSET_X if side == 'l' else -BANK_OFFSET_X
        bank_eb = edit_bones.new(bank_name)
        bank_eb.head = foot_head + Vector((bank_x, 0, HEEL_OFFSET_Z))
        bank_eb.tail = bank_eb.head + Vector((0, 0, 0.005))
        bank_eb.use_deform = False
        bank_eb.parent = foot_eb
        created += 1

    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.mode_set(mode='POSE')
    guide_color = (0.9, 0.9, 0.0)

    for foot_name in foot_bone_names:
        for suffix, guide_role in [
            (GUIDE_SUFFIX_HEEL, f'{prefix_short}_heel_{side}'),
            (GUIDE_SUFFIX_BANK, f'{prefix_short}_bank_{side}'),
        ]:
            guide_name = f"{foot_name}{suffix}"
            pbone = preview_obj.pose.bones.get(guide_name)
            if pbone:
                pbone[role_prop_key] = guide_role
                pbone.color.palette = 'CUSTOM'
                pbone.color.custom.normal = guide_color
                pbone.color.custom.select = (1.0, 1.0, 0.3)
                pbone.color.custom.active = (1.0, 1.0, 0.5)

    bpy.ops.object.mode_set(mode='OBJECT')
    if prev_mode == 'POSE':
        bpy.ops.object.mode_set(mode='POSE')

    return created


def _resolve_project_root():
    script_dir = _ensure_scripts_path() or os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(script_dir)


def _resolve_regression_path(raw_path):
    if not raw_path:
        return ""
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.normpath(os.path.join(_resolve_project_root(), raw_path))


def _default_regression_report_dir():
    return os.path.join(_resolve_project_root(), "regression_reports")


def _load_regression_fixture(fixture_path):
    resolved_path = _resolve_regression_path(fixture_path)
    if not resolved_path or not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Fixture JSON 미발견: {resolved_path or fixture_path}")

    with open(resolved_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    roles = data.get('roles')
    if not isinstance(roles, dict):
        raise ValueError("Fixture JSON에는 'roles' 객체가 필요합니다.")

    normalized_roles = {}
    for role, bone_names in roles.items():
        if role not in ROLE_IDS:
            raise ValueError(f"지원하지 않는 role: {role}")
        if not isinstance(bone_names, list) or not all(isinstance(name, str) for name in bone_names):
            raise ValueError(f"role '{role}'의 값은 문자열 리스트여야 합니다.")
        normalized_roles[role] = bone_names

    apply_mode = str(data.get('apply_mode', 'replace')).lower()
    if apply_mode not in {'replace', 'overlay'}:
        raise ValueError("apply_mode는 'replace' 또는 'overlay'여야 합니다.")

    return {
        'path': resolved_path,
        'description': data.get('description', ''),
        'apply_mode': apply_mode,
        'roles': normalized_roles,
        'run_retarget': bool(data.get('run_retarget', True)),
    }


def _apply_fixture_roles(context, preview_obj, fixture_data):
    from skeleton_analyzer import ROLE_COLORS, ROLE_PROP_KEY

    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')
    preview_obj.select_set(True)
    context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode='POSE')

    if fixture_data['apply_mode'] == 'replace':
        for pbone in preview_obj.pose.bones:
            _set_preview_pose_bone_role(pbone, 'unmapped', ROLE_COLORS, ROLE_PROP_KEY)

    assigned = {}
    duplicate_bones = []
    missing_bones = []
    foot_roles = {}

    for role, bone_names in fixture_data['roles'].items():
        for bone_name in bone_names:
            pbone = preview_obj.pose.bones.get(bone_name)
            if pbone is None:
                missing_bones.append(bone_name)
                continue

            previous_role = assigned.get(bone_name)
            if previous_role and previous_role != role:
                duplicate_bones.append({
                    'bone': bone_name,
                    'previous_role': previous_role,
                    'new_role': role,
                })

            _set_preview_pose_bone_role(pbone, role, ROLE_COLORS, ROLE_PROP_KEY)
            assigned[bone_name] = role

            if role in FOOT_ROLES:
                foot_roles.setdefault(role, []).append(bone_name)

    bpy.ops.object.mode_set(mode='OBJECT')

    guide_count = 0
    for role, foot_bones in foot_roles.items():
        guide_count += _create_foot_guides_for_role(
            context,
            preview_obj,
            foot_bones,
            role,
            ROLE_PROP_KEY,
        )

    role_counts = {}
    for role in assigned.values():
        role_counts[role] = role_counts.get(role, 0) + 1

    return {
        'assigned_count': len(assigned),
        'guide_count': guide_count,
        'missing_bones': missing_bones,
        'duplicate_bones': duplicate_bones,
        'role_counts': role_counts,
        'apply_mode': fixture_data['apply_mode'],
    }


def _detect_guide_kind(role_label, bone_name):
    if '_heel_' in role_label or bone_name.endswith(GUIDE_SUFFIX_HEEL):
        return 'heel'
    if '_bank_' in role_label or bone_name.endswith(GUIDE_SUFFIX_BANK):
        return 'bank'
    return None


def _detect_guide_side(role_label, foot_name):
    if role_label.endswith('_l') or foot_name.endswith('_L') or foot_name.endswith('.l'):
        return 'l'
    if role_label.endswith('_r') or foot_name.endswith('_R') or foot_name.endswith('.r'):
        return 'r'
    return 'l'


def _guide_default_local_head(foot_head, kind, side):
    if kind == 'heel':
        return foot_head + Vector((0.0, HEEL_OFFSET_Y, HEEL_OFFSET_Z))

    bank_x = BANK_OFFSET_X if side == 'l' else -BANK_OFFSET_X
    return foot_head + Vector((bank_x, 0.0, HEEL_OFFSET_Z))


def _is_default_foot_guide(preview_local_positions, guide_name, foot_name, kind, side):
    guide_local = preview_local_positions.get(guide_name)
    foot_local = preview_local_positions.get(foot_name)
    if not guide_local or not foot_local:
        return False

    expected_head = _guide_default_local_head(foot_local[0], kind, side)
    current_head = guide_local[0]
    return (current_head - expected_head).length <= GUIDE_DEFAULT_TOLERANCE


def _compute_auto_foot_guide_world(foot_world_head, foot_world_tail, kind, side,
                                    toe_world_tail=None):
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

    if side == 'r':
        lateral.negate()

    back_offset = min(total_length * AUTO_HEEL_BACK_RATIO, AUTO_GUIDE_MAX_OFFSET)
    side_offset = min(total_length * AUTO_BANK_SIDE_RATIO, AUTO_GUIDE_MAX_OFFSET)

    base = Vector((foot_world_head.x, foot_world_head.y, 0.0))

    if kind == 'heel':
        head = base - forward * back_offset
    else:  # bank
        head = base + lateral * side_offset
    head.z = 0.0

    bone_len = max(total_length * 0.50, 0.015)
    tail = head + forward * bone_len
    tail.z = 0.0
    return head, tail


class ARPCONV_OT_SetRole(Operator):
    """선택된 본의 역할을 변경"""
    bl_idname = "arp_convert.set_role"
    bl_label = "역할 설정"
    bl_options = {'REGISTER', 'UNDO'}

    role: EnumProperty(name="역할", items=ROLE_ITEMS)

    def execute(self, context):
        _ensure_scripts_path()
        from skeleton_analyzer import ROLE_COLORS, ROLE_PROP_KEY

        preview_obj = context.active_object
        if not preview_obj or preview_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Preview Armature를 선택하세요.")
            return {'CANCELLED'}

        # 선택된 본에 역할 적용
        changed = 0
        foot_bones = []  # foot 역할로 변경된 본 이름 수집

        if context.mode == 'POSE':
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
            self.report({'WARNING'}, "본이 선택되지 않았습니다.")
            return {'FINISHED'}

        # foot 역할이면 bank/heel 가이드 본 자동 생성
        if foot_bones:
            guide_count = _create_foot_guides_for_role(
                context, preview_obj, foot_bones, self.role, ROLE_PROP_KEY)
            self.report({'INFO'},
                f"{changed}개 본 → {self.role} + 가이드 {guide_count}개 생성")
        else:
            self.report({'INFO'}, f"{changed}개 본 → {self.role}")

        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 3 — ARP 리그 생성
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_BuildRig(Operator):
    """Preview Armature 기반으로 ARP 리그 생성"""
    bl_idname = "arp_convert.build_rig"
    bl_label = "ARP 리그 생성"
    bl_description = "Preview → append_arp → ref 본 위치 복사 → match_to_rig"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                preview_to_analysis, build_preview_to_ref_mapping,
                ROLE_PROP_KEY,
            )
            from arp_utils import (
                log, ensure_object_mode, select_only,
                run_arp_operator, find_arp_armature,
            )
        except ImportError as e:
            self.report({'ERROR'}, f"모듈 임포트 실패: {e}")
            return {'CANCELLED'}

        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)

        if preview_obj is None:
            self.report({'ERROR'}, "Preview Armature가 없습니다. 먼저 [리그 분석]을 실행하세요.")
            return {'CANCELLED'}

        ensure_object_mode()

        # Step 1: ARP 리그 추가 (먼저 추가해야 실제 ref 본 이름을 알 수 있음)
        log("ARP 리그 추가 (dog 프리셋)")

        source_obj = bpy.data.objects.get(props.source_armature)
        if source_obj is None:
            self.report({'ERROR'}, f"소스 아마추어 '{props.source_armature}'를 찾을 수 없습니다.")
            return {'CANCELLED'}

        select_only(source_obj)
        try:
            run_arp_operator(bpy.ops.arp.append_arp, rig_preset='dog')
        except Exception as e:
            self.report({'ERROR'}, f"ARP 리그 추가 실패: {e}")
            return {'CANCELLED'}

        arp_obj = find_arp_armature()
        if arp_obj is None:
            self.report({'ERROR'}, "ARP 아마추어를 찾을 수 없습니다.")
            return {'CANCELLED'}

        # face/skull 비활성화
        try:
            ensure_object_mode()
            select_only(arp_obj)
            bpy.ops.object.mode_set(mode='EDIT')
            head_ref = arp_obj.data.edit_bones.get('head_ref')
            if head_ref:
                head_ref.select = True
                arp_obj.data.edit_bones.active = head_ref
            from bl_ext.user_default.auto_rig_pro.src.auto_rig import set_facial
            set_facial(enable=False, skull_bones=False)
            bpy.ops.object.mode_set(mode='OBJECT')
            log("face/skull 비활성화 완료")
        except Exception as e:
            log(f"face/skull 비활성화 실패 (무시): {e}")
            ensure_object_mode()

        # Step 2: Preview 본 위치 추출 (Edit 모드 1회)
        log("Preview 본 위치 추출")
        from skeleton_analyzer import (
            read_preview_roles, map_role_chain,
        )

        ensure_object_mode()

        bpy.ops.object.select_all(action='DESELECT')
        preview_obj.select_set(True)
        bpy.context.view_layer.objects.active = preview_obj
        bpy.ops.object.mode_set(mode='EDIT')
        preview_matrix = preview_obj.matrix_world
        preview_positions = {}
        preview_local_positions = {}
        for ebone in preview_obj.data.edit_bones:
            world_head = preview_matrix @ ebone.head.copy()
            world_tail = preview_matrix @ ebone.tail.copy()
            preview_positions[ebone.name] = (world_head, world_tail, ebone.roll)
            preview_local_positions[ebone.name] = (
                ebone.head.copy(),
                ebone.tail.copy(),
                ebone.roll,
            )
        bpy.ops.object.mode_set(mode='OBJECT')

        # Preview 역할 읽기 (Pose 모드 데이터, Edit 불필요)
        roles = read_preview_roles(preview_obj)
        preview_role_by_bone = {
            bone_name: role_label
            for role_label, bone_names in roles.items()
            for bone_name in bone_names
        }

        # Step 3: ARP Edit 모드 1회 진입 → ref 검색 + 매핑 + 위치 설정
        log("ARP ref 본 검색 + 위치 정렬 (단일 Edit 세션)")
        ensure_object_mode()

        bpy.ops.object.select_all(action='DESELECT')
        arp_obj.select_set(True)
        bpy.context.view_layer.objects.active = arp_obj
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = arp_obj.data.edit_bones
        arp_matrix_inv = arp_obj.matrix_world.inverted()

        # --- ref 본 인라인 검색 (Edit 모드 안에서) ---
        ref_names = set()
        ref_depth = {}
        for eb in edit_bones:
            if '_ref' in eb.name:
                ref_names.add(eb.name)
                d = 0
                p = eb.parent
                while p:
                    d += 1
                    p = p.parent
                ref_depth[eb.name] = d

        log(f"  ARP ref 본 발견: {len(ref_names)}개")

        def collect_connected_ref_chain(root_name):
            chain = []
            current_name = root_name
            visited = set()

            while current_name and current_name not in visited:
                eb = edit_bones.get(current_name)
                if eb is None:
                    break
                visited.add(current_name)
                chain.append(current_name)

                child_candidates = [
                    child.name for child in eb.children
                    if '_ref' in child.name
                    and 'bank' not in child.name
                    and 'heel' not in child.name
                ]
                if not child_candidates:
                    break

                child_candidates.sort(key=lambda x: ref_depth.get(x, 0))
                next_name = None
                for child_name in child_candidates:
                    child_eb = edit_bones.get(child_name)
                    if child_eb and child_eb.parent and child_eb.parent.name == current_name:
                        next_name = child_name
                        break
                if next_name is None:
                    break
                current_name = next_name

            return chain

        # 역할별 ref 본 분류 (인라인)
        FOOT_AUX_PREFIXES = ['foot_bank', 'foot_heel']

        arp_chains = {}

        # Root/Spine/Neck/Head/Tail
        for name in ref_names:
            if name.startswith('root_ref'):
                arp_chains.setdefault('root', []).append(name)
            elif 'spine_' in name and '_ref' in name:
                arp_chains.setdefault('spine', []).append(name)
            elif 'neck' in name and '_ref' in name:
                arp_chains.setdefault('neck', []).append(name)
            elif name.startswith('head_ref'):
                arp_chains.setdefault('head', []).append(name)
            elif 'tail_' in name and '_ref' in name:
                arp_chains.setdefault('tail', []).append(name)

        # 정렬
        for key in ['root', 'spine', 'neck', 'head', 'tail']:
            if key in arp_chains:
                arp_chains[key] = sorted(arp_chains[key],
                    key=lambda x: ref_depth.get(x, 0))

        # Legs/Feet/Ear (side별)
        for side_suffix, side_key in [('.l', 'l'), ('.r', 'r')]:
            for is_dupli, leg_prefix in [(False, 'back'), (True, 'front')]:
                thigh_roots = [n for n in ref_names
                               if n.startswith('thigh_b_ref')
                               and n.endswith(side_suffix)
                               and ('dupli' in n) == is_dupli]
                if not thigh_roots:
                    thigh_roots = [n for n in ref_names
                                   if n.startswith('thigh_ref')
                                   and n.endswith(side_suffix)
                                   and ('dupli' in n) == is_dupli]

                if thigh_roots:
                    thigh_roots.sort(key=lambda x: ref_depth.get(x, 0))
                    limb_chain = collect_connected_ref_chain(thigh_roots[0])
                    leg_bones = [n for n in limb_chain if n.startswith('thigh') or n.startswith('leg')]
                    foot_bones = [n for n in limb_chain if n.startswith('foot') or n.startswith('toes')]
                    if leg_bones:
                        arp_chains[f'{leg_prefix}_leg_{side_key}'] = leg_bones
                    if foot_bones:
                        arp_chains[f'{leg_prefix}_foot_{side_key}'] = foot_bones

                # Bank/Heel
                for aux_pfx in FOOT_AUX_PREFIXES:
                    aux_key = aux_pfx.replace('foot_', '')
                    cands = [n for n in ref_names
                             if n.startswith(aux_pfx) and '_ref' in n
                             and n.endswith(side_suffix)
                             and ('dupli' in n) == is_dupli]
                    if cands:
                        cands.sort(key=lambda x: ref_depth.get(x, 0))
                        arp_chains[f'{leg_prefix}_{aux_key}_{side_key}'] = cands

            # Ear
            ear_cands = sorted([n for n in ref_names
                                if 'ear' in n and '_ref' in n
                                and n.endswith(side_suffix)],
                               key=lambda x: ref_depth.get(x, 0))
            if ear_cands:
                arp_chains[f'ear_{side_key}'] = ear_cands

        # 검색 결과 로그
        log("  --- ARP ref 체인 ---")
        for role, bones in arp_chains.items():
            log(f"  {role:20s}: {' → '.join(bones)}")

        # --- 체인 개수 매칭 (ARP 네이티브 함수로 조정) ---
        chain_adjusted = _adjust_chain_counts(arp_obj, roles, arp_chains, log)

        if chain_adjusted:
            # set_* 함수가 Edit Mode를 변경할 수 있으므로 재진입
            if bpy.context.mode != 'EDIT_ARMATURE':
                bpy.ops.object.mode_set(mode='EDIT')

            # ref 본 재탐색 (set_* 호출로 이름/구조가 변경되었을 수 있음)
            edit_bones = arp_obj.data.edit_bones
            ref_names = set()
            ref_depth = {}
            for eb in edit_bones:
                if '_ref' in eb.name:
                    ref_names.add(eb.name)
                    d = 0
                    p = eb.parent
                    while p:
                        d += 1
                        p = p.parent
                    ref_depth[eb.name] = d

            log(f"  ref 본 재탐색: {len(ref_names)}개")

            # arp_chains 재구성
            arp_chains = {}

            for name in ref_names:
                if name.startswith('root_ref'):
                    arp_chains.setdefault('root', []).append(name)
                elif 'spine_' in name and '_ref' in name:
                    arp_chains.setdefault('spine', []).append(name)
                elif 'neck' in name and '_ref' in name:
                    arp_chains.setdefault('neck', []).append(name)
                elif name.startswith('head_ref'):
                    arp_chains.setdefault('head', []).append(name)
                elif 'tail_' in name and '_ref' in name:
                    arp_chains.setdefault('tail', []).append(name)

            for key in ['root', 'spine', 'neck', 'head', 'tail']:
                if key in arp_chains:
                    arp_chains[key] = sorted(arp_chains[key],
                        key=lambda x: ref_depth.get(x, 0))

            for side_suffix, side_key in [('.l', 'l'), ('.r', 'r')]:
                for is_dupli, leg_prefix in [(False, 'back'), (True, 'front')]:
                    thigh_roots = [n for n in ref_names
                                   if n.startswith('thigh_b_ref')
                                   and n.endswith(side_suffix)
                                   and ('dupli' in n) == is_dupli]
                    if not thigh_roots:
                        thigh_roots = [n for n in ref_names
                                       if n.startswith('thigh_ref')
                                       and n.endswith(side_suffix)
                                       and ('dupli' in n) == is_dupli]

                    if thigh_roots:
                        thigh_roots.sort(key=lambda x: ref_depth.get(x, 0))
                        limb_chain = collect_connected_ref_chain(thigh_roots[0])
                        leg_bones = [n for n in limb_chain if n.startswith('thigh') or n.startswith('leg')]
                        foot_bones = [n for n in limb_chain if n.startswith('foot') or n.startswith('toes')]
                        if leg_bones:
                            arp_chains[f'{leg_prefix}_leg_{side_key}'] = leg_bones
                        if foot_bones:
                            arp_chains[f'{leg_prefix}_foot_{side_key}'] = foot_bones

                    for aux_pfx in FOOT_AUX_PREFIXES:
                        aux_key = aux_pfx.replace('foot_', '')
                        cands = [n for n in ref_names
                                 if n.startswith(aux_pfx) and '_ref' in n
                                 and n.endswith(side_suffix)
                                 and ('dupli' in n) == is_dupli]
                        if cands:
                            cands.sort(key=lambda x: ref_depth.get(x, 0))
                            arp_chains[f'{leg_prefix}_{aux_key}_{side_key}'] = cands

                ear_cands = sorted([n for n in ref_names
                                    if 'ear' in n and '_ref' in n
                                    and n.endswith(side_suffix)],
                                   key=lambda x: ref_depth.get(x, 0))
                if ear_cands:
                    arp_chains[f'ear_{side_key}'] = ear_cands

            log("  --- ARP ref 체인 (조정 후) ---")
            for role, bones in arp_chains.items():
                log(f"  {role:20s}: {' → '.join(bones)}")

        # --- 매핑 생성 ---
        deform_to_ref = {}

        def add_chain_mapping(role_label, preview_bones, target_refs):
            if not preview_bones:
                return
            if not target_refs:
                if 'heel' not in role_label and 'bank' not in role_label:
                    log(f"  [WARN] 역할 '{role_label}' → ARP ref 없음")
                return

            chain_map = map_role_chain(role_label, preview_bones, target_refs)
            deform_to_ref.update(chain_map)

        for role, preview_bones in roles.items():
            if role == 'unmapped':
                continue
            add_chain_mapping(role, preview_bones, arp_chains.get(role, []))

        log(f"  매핑 결과: {len(deform_to_ref)}개")
        for src, ref in deform_to_ref.items():
            log(f"  {src:25s} → {ref}")

        if not deform_to_ref:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.report({'ERROR'}, "매핑 생성 실패")
            return {'CANCELLED'}

        # --- 위치 설정 (같은 Edit 세션에서) ---
        # 원칙: ARP 기본 parent/use_connect 구조를 보존하고 위치만 설정
        # - connected 본: tail만 설정 (head는 부모.tail에 자동 고정)
        # - disconnected 본: head + tail 설정
        # - 하이어라키 깊이 순서(부모→자식)로 처리

        resolved = {}
        for src_name, ref_name in deform_to_ref.items():
            if src_name in preview_positions:
                resolved_value = preview_positions[src_name]
                role_label = preview_role_by_bone.get(src_name, '')
                guide_kind = _detect_guide_kind(role_label, src_name)

                if guide_kind:
                    preview_bone = preview_obj.data.bones.get(src_name)
                    foot_name = preview_bone.parent.name if preview_bone and preview_bone.parent else None
                    guide_side = _detect_guide_side(role_label, foot_name or src_name)

                    if foot_name and _is_default_foot_guide(
                        preview_local_positions,
                        src_name,
                        foot_name,
                        guide_kind,
                        guide_side,
                    ):
                        foot_world = preview_positions.get(foot_name)
                        if foot_world:
                            foot_len = (foot_world[1] - foot_world[0]).length
                            # toe 본 위치 조회
                            toe_world_tail = None
                            foot_bone_preview = preview_obj.data.bones.get(foot_name)
                            if foot_bone_preview:
                                for child in foot_bone_preview.children:
                                    if child.name in preview_positions and child.name != src_name:
                                        child_pos = preview_positions[child.name]
                                        if toe_world_tail is None or child_pos[1].z < toe_world_tail.z:
                                            toe_world_tail = child_pos[1]
                            auto_head, auto_tail = _compute_auto_foot_guide_world(
                                foot_world[0],
                                foot_world[1],
                                guide_kind,
                                guide_side,
                                toe_world_tail=toe_world_tail,
                            )
                            orig_head = resolved_value[0]
                            resolved_value = (auto_head, auto_tail, resolved_value[2])
                            offset = (auto_head - orig_head).length
                            log(f"  {src_name}: 자동 {guide_kind} 보정 (side={guide_side}, "
                                f"foot_len={foot_len:.4f}, offset={offset:.4f})")
                    else:
                        log(f"  {src_name}: {guide_kind} 가이드 사용자 위치 유지")

                resolved[ref_name] = resolved_value

        # --- heel/bank ref 본 위치 설정 (foot ref 기준) ---
        FOOT_AUX_PREFIXES = ['foot_bank', 'foot_heel']
        for role, ref_chain in arp_chains.items():
            if 'heel' not in role and 'bank' not in role:
                continue
            # 대응하는 foot 역할 찾기 (back_heel_l → back_foot_l)
            foot_role = role.replace('_heel_', '_foot_').replace('_bank_', '_foot_')
            foot_refs = arp_chains.get(foot_role, [])
            if not foot_refs:
                continue

            # foot ref 본에서 위치 가져오기
            foot_ref_name = foot_refs[0]  # foot_ref.l 등
            foot_ref_eb = edit_bones.get(foot_ref_name)
            if not foot_ref_eb or foot_ref_name not in resolved:
                continue

            foot_world_head = resolved[foot_ref_name][0]
            foot_world_tail = resolved[foot_ref_name][1]

            # toe ref 본 찾기
            toe_world_tail = None
            if len(foot_refs) > 1:
                toe_ref_name = foot_refs[-1]
                if toe_ref_name in resolved:
                    toe_world_tail = resolved[toe_ref_name][1]

            side = 'r' if role.endswith('_r') else 'l'

            # heel 먼저 계산
            heel_head, heel_tail = _compute_auto_foot_guide_world(
                foot_world_head, foot_world_tail, 'heel', side,
                toe_world_tail=toe_world_tail,
            )

            # forward / lateral 축 계산 (bank 배치용)
            fwd = foot_world_tail - foot_world_head
            fwd.z = 0.0
            if fwd.length < 0.0001:
                fwd = Vector((0.0, 1.0, 0.0))
            fwd.normalize()
            lat = Vector((0.0, 0.0, 1.0)).cross(fwd)
            if lat.length < 0.0001:
                lat = Vector((1.0, 0.0, 0.0))
            else:
                lat.normalize()
            if side == 'r':
                lat.negate()

            foot_length = (foot_world_tail - foot_world_head).length
            toe_length = (toe_world_tail - foot_world_tail).length if toe_world_tail else 0
            total_length = max(foot_length + toe_length, 0.001)
            bank_offset = total_length * 0.50
            bone_len = max(total_length * 0.50, 0.015)

            for aux_ref_name in ref_chain:
                aux_eb = edit_bones.get(aux_ref_name)
                if not aux_eb:
                    continue

                if 'heel' in aux_ref_name:
                    auto_head = heel_head.copy()
                    auto_tail = heel_tail.copy()
                    guide_kind = 'heel'
                elif 'bank_01' in aux_ref_name:
                    # bank_01 = inner (같은 side 방향)
                    auto_head = heel_head + lat * bank_offset
                    auto_head.z = 0.0
                    auto_tail = auto_head + fwd * bone_len
                    auto_tail.z = 0.0
                    guide_kind = 'bank_inner'
                else:
                    # bank_02 = outer (반대 방향)
                    auto_head = heel_head - lat * bank_offset
                    auto_head.z = 0.0
                    auto_tail = auto_head + fwd * bone_len
                    auto_tail.z = 0.0
                    guide_kind = 'bank_outer'

                resolved[aux_ref_name] = (auto_head, auto_tail, 0.0)
                log(f"  {aux_ref_name}: 자동 {guide_kind} 배치 (Z=0, foot={foot_ref_name})")

        # 하이어라키 깊이 계산 → 부모(얕은)부터 자식(깊은) 순서
        def get_depth(bone_name):
            eb = edit_bones.get(bone_name)
            depth = 0
            while eb and eb.parent:
                depth += 1
                eb = eb.parent
            return depth

        sorted_refs = sorted(resolved.keys(), key=get_depth)
        aligned = 0

        def find_connected_descendant_chain(start_ebone):
            """
            현재 ref 본에서 connected 자식 체인을 따라가며
            다음으로 위치가 결정된(resolved) ref 본을 찾는다.

            Returns:
                tuple[list[EditBone], EditBone | None]
                - helpers: start와 next_resolved 사이의 미매핑 connected 본들
                - next_resolved: 다음으로 위치가 결정된 connected 자식 본
            """
            helpers = []
            current = start_ebone
            visited = set()

            while current:
                candidates = [
                    child for child in current.children
                    if child.use_connect
                    and '_ref' in child.name
                    and 'bank' not in child.name
                    and 'heel' not in child.name
                ]
                if not candidates:
                    return helpers, None

                candidates.sort(key=lambda child: ref_depth.get(child.name, 0))
                child = candidates[0]
                if child.name in visited:
                    return helpers, None
                visited.add(child.name)

                if child.name in resolved:
                    return helpers, child

                helpers.append(child)
                current = child

            return helpers, None

        for ref_name in sorted_refs:
            world_head, world_tail, roll = resolved[ref_name]
            ebone = edit_bones.get(ref_name)
            if ebone is None:
                log(f"  '{ref_name}' 미발견 (skip)", "WARN")
                continue

            local_head = arp_matrix_inv @ world_head
            local_tail = arp_matrix_inv @ world_tail
            preview_tail = local_tail.copy()
            tail_source = "프리뷰.tail"

            current_head = ebone.head.copy() if (ebone.use_connect and ebone.parent) else local_head
            helper_chain, next_resolved_child = find_connected_descendant_chain(ebone)
            if next_resolved_child:
                next_head = arp_matrix_inv @ resolved[next_resolved_child.name][0]
                segment_count = len(helper_chain) + 1

                if segment_count == 1:
                    local_tail = next_head
                    tail_source = f"{next_resolved_child.name}.head"
                else:
                    # ARP helper ref(thigh_ref 등)가 끼어 있는 경우
                    # 현재 본 ~ 다음 매핑 본 head 사이를 균등 분할해 helper 체인도 함께 정렬한다.
                    local_tail = current_head.lerp(next_head, 1.0 / segment_count)
                    tail_source = f"{next_resolved_child.name}.head/{segment_count}분할"

                    for idx, helper_eb in enumerate(helper_chain):
                        factor = float(idx + 2) / float(segment_count)
                        helper_tail = current_head.lerp(next_head, factor)
                        helper_eb.tail = helper_tail
                        log(f"  {helper_eb.name}: helper tail 설정 ({next_resolved_child.name}.head/{segment_count}분할)")
            elif helper_chain and ref_name.startswith('foot'):
                # 소스 발 본만 있고 toe 본이 없는 경우:
                # 마지막 소스 본의 tail까지를 ARP foot/toes 체인으로 분할해
                # virtual toe 구간을 만든다.
                segment_count = len(helper_chain) + 1
                source_end = local_tail
                local_tail = current_head.lerp(source_end, 1.0 / segment_count)
                tail_source = f"프리뷰.tail/{segment_count}분할"

                for idx, helper_eb in enumerate(helper_chain):
                    factor = float(idx + 2) / float(segment_count)
                    helper_tail = current_head.lerp(source_end, factor)
                    helper_eb.tail = helper_tail
                    log(f"  {helper_eb.name}: virtual toe tail 설정 (프리뷰.tail/{segment_count}분할)")

            # root_ref: spine 방향, tail을 원래 pelvis.head에 맞춰 head를 뒤로 이동
            if ref_name.startswith('root_ref') and next_resolved_child and next_resolved_child.name in resolved:
                spine_world_tail = resolved[next_resolved_child.name][1]
                spine_local_tail = arp_matrix_inv @ spine_world_tail
                spine_dir = spine_local_tail - current_head
                if spine_dir.length > 0.001:
                    bone_len = max((preview_tail - current_head).length, 0.02)
                    # tail = pelvis.head (spine01 시작점), head = 뒤로 이동
                    local_tail = current_head.copy()
                    local_head = current_head - spine_dir.normalized() * bone_len
                    current_head = local_head
                    tail_source = f"root→spine 방향 (head 후방 이동)"
                else:
                    bone_len = max((preview_tail - current_head).length, 0.02)
                    local_tail = current_head + Vector((0, 0, bone_len))
                    tail_source = "+Z fallback"
            else:
                # 결과 본이 프리뷰 대비 너무 짧으면 프리뷰 tail 사용
                preview_length = (preview_tail - current_head).length
                result_length = (local_tail - current_head).length
                if preview_length > 0.001 and result_length < preview_length * 0.2:
                    local_tail = preview_tail
                    tail_source = "프리뷰.tail (짧은 본 보정)"
                elif result_length < 0.0001:
                    local_tail = current_head + Vector((0, 0.01, 0))

            # ARP 원래 연결 구조 보존
            if ebone.use_connect and ebone.parent:
                # connected 본: head가 부모.tail에 고정 → tail만 설정
                ebone.tail = local_tail
                log(f"  {ref_name}: tail만 설정 ({tail_source}, connected to {ebone.parent.name})")
            else:
                # disconnected 본: head + tail 모두 설정
                ebone.head = local_head
                ebone.tail = local_tail
                log(f"  {ref_name}: head+tail 설정 ({tail_source})")

            ebone.roll = roll
            aligned += 1

        # 진단: 최종 ref 본 상태 로그
        log("=== ref 본 최종 상태 ===")
        for ref_name in sorted_refs:
            eb = edit_bones.get(ref_name)
            if eb:
                h = eb.head
                t = eb.tail
                parent_name = eb.parent.name if eb.parent else "None"
                log(f"  {ref_name}: head=({h.x:.4f},{h.y:.4f},{h.z:.4f}) "
                    f"tail=({t.x:.4f},{t.y:.4f},{t.z:.4f}) "
                    f"connected={eb.use_connect} parent={parent_name}")

        bpy.ops.object.mode_set(mode='OBJECT')
        log(f"ref 본 정렬 완료: {aligned}/{len(resolved)}개")

        # Step 4: match_to_rig (Edit 모드 재진입 없이 바로 실행)
        log("match_to_rig 실행")
        ensure_object_mode()
        select_only(arp_obj)
        try:
            run_arp_operator(bpy.ops.arp.match_to_rig)
        except Exception as e:
            self.report({'ERROR'}, f"match_to_rig 실패: {e}")
            log(f"  match_to_rig 에러: {e}", "ERROR")
            return {'CANCELLED'}

        # Step 5: unmapped cc_ 커스텀 본 추가
        from skeleton_analyzer import read_preview_roles
        roles = read_preview_roles(preview_obj)
        custom_bones = [
            bone_name for bone_name in roles.get('unmapped', [])
            if not bone_name.endswith(GUIDE_SUFFIX_HEEL)
            and not bone_name.endswith(GUIDE_SUFFIX_BANK)
        ]

        if custom_bones:
            log(f"cc_ 커스텀 본 추가: {len(custom_bones)}개")
            ensure_object_mode()
            select_only(arp_obj)
            try:
                created_cc, cc_bone_map = _create_cc_bones_from_preview(
                    arp_obj=arp_obj,
                    preview_obj=preview_obj,
                    preview_positions=preview_positions,
                    custom_bone_names=custom_bones,
                    deform_to_ref=deform_to_ref,
                    log=log,
                )
                log(f"  cc_ 생성 완료: {created_cc}개")

                copied_constraints = _copy_custom_bone_constraints(
                    source_obj=source_obj,
                    arp_obj=arp_obj,
                    custom_bone_names=custom_bones,
                    deform_to_ref=deform_to_ref,
                    log=log,
                )
                if copied_constraints:
                    log(f"  constraint 복제 완료: {copied_constraints}개")
            except Exception as e:
                self.report({'ERROR'}, f"cc_ 커스텀 본 생성 실패: {e}")
                log(f"  cc_ 생성 에러: {traceback.format_exc()}", "ERROR")
                return {'CANCELLED'}
        else:
            cc_bone_map = {}

        # Step 6: 전체 웨이트 전송 (deform 본 + cc_ 본) + Armature modifier 변경
        log("=== 웨이트 전송 ===")
        ensure_object_mode()
        try:
            weight_map = _build_position_weight_map(source_obj, arp_obj, cc_bone_map, log)
            if weight_map:
                transferred = _transfer_all_weights(source_obj, arp_obj, weight_map, log)
                log(f"  전체 weight 전송: {transferred} groups")
            else:
                log("  weight map 비어있음 — 전송 스킵", "WARN")
        except Exception as e:
            log(f"  weight 전송 실패 (무시): {e}", "WARN")
            log(traceback.format_exc(), "WARN")

        self.report({'INFO'}, f"ARP 리그 생성 완료 ({aligned}개 ref 본 정렬)")
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 4 — 리타게팅
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_Retarget(Operator):
    """동적 .bmap 생성 + 애니메이션 리타게팅"""
    bl_idname = "arp_convert.retarget"
    bl_label = "애니메이션 리타게팅"
    bl_description = "Preview 매핑으로 .bmap 자동 생성 후 리타게팅"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                preview_to_analysis, generate_bmap_content,
            )
            from arp_utils import (
                log, ensure_object_mode, select_only,
                run_arp_operator, find_arp_armature,
                ensure_retarget_context,
            )
        except ImportError as e:
            self.report({'ERROR'}, f"모듈 임포트 실패: {e}")
            return {'CANCELLED'}

        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)
        source_obj = bpy.data.objects.get(props.source_armature)
        arp_obj = find_arp_armature()

        if not all([preview_obj, source_obj, arp_obj]):
            self.report({'ERROR'}, "소스/Preview/ARP 아마추어를 모두 찾을 수 없습니다.")
            return {'CANCELLED'}

        ensure_object_mode()

        # 동적 .bmap 생성 (ARP 아마추어에서 실제 컨트롤러 이름 탐색)
        log("동적 .bmap 생성")
        analysis = preview_to_analysis(preview_obj)
        bmap_content = generate_bmap_content(analysis, arp_obj=arp_obj)

        bmap_name = "auto_generated"
        blender_ver = f"{bpy.app.version[0]}.{bpy.app.version[1]}"

        for presets_dir in [
            os.path.join(os.environ.get("APPDATA", ""),
                "Blender Foundation", "Blender", blender_ver,
                "extensions", "user_default", "auto_rig_pro", "remap_presets"),
            os.path.join(os.environ.get("APPDATA", ""),
                "Blender Foundation", "Blender", blender_ver,
                "config", "addons", "auto_rig_pro-master", "remap_presets"),
        ]:
            if os.path.isdir(presets_dir):
                bmap_path = os.path.join(presets_dir, f"{bmap_name}.bmap")
                with open(bmap_path, 'w', encoding='utf-8') as f:
                    f.write(bmap_content)
                log(f".bmap 저장: {bmap_path}")
                break

        # 리타게팅 설정
        log("리타게팅 설정")
        try:
            ensure_retarget_context(source_obj, arp_obj)
            run_arp_operator(bpy.ops.arp.auto_scale)
            ensure_object_mode()
            run_arp_operator(bpy.ops.arp.build_bones_list)

            try:
                run_arp_operator(bpy.ops.arp.import_config_preset, preset_name=bmap_name)
                log(f".bmap 로드 성공: {bmap_name}")
            except Exception as e:
                log(f".bmap 로드 실패: {e}", "WARN")

            run_arp_operator(bpy.ops.arp.redefine_rest_pose, preserve=True)
            run_arp_operator(bpy.ops.arp.save_pose_rest)
            ensure_object_mode()
        except Exception as e:
            self.report({'ERROR'}, f"리타게팅 설정 실패: {e}")
            log(traceback.format_exc(), "ERROR")
            return {'CANCELLED'}

        # 액션별 리타게팅
        log("액션별 리타게팅")
        actions = list(bpy.data.actions)
        success = 0
        fail = 0

        for i, action in enumerate(actions):
            f_start = int(action.frame_range[0])
            f_end = int(action.frame_range[1])
            log(f"  [{i+1}/{len(actions)}] '{action.name}' ({f_start}~{f_end})")

            try:
                if source_obj.animation_data is None:
                    source_obj.animation_data_create()
                source_obj.animation_data.action = action

                ensure_object_mode()
                select_only(arp_obj)
                run_arp_operator(
                    bpy.ops.arp.retarget,
                    frame_start=f_start,
                    frame_end=f_end,
                    fake_user_action=True,
                    interpolation_type='LINEAR',
                )
                success += 1
            except Exception as e:
                fail += 1
                log(f"    실패: {e}", "WARN")

        self.report({'INFO'}, f"리타게팅 완료: {success}/{len(actions)} 성공")
        return {'FINISHED'}


# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: 회귀 테스트
# ═══════════════════════════════════════════════════════════════

class ARPCONV_OT_RunRegression(Operator):
    """Fixture 기반 Preview 회귀 테스트"""
    bl_idname = "arp_convert.run_regression"
    bl_label = "회귀 테스트 실행"
    bl_description = "Fixture JSON으로 역할을 적용하고 BuildRig/Retarget까지 자동 실행"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        _ensure_scripts_path()
        _reload_modules()

        try:
            from arp_utils import log
        except ImportError as e:
            self.report({'ERROR'}, f"모듈 임포트 실패: {e}")
            return {'CANCELLED'}

        props = context.scene.arp_convert_props
        fixture_path = props.regression_fixture.strip()
        if not fixture_path:
            self.report({'ERROR'}, "Fixture JSON 경로를 지정하세요.")
            return {'CANCELLED'}

        started = time.time()
        report = {
            'success': False,
            'fixture_path': '',
            'report_path': '',
            'source_armature': '',
            'preview_armature': '',
            'build_rig': False,
            'retarget': False,
            'role_application': {},
            'warnings': [],
            'elapsed_sec': 0.0,
        }

        try:
            fixture_data = _load_regression_fixture(fixture_path)
            report['fixture_path'] = fixture_data['path']
            log(f"회귀 테스트 fixture 로드: {fixture_data['path']}")

            result = bpy.ops.arp_convert.create_preview()
            if 'FINISHED' not in result:
                raise RuntimeError("Preview 생성 실패")

            preview_obj = bpy.data.objects.get(props.preview_armature)
            source_obj = bpy.data.objects.get(props.source_armature)
            if preview_obj is None or source_obj is None:
                raise RuntimeError("Preview 또는 source armature를 찾을 수 없습니다.")

            report['preview_armature'] = preview_obj.name
            report['source_armature'] = source_obj.name

            role_summary = _apply_fixture_roles(context, preview_obj, fixture_data)
            report['role_application'] = role_summary
            if role_summary['missing_bones']:
                report['warnings'].append(
                    f"fixture bone 미발견: {', '.join(role_summary['missing_bones'])}"
                )
            if role_summary['duplicate_bones']:
                report['warnings'].append(
                    f"중복 role 지정 본 {len(role_summary['duplicate_bones'])}개"
                )

            log(
                "회귀 테스트 역할 적용: "
                f"{role_summary['assigned_count']}개 본, "
                f"가이드 {role_summary['guide_count']}개"
            )

            result = bpy.ops.arp_convert.build_rig()
            if 'FINISHED' not in result:
                raise RuntimeError("BuildRig 실패")
            report['build_rig'] = True

            should_run_retarget = props.regression_run_retarget and fixture_data['run_retarget']
            if should_run_retarget:
                result = bpy.ops.arp_convert.retarget()
                if 'FINISHED' not in result:
                    raise RuntimeError("Retarget 실패")
                report['retarget'] = True

            report['success'] = True
            self.report({'INFO'}, "회귀 테스트 완료")
            return {'FINISHED'}

        except Exception as e:
            log(f"회귀 테스트 실패: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
            self.report({'ERROR'}, f"회귀 테스트 실패: {e}")
            report['warnings'].append(str(e))
            return {'CANCELLED'}

        finally:
            report['elapsed_sec'] = round(time.time() - started, 2)
            report_dir = _resolve_regression_path(props.regression_report_dir.strip())
            if not report_dir:
                report_dir = _default_regression_report_dir()
            os.makedirs(report_dir, exist_ok=True)

            blend_name = os.path.splitext(os.path.basename(bpy.data.filepath or "untitled.blend"))[0]
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f"{blend_name}_{timestamp}.json")
            report['report_path'] = report_path
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            try:
                from arp_utils import log
                log(f"회귀 테스트 리포트 저장: {report_path}")
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════
# UI 패널
# ═══════════════════════════════════════════════════════════════

class ARPCONV_PT_MainPanel(Panel):
    """ARP 리그 변환 메인 패널"""
    bl_label = "ARP 리그 변환"
    bl_idname = "ARPCONV_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "ARP Convert"

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props

        # Step 1: 분석 + Preview
        box = layout.box()
        box.label(text="Step 1: 분석", icon='VIEWZOOM')
        if props.source_armature:
            box.label(text=f"소스: {props.source_armature}")
        row = box.row()
        row.scale_y = 1.5
        row.operator("arp_convert.create_preview", icon='ARMATURE_DATA')

        if not props.is_analyzed:
            layout.separator()
            layout.label(text="소스 아마추어를 선택하고 분석을 실행하세요.", icon='INFO')
            return

        # 신뢰도
        layout.label(text=f"신뢰도: {props.confidence:.0%}", icon='CHECKMARK')
        if props.preview_armature:
            layout.label(text=f"Preview: {props.preview_armature}")

        layout.separator()

        # Step 2: 역할 수정
        box = layout.box()
        box.label(text="Step 2: 역할 수정", icon='BONE_DATA')
        box.label(text="본 선택 후 역할을 변경하세요:")

        # 역할 버튼 — 카테고리별 정리
        # Body
        sub = box.column(align=True)
        sub.label(text="Body:")
        grid = sub.grid_flow(columns=3, align=True)
        for role_id in ['root', 'spine', 'neck', 'head', 'tail']:
            op = grid.operator("arp_convert.set_role", text=role_id.capitalize())
            op.role = role_id

        # Legs
        sub = box.column(align=True)
        sub.label(text="Legs:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ['back_leg_l', 'back_leg_r', 'front_leg_l', 'front_leg_r']:
            label = role_id.replace('_', ' ').title().replace('Back Leg', 'BLeg').replace('Front Leg', 'FLeg')
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Feet (★)
        sub = box.column(align=True)
        sub.label(text="Feet (★ bank/heel 자동 생성):")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ['back_foot_l', 'back_foot_r', 'front_foot_l', 'front_foot_r']:
            label = role_id.replace('_', ' ').title().replace('Back Foot', 'BFoot').replace('Front Foot', 'FFoot')
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Head features
        sub = box.column(align=True)
        sub.label(text="Head:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ['ear_l', 'ear_r']:
            label = {'ear_l': 'Ear L', 'ear_r': 'Ear R'}[role_id]
            op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # Unmapped (cc_ custom bones)
        row = box.row()
        op = row.operator("arp_convert.set_role", text="Unmapped (cc_)")
        op.role = 'unmapped'

        # 현재 선택된 본의 역할 표시
        if context.active_object and context.active_object.type == 'ARMATURE':
            active_bone = context.active_bone
            if active_bone:
                pbone = context.active_object.pose.bones.get(active_bone.name)
                if pbone:
                    _ensure_scripts_path()
                    from skeleton_analyzer import ROLE_PROP_KEY
                    current_role = pbone.get(ROLE_PROP_KEY, 'unmapped')
                    box.separator()
                    box.label(text=f"선택: {active_bone.name}", icon='BONE_DATA')
                    box.label(text=f"현재 역할: {current_role}")

        layout.separator()

        # Step 3: 리그 생성
        box = layout.box()
        box.label(text="Step 3: 적용", icon='PLAY')
        col = box.column(align=True)
        col.scale_y = 1.3
        col.operator("arp_convert.build_rig", icon='MOD_ARMATURE')
        col.operator("arp_convert.retarget", icon='ACTION')

        layout.separator()

        box = layout.box()
        box.label(text="Regression", icon='FILE_TEXT')
        box.prop(props, "regression_fixture", text="Fixture")
        box.prop(props, "regression_report_dir", text="Report Dir")
        box.prop(props, "regression_run_retarget")
        row = box.row()
        row.scale_y = 1.2
        row.operator("arp_convert.run_regression", icon='CHECKMARK')


# ═══════════════════════════════════════════════════════════════
# 등록
# ═══════════════════════════════════════════════════════════════

classes = [
    ARPCONV_Props,
    ARPCONV_OT_CreatePreview,
    ARPCONV_OT_SetRole,
    ARPCONV_OT_BuildRig,
    ARPCONV_OT_Retarget,
    ARPCONV_OT_RunRegression,
    ARPCONV_PT_MainPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.arp_convert_props = PointerProperty(type=ARPCONV_Props)


def unregister():
    del bpy.types.Scene.arp_convert_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

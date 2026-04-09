"""
arp_convert_addon에서 분리한 웨이트 전송 로직.

소스 아마추어의 vertex group 웨이트를 ARP 리그로 전송하는 함수들.
Build Rig의 Step 7(전체 웨이트 전송) 단계에서 사용된다.
"""

import bpy
from mathutils import Vector


def _closest_point_on_segment(point, seg_a, seg_b):
    """점에서 선분(seg_a→seg_b)까지 가장 가까운 점을 반환."""
    ab = seg_b - seg_a
    ab_sq = ab.dot(ab)
    if ab_sq < 1e-12:
        return seg_a.copy()
    t = max(0.0, min(1.0, (point - seg_a).dot(ab) / ab_sq))
    return seg_a + ab * t


def _compute_proximity_ratios(vertex_co, bone_infos):
    """정점 좌표와 본 정보로 proximity 기반 ratio 계산.

    각 본의 closest point까지 거리의 역수 비율로 분배.

    Args:
        vertex_co: Vector — 정점의 월드 좌표
        bone_infos: [(name, head_vec, tail_vec), ...]

    Returns:
        [(name, ratio), ...] — ratio 합 = 1.0
    """
    inv_distances = []
    for name, head, tail in bone_infos:
        closest = _closest_point_on_segment(vertex_co, head, tail)
        dist = max((vertex_co - closest).length, 0.0001)
        inv_distances.append((name, 1.0 / dist))

    total = sum(d for _, d in inv_distances)
    return [(name, d / total) for name, d in inv_distances]


def _build_position_weight_map(
    source_obj,
    arp_obj,
    cc_bone_map,
    roles,
    preview_role_by_bone,
    deform_to_ref,
    arp_chains,
    log,
):
    """Preview role metadata를 반영해 source -> ARP deform weight map을 생성한다."""
    from arp_build_helpers import (
        _build_arp_deform_metadata,
        _build_ref_metadata,
        _build_source_deform_metadata,
    )
    from weight_transfer_rules import build_weight_map

    ref_meta = _build_ref_metadata(arp_obj, arp_chains)
    arp_meta = _build_arp_deform_metadata(arp_obj, ref_meta, log)
    if not arp_meta:
        return {}

    source_meta = _build_source_deform_metadata(source_obj, preview_role_by_bone)
    aux_count = sum(1 for meta in arp_meta.values() if meta.get("is_auxiliary"))
    log(f"  Deform 매핑 후보: {len(arp_meta)}개 (heel/bank 제외 {aux_count}개)")

    weight_map = build_weight_map(
        source_meta=source_meta,
        arp_meta=arp_meta,
        cc_bone_map=cc_bone_map,
        roles=roles,
        deform_to_ref=deform_to_ref,
        arp_chains=arp_chains,
        log=log,
    )

    for src_name, mappings in weight_map.items():
        if src_name in cc_bone_map:
            log(f"  cc_ 매핑: {src_name} -> {mappings[0][0]}", "DEBUG")
            continue
        if len(mappings) == 1:
            log(f"  weight 매핑: {src_name} -> {mappings[0][0]}", "DEBUG")
            continue
        split_str = " + ".join(f"{arp_name}({ratio:.0%})" for arp_name, ratio in mappings)
        log(f"  weight 분할: {src_name} -> {split_str}", "DEBUG")

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

        # ARP vertex group 초기화 (소스==타겟인 커스텀 본은 제외)
        all_sources = set(weight_map.keys())
        all_targets = set()
        for mappings in weight_map.values():
            for arp_name, _ in mappings:
                all_targets.add(arp_name)
        for arp_name in all_targets:
            if arp_name in all_sources:
                continue  # 소스와 이름이 같은 VG는 삭제하면 안됨
            existing = mesh_obj.vertex_groups.get(arp_name)
            if existing:
                mesh_obj.vertex_groups.remove(existing)

        # stretch/twist proximity 분배를 위한 본 위치 캐시
        arp_mw = arp_obj.matrix_world
        bone_pos_cache = {}
        for b in arp_obj.data.bones:
            bone_pos_cache[b.name] = (arp_mw @ b.head_local, arp_mw @ b.tail_local)

        mesh_mw = mesh_obj.matrix_world

        for src_name, mappings in weight_map.items():
            src_vg = mesh_obj.vertex_groups.get(src_name)
            if not src_vg:
                continue

            # stretch/twist 포함 여부 판단
            has_twist_stretch = len(mappings) > 1 and any(
                "twist" in name or "stretch" in name for name, _ in mappings
            )

            if has_twist_stretch:
                # proximity 기반 per-vertex ratio
                bone_infos = []
                for arp_name, _ in mappings:
                    pos = bone_pos_cache.get(arp_name)
                    if pos:
                        bone_infos.append((arp_name, pos[0], pos[1]))

                # ARP VG 준비
                arp_vgs = {}
                for arp_name, _ in mappings:
                    vg = mesh_obj.vertex_groups.get(arp_name)
                    if not vg:
                        vg = mesh_obj.vertex_groups.new(name=arp_name)
                    arp_vgs[arp_name] = vg

                if bone_infos:
                    for v in mesh_obj.data.vertices:
                        src_weight = 0.0
                        for g in v.groups:
                            if g.group == src_vg.index:
                                src_weight = g.weight
                                break
                        if src_weight < 0.0001:
                            continue

                        vert_co = mesh_mw @ v.co
                        prox_ratios = _compute_proximity_ratios(vert_co, bone_infos)
                        for arp_name, ratio in prox_ratios:
                            if arp_name in arp_vgs:
                                arp_vgs[arp_name].add([v.index], src_weight * ratio, "REPLACE")
            else:
                # 기존 고정 ratio 방식
                for arp_name, ratio in mappings:
                    arp_vg = mesh_obj.vertex_groups.get(arp_name)
                    if not arp_vg:
                        arp_vg = mesh_obj.vertex_groups.new(name=arp_name)

                    for v in mesh_obj.data.vertices:
                        for g in v.groups:
                            if g.group == src_vg.index:
                                arp_vg.add([v.index], g.weight * ratio, "REPLACE")
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
            if mod.type == "ARMATURE" and mod.object == source_obj:
                mod.object = arp_obj
                log(f"  Armature modifier 변경: {source_obj.name} → {arp_obj.name}")
                break

    log(f"  weight 전송 완료: {total_groups} groups, {len(meshes)} meshes")
    return total_groups


def _map_source_bone_to_target_bone(source_bone_name, custom_bone_names, deform_to_ref):
    from arp_cc_bones import _make_cc_bone_name

    if source_bone_name in custom_bone_names:
        return _make_cc_bone_name(source_bone_name)
    return deform_to_ref.get(source_bone_name)

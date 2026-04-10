"""
arp_convert_addon에서 분리한 Build Rig 내부 헬퍼.

ARP ref 메타데이터 구성, 체인 개수 조정, source-to-ref deform 매핑,
primary deform bone 탐색, cc parent 해결 등 Build Rig에서만 쓰이는
헬퍼 함수들을 담는다.
"""

import bpy


def _get_arp_set_functions():
    """ARP 내부 set_spine/set_neck/set_tail/set_ears 함수를 import."""
    try:
        from bl_ext.user_default.auto_rig_pro.src.auto_rig import (
            set_ears,
            set_neck,
            set_spine,
            set_tail,
        )

        return set_spine, set_neck, set_tail, set_ears
    except ImportError:
        return None, None, None, None


def _select_edit_bone(arp_obj, bone_name):
    """Edit Mode에서 특정 본을 선택하고 active로 설정."""
    edit_bones = arp_obj.data.edit_bones
    bpy.ops.armature.select_all(action="DESELECT")
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
        ("spine", set_spine, "count", "spine_01_ref"),
        ("neck", set_neck, "neck_count", "neck_ref"),
        ("tail", set_tail, "tail_count", "tail_00_ref"),
    ]

    for chain_role, set_func, param_name, ref_search_key in adjustments:
        source_bones = roles.get(chain_role, [])
        arp_refs = arp_chains.get(chain_role, [])

        # ARP에 ref 본이 없으면 조정 불가 (이미 0)
        if not arp_refs:
            continue

        src_count = len(source_bones)
        arp_count = len(arp_refs)

        if src_count == arp_count:
            continue

        # spine/neck은 최소 1본 필요 (ARP dog preset 제약) — 0이면 skip
        if src_count == 0 and chain_role in ("spine", "neck"):
            log(f"  [체인 매칭] {chain_role}: 소스 없음 — 최소 1본 필요, 기본값 유지")
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
            call_count = src_count + 1 if chain_role == "spine" else src_count
            kwargs = {param_name: call_count}
            set_func(**kwargs)
            log(f"    → ARP {chain_role} 개수를 {call_count}으로 변경 완료 (소스 {src_count}본)")
            adjusted = True
        except Exception as e:
            log(f"    [ERROR] {chain_role} 개수 변경 실패: {e}")

    # ear: L/R 개별 호출
    if set_ears:
        for side_key, side_arg in [("ear_l", ".l"), ("ear_r", ".r")]:
            source_bones = roles.get(side_key, [])
            arp_refs = arp_chains.get(side_key, [])

            # ARP ref 본이 없으면 조정 불가
            if not arp_refs:
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


def _get_bone_side(name):
    """본 이름에서 사이드 추출 (.l/_L → L, .r/_R → R, .x/기타 → X)"""
    if name.endswith(".l"):
        return "L"
    if name.endswith(".r"):
        return "R"
    if name.endswith(".x"):
        return "X"
    if name.endswith("_L") or name.endswith("_l"):
        return "L"
    if name.endswith("_R") or name.endswith("_r"):
        return "R"
    return "X"


def _vector_to_tuple(vec):
    return (float(vec.x), float(vec.y), float(vec.z))


def _is_auxiliary_arp_deform(name):
    lowered = name.lower()
    return "heel" in lowered or "bank" in lowered


def _classify_arp_family_kind(name):
    lowered = name.lower()
    if "twist" in lowered:
        return "twist"
    if "stretch" in lowered:
        return "stretch"
    if lowered.startswith("toes") or "toes" in lowered:
        return "toe"
    return "main"


def _build_ref_metadata(arp_obj, arp_chains):
    arp_matrix = arp_obj.matrix_world
    ref_to_role = {}
    ref_to_index = {}
    ref_meta = {}

    for role_name, ref_names in (arp_chains or {}).items():
        for index, ref_name in enumerate(ref_names):
            ref_to_role[ref_name] = role_name
            ref_to_index[ref_name] = index

    for bone in arp_obj.data.bones:
        if "_ref" not in bone.name:
            continue
        head_w = arp_matrix @ bone.head_local
        tail_w = arp_matrix @ bone.tail_local
        ref_meta[bone.name] = {
            "name": bone.name,
            "head": _vector_to_tuple(head_w),
            "tail": _vector_to_tuple(tail_w),
            "mid": _vector_to_tuple((head_w + tail_w) * 0.5),
            "length": (tail_w - head_w).length,
            "side": _get_bone_side(bone.name),
            "role": ref_to_role.get(bone.name, ""),
            "segment_index": ref_to_index.get(bone.name),
        }

    return ref_meta


def _find_nearest_ref_name(position, side, ref_meta):
    best_name = None
    best_distance = float("inf")

    for ref_name, meta in ref_meta.items():
        ref_side = meta.get("side")
        if side != "X" and ref_side != side:
            continue
        ref_pos = meta.get("mid") or meta.get("head")
        if not ref_pos:
            continue
        distance = (
            (position[0] - ref_pos[0]) ** 2
            + (position[1] - ref_pos[1]) ** 2
            + (position[2] - ref_pos[2]) ** 2
        )
        if distance < best_distance:
            best_distance = distance
            best_name = ref_name

    if best_name is None and side != "X":
        return _find_nearest_ref_name(position, "X", ref_meta)
    return best_name


def _build_arp_deform_metadata(arp_obj, ref_meta, log):
    deform_col = arp_obj.data.collections_all.get("Deform")
    if not deform_col:
        log("  Deform 컬렉션 미발견", "ERROR")
        return {}

    arp_matrix = arp_obj.matrix_world
    arp_meta = {}

    for bone in arp_obj.data.bones:
        if deform_col not in bone.collections.values():
            continue
        if "_ref" in bone.name:
            continue

        head_w = arp_matrix @ bone.head_local
        tail_w = arp_matrix @ bone.tail_local
        side = _get_bone_side(bone.name)
        owner_ref = _find_nearest_ref_name(
            _vector_to_tuple((head_w + tail_w) * 0.5),
            side,
            ref_meta,
        )
        owner_meta = ref_meta.get(owner_ref, {})

        arp_meta[bone.name] = {
            "name": bone.name,
            "head": _vector_to_tuple(head_w),
            "tail": _vector_to_tuple(tail_w),
            "length": (tail_w - head_w).length,
            "side": side,
            "family_kind": _classify_arp_family_kind(bone.name),
            "owner_ref": owner_ref,
            "owner_role": owner_meta.get("role", ""),
            "segment_index": owner_meta.get("segment_index"),
            "is_auxiliary": _is_auxiliary_arp_deform(bone.name),
        }

    return arp_meta


def _build_source_deform_metadata(source_obj, preview_role_by_bone):
    src_matrix = source_obj.matrix_world
    source_meta = {}

    for bone in source_obj.data.bones:
        if not bone.use_deform:
            continue
        head_w = src_matrix @ bone.head_local
        tail_w = src_matrix @ bone.tail_local
        source_meta[bone.name] = {
            "name": bone.name,
            "head": _vector_to_tuple(head_w),
            "tail": _vector_to_tuple(tail_w),
            "length": (tail_w - head_w).length,
            "side": _get_bone_side(bone.name),
            "role": preview_role_by_bone.get(bone.name, ""),
        }

    return source_meta


def _distance_sq(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _build_primary_deform_bones_by_ref(arp_obj, arp_chains, log):
    ref_meta = _build_ref_metadata(arp_obj, arp_chains)
    arp_meta = _build_arp_deform_metadata(arp_obj, ref_meta, log)
    primary_by_ref = {}

    for ref_name, ref_info in ref_meta.items():
        main_candidates = [
            meta
            for meta in arp_meta.values()
            if meta.get("owner_ref") == ref_name
            and meta.get("family_kind") == "main"
            and not meta.get("is_auxiliary")
        ]
        if not main_candidates:
            continue

        ref_anchor = ref_info.get("head") or ref_info.get("mid")
        main_candidates.sort(
            key=lambda meta: (
                _distance_sq(meta.get("head") or meta.get("tail"), ref_anchor),
                meta.get("name", ""),
            )
        )
        primary_by_ref[ref_name] = main_candidates[0]["name"]

    return primary_by_ref


def _resolve_root_deform_parent_name(arp_obj, primary_deform_by_ref):
    for candidate_name in [
        primary_deform_by_ref.get("root_ref.x"),
        "root.x",
        "root",
        "root_ref.x",
    ]:
        if candidate_name and arp_obj.data.bones.get(candidate_name):
            return candidate_name
    return "root_ref.x"


def _build_cc_parent_targets(arp_obj, arp_chains, deform_to_ref, log):
    primary_deform_by_ref = _build_primary_deform_bones_by_ref(arp_obj, arp_chains, log)
    source_to_deform_parent = {}

    for source_bone_name, ref_name in (deform_to_ref or {}).items():
        deform_parent_name = primary_deform_by_ref.get(ref_name)
        if deform_parent_name:
            source_to_deform_parent[source_bone_name] = deform_parent_name

    root_parent_name = _resolve_root_deform_parent_name(arp_obj, primary_deform_by_ref)
    return source_to_deform_parent, root_parent_name


def _resolve_cc_parent_name(
    source_bone_name,
    preview_hierarchy,
    custom_bone_names,
    source_to_deform_parent,
    root_parent_name,
):
    from arp_cc_bones import _make_cc_bone_name
    from arp_ops_preview import _iter_preview_ancestors

    for ancestor_name in _iter_preview_ancestors(source_bone_name, preview_hierarchy):
        if ancestor_name in custom_bone_names:
            return _make_cc_bone_name(ancestor_name)

        deform_parent_name = source_to_deform_parent.get(ancestor_name)
        if deform_parent_name:
            return deform_parent_name

    return root_parent_name

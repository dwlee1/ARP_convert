"""
Role-aware ARP deform weight transfer helpers.

This module is intentionally Blender-free so the weight routing math can be
unit tested with plain Python metadata dictionaries.
"""

from math import sqrt

LEG_ROLE_PREFIXES = ("back_leg_", "front_leg_")
FOOT_ROLE_PREFIXES = ("back_foot_", "front_foot_")


def build_weight_map(
    source_meta,
    arp_meta,
    cc_bone_map,
    roles,
    deform_to_ref,
    arp_chains,
    log=None,
):
    """
    Build {source_bone: [(target_bone, ratio), ...]} using role-aware rules.

    Args:
        source_meta: {source_name: metadata}
        arp_meta: {arp_name: metadata}
        cc_bone_map: {source_name: cc_target_name}
        roles: preview roles dict
        deform_to_ref: {source_name: arp_ref_name}
        arp_chains: {role_name: [arp_ref_names]}
        log: optional callable(str)
    """
    weight_map = {}
    reserved_targets = set()
    fallback_sources = {}

    non_aux_arp = {name: meta for name, meta in arp_meta.items() if not meta.get("is_auxiliary")}
    arp_by_owner_ref = {}
    for name, meta in non_aux_arp.items():
        owner_ref = meta.get("owner_ref")
        if owner_ref:
            arp_by_owner_ref.setdefault(owner_ref, []).append(name)

    role_source_names = {}
    for role_name, role_bones in (roles or {}).items():
        role_source_names[role_name] = [
            bone_name
            for bone_name in role_bones
            if bone_name in source_meta and bone_name not in cc_bone_map
        ]

    for role_name, role_bones in role_source_names.items():
        if _is_leg_role(role_name):
            for src_name in role_bones:
                mapping, reason = _resolve_leg_mapping(
                    src_name,
                    source_meta,
                    non_aux_arp,
                    arp_by_owner_ref,
                    deform_to_ref,
                )
                if mapping:
                    weight_map[src_name] = mapping
                    reserved_targets.update(target for target, _ in mapping)
                else:
                    fallback_sources[src_name] = reason
        elif _is_foot_role(role_name):
            foot_results, foot_fallbacks = _resolve_foot_role_mapping(
                role_name,
                role_bones,
                source_meta,
                non_aux_arp,
                arp_by_owner_ref,
                arp_chains,
            )
            for src_name, mapping in foot_results.items():
                weight_map[src_name] = mapping
                reserved_targets.update(target for target, _ in mapping)
            fallback_sources.update(foot_fallbacks)

    generic_sources = [
        src_name
        for src_name in source_meta
        if src_name not in cc_bone_map
        and src_name not in weight_map
        and not _is_leg_role(source_meta[src_name].get("role"))
        and not _is_foot_role(source_meta[src_name].get("role"))
    ]
    generic_sources.extend(
        src_name for src_name in fallback_sources if src_name not in generic_sources
    )

    generic_candidates = {
        name: meta for name, meta in non_aux_arp.items() if name not in reserved_targets
    }
    generic_map = _build_generic_weight_map(
        generic_sources,
        source_meta,
        generic_candidates,
    )
    weight_map.update(generic_map)

    if log:
        for src_name, reason in fallback_sources.items():
            if src_name in generic_map:
                log(f"  role-aware fallback: {src_name} ({reason})")

    for src_name, cc_name in cc_bone_map.items():
        weight_map[src_name] = [(cc_name, 1.0)]

    return weight_map


def _resolve_leg_mapping(
    src_name,
    source_meta,
    arp_meta,
    arp_by_owner_ref,
    deform_to_ref,
):
    mapped_ref = (deform_to_ref or {}).get(src_name)
    if not mapped_ref:
        return None, "missing mapped ref"

    family_names = list(arp_by_owner_ref.get(mapped_ref, []))
    if not family_names:
        return None, f"no ARP family for {mapped_ref}"

    primary_names = [name for name in family_names if arp_meta[name].get("family_kind") == "main"]
    if not primary_names:
        return None, f"no primary deform owner for {mapped_ref}"

    src_side = source_meta[src_name].get("side")
    primary_names = [
        name for name in primary_names if arp_meta[name].get("side") == src_side
    ] or primary_names
    primary_name = min(
        primary_names,
        key=lambda name: _distance(
            source_meta[src_name].get("head"),
            arp_meta[name].get("head"),
        ),
    )

    owned_names = [
        name
        for name in family_names
        if arp_meta[name].get("side") == src_side
        and arp_meta[name].get("family_kind") in {"twist", "stretch"}
    ]
    family = [primary_name] + [name for name in owned_names if name != primary_name]
    return _split_by_lengths(family, arp_meta), None


def _resolve_foot_role_mapping(
    role_name,
    role_bones,
    source_meta,
    arp_meta,
    arp_by_owner_ref,
    arp_chains,
):
    results = {}
    fallbacks = {}
    if not role_bones:
        return results, fallbacks

    foot_refs = list((arp_chains or {}).get(role_name, []))
    if len(foot_refs) >= 2:
        foot_ref = foot_refs[0]
        toe_ref = foot_refs[1]
    else:
        for src_name in role_bones:
            fallbacks[src_name] = f"missing foot/toe refs for {role_name} (got {len(foot_refs)})"
        return results, fallbacks

    foot_family = _collect_family_members(arp_by_owner_ref, arp_meta, foot_ref)
    toe_family = _collect_family_members(arp_by_owner_ref, arp_meta, toe_ref)

    if len(role_bones) == 2:
        proximal_name = role_bones[0]
        distal_name = role_bones[-1]

        if foot_family:
            results[proximal_name] = _split_by_lengths(foot_family, arp_meta)
        else:
            fallbacks[proximal_name] = f"missing foot family for {foot_ref}"

        if toe_family:
            results[distal_name] = _split_by_lengths(toe_family, arp_meta)
        else:
            fallbacks[distal_name] = f"missing toe family for {toe_ref}"
        return results, fallbacks

    if len(role_bones) == 1:
        src_name = role_bones[0]
        if not foot_family or not toe_family:
            missing_name = foot_ref if not foot_family else toe_ref
            missing_kind = "foot" if not foot_family else "toe"
            fallbacks[src_name] = f"missing {missing_kind} family for {missing_name}"
            return results, fallbacks

        results[src_name] = _split_across_families(
            [foot_family, toe_family],
            arp_meta,
        )
        return results, fallbacks

    for src_name in role_bones:
        fallbacks[src_name] = f"unexpected foot source count ({len(role_bones)})"
    return results, fallbacks


def _collect_family_members(arp_by_owner_ref, arp_meta, owner_ref):
    return [
        name
        for name in arp_by_owner_ref.get(owner_ref, [])
        if arp_meta[name].get("family_kind") in {"main", "twist", "stretch", "toe"}
    ]


def _build_generic_weight_map(source_names, source_meta, arp_meta):
    if not source_names or not arp_meta:
        return {}

    match_pairs = []
    for src_name in source_names:
        src_info = source_meta.get(src_name)
        if not src_info:
            continue
        src_side = src_info.get("side")
        src_head = src_info.get("head")
        for cand_name, cand_info in arp_meta.items():
            if cand_info.get("side") != src_side:
                continue
            match_pairs.append(
                (
                    _distance(src_head, cand_info.get("head")),
                    src_name,
                    cand_name,
                )
            )

    match_pairs.sort(key=lambda item: (item[0], item[1], item[2]))

    initial_map = {}
    claimed_sources = set()
    claimed_targets = set()
    for _, src_name, cand_name in match_pairs:
        if src_name in claimed_sources or cand_name in claimed_targets:
            continue
        initial_map[src_name] = cand_name
        claimed_sources.add(src_name)
        claimed_targets.add(cand_name)

    src_to_targets = {src_name: [cand_name] for src_name, cand_name in initial_map.items()}
    initial_map_inv = {cand_name: src_name for src_name, cand_name in initial_map.items()}

    for orphan_name in [name for name in arp_meta if name not in claimed_targets]:
        orphan_side = arp_meta[orphan_name].get("side")
        best_claimed = None
        best_distance = float("inf")
        for claimed_name in claimed_targets:
            if arp_meta[claimed_name].get("side") != orphan_side:
                continue
            distance = _distance(
                arp_meta[orphan_name].get("head"),
                arp_meta[claimed_name].get("head"),
            )
            if distance < best_distance:
                best_distance = distance
                best_claimed = claimed_name
        if best_claimed and best_claimed in initial_map_inv:
            owner_src = initial_map_inv[best_claimed]
            src_to_targets.setdefault(owner_src, []).append(orphan_name)

    weight_map = {}
    for src_name, target_names in src_to_targets.items():
        weight_map[src_name] = _split_by_lengths(target_names, arp_meta)
    return weight_map


def _split_across_families(families, arp_meta):
    family_lengths = [sum(_safe_length(arp_meta[name]) for name in family) for family in families]
    total_length = sum(family_lengths)
    if total_length <= 0.0:
        flat_names = [name for family in families for name in family]
        return _split_by_lengths(flat_names, arp_meta)

    mappings = []
    for family, family_length in zip(families, family_lengths):
        if not family or family_length <= 0.0:
            continue
        family_ratio = family_length / total_length
        family_split = _split_by_lengths(family, arp_meta)
        for bone_name, ratio in family_split:
            mappings.append((bone_name, family_ratio * ratio))
    return _normalize_ratios(mappings)


def _split_by_lengths(names, meta_lookup):
    unique_names = []
    seen_names = set()
    for name in names:
        if name in meta_lookup and name not in seen_names:
            unique_names.append(name)
            seen_names.add(name)
    if not unique_names:
        return []

    total_length = sum(_safe_length(meta_lookup[name]) for name in unique_names)
    if total_length <= 0.0:
        ratio = 1.0 / len(unique_names)
        return [(name, ratio) for name in unique_names]

    return [(name, _safe_length(meta_lookup[name]) / total_length) for name in unique_names]


def _normalize_ratios(mappings):
    total_ratio = sum(ratio for _, ratio in mappings)
    if total_ratio <= 0.0:
        return mappings
    return [(name, ratio / total_ratio) for name, ratio in mappings]


def _safe_length(meta):
    return max(float(meta.get("length", 0.0) or 0.0), 0.00001)


def _distance(a, b):
    if a is None or b is None:
        return float("inf")
    ax, ay, az = a
    bx, by, bz = b
    return sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)


def _is_leg_role(role_name):
    return bool(role_name) and role_name.startswith(LEG_ROLE_PREFIXES)


def _is_foot_role(role_name):
    return bool(role_name) and role_name.startswith(FOOT_ROLE_PREFIXES)

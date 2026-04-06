"""
mcp_bridge에서 분리한 순수 데이터 가공 로직.

bpy 의존 없이 단위 테스트 가능. mcp_bridge의 각 함수는
(1) bpy 호출로 raw 데이터 수집 → (2) 이 모듈의 헬퍼로 가공 → (3) JSON 출력
구조를 가진다.
"""


def filter_pairs_by_role(bone_pairs, target_to_role, role_filter=None):
    """bone_pairs를 역할별로 필터링한다.

    Args:
        bone_pairs: [(src, tgt, is_custom), ...] 리스트 (3-tuple 또는 list).
        target_to_role: {target_bone_name: role_or_None} flat 매핑.
            호출부가 discover_arp_ctrl_map() 결과({role: [ctrls,...]})를
            {ctrl: role} 형태로 뒤집어서 전달해야 한다.
        role_filter: None이면 전체. 문자열이면 정확 매칭. list/set이면 포함 매칭.

    Returns:
        [{"source": str, "target": str, "is_custom": bool, "role": str|None}, ...]
        target이 target_to_role에 없으면 role=None으로 반환.
    """
    if role_filter is None:
        filter_set = None
    elif isinstance(role_filter, str):
        filter_set = {role_filter}
    else:
        filter_set = set(role_filter)

    result = []
    for pair in bone_pairs:
        src = pair[0]
        tgt = pair[1]
        is_custom = bool(pair[2]) if len(pair) > 2 else False
        role = target_to_role.get(tgt)
        if filter_set is not None and role not in filter_set:
            continue
        result.append({"source": src, "target": tgt, "is_custom": is_custom, "role": role})
    return result


def compute_position_stats(distances):
    """거리(float) 리스트에서 min/max/mean/count를 집계한다.

    빈 리스트는 {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'count': 0}을 반환한다.
    """
    if not distances:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "count": 0}
    return {
        "min": min(distances),
        "max": max(distances),
        "mean": sum(distances) / len(distances),
        "count": len(distances),
    }


def compute_rotation_stats(angles_deg):
    """회전 오차(deg) 리스트에서 min/max/mean/count를 집계한다."""
    return compute_position_stats(angles_deg)


def summarize_pair_results(
    pair_results,
    *,
    top_n=5,
    position_threshold=0.001,
    rotation_threshold_deg=1.0,
):
    """pair 결과를 정렬/요약해 요약 모드 응답에 맞는 dict로 반환한다."""
    sorted_pairs = sorted(
        pair_results,
        key=lambda r: (
            float(r.get("max_err", 0.0)),
            float(r.get("rot_max_deg", 0.0)),
        ),
        reverse=True,
    )
    top_offenders = [
        {
            "src": r.get("src"),
            "arp": r.get("arp"),
            "max_err": float(r.get("max_err", 0.0)),
            "mean_err": float(r.get("mean_err", 0.0)),
            "rot_max_deg": float(r.get("rot_max_deg", 0.0)),
            "rot_mean_deg": float(r.get("rot_mean_deg", 0.0)),
        }
        for r in sorted_pairs[:top_n]
    ]
    pass_count = sum(
        1
        for r in pair_results
        if float(r.get("max_err", 0.0)) < position_threshold
        and float(r.get("rot_max_deg", 0.0)) < rotation_threshold_deg
    )
    return {
        "top_offenders": top_offenders,
        "pass_count": pass_count,
    }


def format_comparison_report(pair_results):
    """프레임 비교 결과 리스트를 읽기 쉬운 멀티라인 문자열로 변환한다.

    입력: [{"src": str, "arp": str, "max_err": float, "mean_err": float, ...}, ...]
    빈 입력은 "no pairs compared"를 반환한다.
    """
    if not pair_results:
        return "no pairs compared"
    include_rotation = any("rot_max_deg" in row or "rot_mean_deg" in row for row in pair_results)
    header = f"{'src_bone':<25} -> {'arp_bone':<30} | {'max_err':>9} | {'mean_err':>9}"
    if include_rotation:
        header += f" | {'rot_max':>9} | {'rot_mean':>9}"
    lines = [header, "-" * len(header)]
    for r in pair_results:
        src = str(r.get("src", ""))
        arp = str(r.get("arp", ""))
        try:
            max_err_val = float(r.get("max_err", 0.0))
            max_err_str = f"{max_err_val:>9.5f}"
        except (TypeError, ValueError):
            max_err_str = f"{'N/A':>9}"
        try:
            mean_err_val = float(r.get("mean_err", 0.0))
            mean_err_str = f"{mean_err_val:>9.5f}"
        except (TypeError, ValueError):
            mean_err_str = f"{'N/A':>9}"
        line = f"{src:<25} -> {arp:<30} | {max_err_str} | {mean_err_str}"
        if include_rotation:
            try:
                rot_max_val = float(r.get("rot_max_deg", 0.0))
                rot_max_str = f"{rot_max_val:>9.3f}"
            except (TypeError, ValueError):
                rot_max_str = f"{'N/A':>9}"
            try:
                rot_mean_val = float(r.get("rot_mean_deg", 0.0))
                rot_mean_str = f"{rot_mean_val:>9.3f}"
            except (TypeError, ValueError):
                rot_mean_str = f"{'N/A':>9}"
            line += f" | {rot_max_str} | {rot_mean_str}"
        lines.append(line)
    return "\n".join(lines)


def match_bone_names(bone_names, pattern):
    """본 이름 리스트에서 정규식(re.search) 매칭되는 항목을 정렬 반환한다.

    pattern이 None이면 전체를 정렬 반환한다. 잘못된 정규식은 re.error 전파.
    """
    import re

    names = sorted(bone_names)
    if pattern is None:
        return names
    regex = re.compile(pattern)
    return [n for n in names if regex.search(n)]

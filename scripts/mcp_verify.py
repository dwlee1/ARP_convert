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
        target_to_role: {target_bone_name: role_or_None} 매핑 (호출부에서 구성).
        role_filter: None이면 전체. 문자열이면 정확 매칭. list/set이면 포함 매칭.

    Returns:
        [{"source": str, "target": str, "is_custom": bool, "role": str|None}, ...]
    """
    raise NotImplementedError


def compute_position_stats(distances):
    """거리(float) 리스트에서 min/max/mean/count를 집계한다.

    빈 리스트는 {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'count': 0}을 반환한다.
    """
    raise NotImplementedError


def format_comparison_report(pair_results):
    """프레임 비교 결과 리스트를 읽기 쉬운 멀티라인 문자열로 변환한다.

    입력: [{"src": str, "arp": str, "max_err": float, "mean_err": float, ...}, ...]
    빈 입력은 "no pairs compared"를 반환한다.
    """
    raise NotImplementedError


def match_bone_names(bone_names, pattern):
    """본 이름 리스트에서 정규식(re.search) 매칭되는 항목을 정렬 반환한다.

    pattern이 None이면 전체를 정렬 반환한다. 잘못된 정규식은 re.error 전파.
    """
    raise NotImplementedError

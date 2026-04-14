"""controller auto-size 규칙 테스트."""

import math

import pytest

import arp_build_helpers as ab

PREVIEW_POSITIONS = {
    "spine01": ((0.0, 0.0, 0.0), (0.0, 0.30, 0.0), 0.0),
    "spine02": ((0.0, 0.30, 0.0), (0.0, 0.55, 0.0), 0.0),
    "neck01": ((0.0, 0.55, 0.0), (0.0, 0.68, 0.0), 0.0),
    "neck02": ((0.0, 0.68, 0.0), (0.0, 0.80, 0.0), 0.0),
    "head": ((0.0, 0.80, 0.0), (0.0, 1.00, 0.0), 0.0),
    "ear.L.01": ((0.02, 0.92, 0.0), (0.04, 1.04, 0.0), 0.0),
    "ear.L.02": ((0.04, 1.04, 0.0), (0.05, 1.14, 0.0), 0.0),
    "foot_back_l": ((0.12, -0.20, 0.0), (0.16, -0.34, 0.0), 0.0),
    "toe_back_l": ((0.16, -0.34, 0.0), (0.22, -0.42, 0.0), 0.0),
}

_ROLES = {
    "spine": ["spine01", "spine02"],
    "neck": ["neck01", "neck02"],
    "head": ["head"],
    "ear_l": ["ear.L.01", "ear.L.02"],
    "back_foot_l": ["foot_back_l", "toe_back_l"],
}

_CTRL_MAP = {
    "spine": ["c_spine_01.x", "c_spine_02.x"],
    "neck": ["c_subneck_01.x", "c_neck.x"],
    "head": ["c_head.x"],
    "ear_l": ["c_ear_01.l", "c_ear_02.l"],
    "back_foot_l": ["c_foot_fk.l", "c_toes_fk.l"],
}


def _bone_len(bone_name):
    head, tail = PREVIEW_POSITIONS[bone_name][:2]
    return math.dist(head, tail)


def test_fallback_when_no_arp_length():
    """arp_bone_lengths 없을 때 target_size를 scale로 직접 사용."""
    roles = {"spine": ["spine01"], "head": ["head"]}
    ctrl_map = {"head": ["c_head.x"]}

    spine_total = _bone_len("spine01")
    target = spine_total * ab.BODY_FRACTION

    targets = ab._build_controller_size_targets_per_bone(roles, ctrl_map, PREVIEW_POSITIONS, {})

    assert targets["c_head.x"] == pytest.approx(ab._clamp_controller_size(target), rel=1e-6)


def test_body_reference_uniform_absolute_size():
    """모든 컨트롤러가 동일한 절대 표시 크기(target)를 가진다.
    표시 크기 = ctrl_bone_length * scale = ctrl_bone_length * (target / ctrl_bone_length) = target
    """
    spine_total = _bone_len("spine01") + _bone_len("spine02")
    target = spine_total * ab.BODY_FRACTION

    arp_bone_lengths = {
        "c_spine_01.x": 0.5,
        "c_spine_02.x": 0.2,
        "c_head.x": 0.8,
        "c_ear_01.l": 0.1,
    }
    roles = {"spine": ["spine01", "spine02"]}
    ctrl_map = {
        "spine": ["c_spine_01.x", "c_spine_02.x"],
        "head": ["c_head.x"],
        "ear_l": ["c_ear_01.l"],
    }

    targets = ab._build_controller_size_targets_per_bone(
        roles, ctrl_map, PREVIEW_POSITIONS, arp_bone_lengths
    )

    assert targets["c_spine_01.x"] == pytest.approx(target / 0.5, rel=1e-6)
    assert targets["c_spine_02.x"] == pytest.approx(target / 0.2, rel=1e-6)
    assert targets["c_head.x"] == pytest.approx(target / 0.8, rel=1e-6)
    assert targets["c_ear_01.l"] == pytest.approx(target / 0.1, rel=1e-6)

    # 핵심 불변성: 모든 컨트롤러의 절대 표시 크기가 target으로 수렴
    for ctrl_name, scale in targets.items():
        ctrl_len = arp_bone_lengths[ctrl_name]
        assert ctrl_len * scale == pytest.approx(target, rel=1e-4), (
            f"{ctrl_name}: absolute size {ctrl_len * scale:.6f} != target {target:.6f}"
        )


def test_skips_unsupported_roles():
    """지원하지 않는 역할은 targets에 포함되지 않는다."""
    roles = {"spine": ["spine01"], "unmapped": ["spine01"]}
    ctrl_map = {"spine": ["c_spine_01.x"], "unmapped": ["c_custom.x"]}
    arp_bone_lengths = {"c_spine_01.x": 1.0, "c_custom.x": 1.0}

    targets = ab._build_controller_size_targets_per_bone(
        roles, ctrl_map, PREVIEW_POSITIONS, arp_bone_lengths
    )

    assert "c_spine_01.x" in targets
    assert "c_custom.x" not in targets


def test_clamp_controller_size_enforces_bounds():
    assert ab._clamp_controller_size(0.001, 0.03, 0.6) == 0.03
    assert ab._clamp_controller_size(0.25, 0.03, 0.6) == 0.25
    assert ab._clamp_controller_size(1.20, 0.03, 0.6) == 0.6


def test_compute_body_reference_uses_spine():
    """spine 역할이 있으면 spine 합계를 반환."""
    roles = {"spine": ["spine01", "spine02"], "head": ["head"]}
    ref = ab._compute_body_reference(roles, PREVIEW_POSITIONS)
    expected = _bone_len("spine01") + _bone_len("spine02")
    assert ref == pytest.approx(expected, rel=1e-6)


def test_compute_body_reference_fallback_avg_when_no_spine():
    """spine 역할 없으면 할당된 모든 본의 평균 길이를 반환."""
    roles = {"head": ["head"], "neck": ["neck01"]}
    ref = ab._compute_body_reference(roles, PREVIEW_POSITIONS)
    expected = (_bone_len("head") + _bone_len("neck01")) / 2
    assert ref == pytest.approx(expected, rel=1e-6)


def test_compute_body_reference_fallback_constant_when_empty():
    """할당된 본이 아예 없으면 AUTO_SIZE_FALLBACK 반환."""
    ref = ab._compute_body_reference({}, PREVIEW_POSITIONS)
    assert ref == pytest.approx(ab.AUTO_SIZE_FALLBACK, rel=1e-6)


def test_compute_body_reference_spine_zero_length_falls_back():
    """spine 본 이름이 있지만 preview_positions에 없으면 평균 fallback으로 내려간다."""
    roles = {"spine": ["ghost_bone"], "head": ["head"]}
    ref = ab._compute_body_reference(roles, PREVIEW_POSITIONS)
    # ghost_bone은 PREVIEW_POSITIONS에 없어 길이 0 → spine total=0 → head 길이 평균
    assert ref == pytest.approx(_bone_len("head"), rel=1e-6)

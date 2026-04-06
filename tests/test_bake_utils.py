"""F12 베이크 유틸리티 단위 테스트 (Blender 불필요)."""

import json
import math

from arp_utils import (
    _make_compatible_euler_angles,
    deserialize_bone_pairs,
    serialize_bone_pairs,
)


class TestBonePairsSerialization:
    def test_roundtrip(self):
        pairs = [
            ("thigh_L", "c_thigh_fk.l", False),
            ("eye_L", "eye_L", True),
        ]
        serialized = serialize_bone_pairs(pairs)
        result = deserialize_bone_pairs(serialized)
        assert result == pairs

    def test_serialize_returns_json_string(self):
        pairs = [("spine01", "c_spine_01.x", False)]
        serialized = serialize_bone_pairs(pairs)
        parsed = json.loads(serialized)
        assert isinstance(parsed, list)
        assert parsed[0] == ["spine01", "c_spine_01.x", False]

    def test_deserialize_empty(self):
        result = deserialize_bone_pairs("[]")
        assert result == []

    def test_deserialize_converts_lists_to_tuples(self):
        raw = json.dumps([["a", "b", True]])
        result = deserialize_bone_pairs(raw)
        assert result == [("a", "b", True)]


class TestCompatibleEulerAngles:
    def test_returns_current_values_without_previous(self):
        result = _make_compatible_euler_angles((0.1, -0.2, 0.3), None)
        assert result == (0.1, -0.2, 0.3)

    def test_wraps_positive_pi_boundary(self):
        previous = (0.0, math.radians(179.0), 0.0)
        current = (0.0, math.radians(-179.0), 0.0)
        result = _make_compatible_euler_angles(current, previous)
        assert abs(result[1] - math.radians(181.0)) < 1e-6

    def test_wraps_negative_pi_boundary(self):
        previous = (0.0, math.radians(-179.0), 0.0)
        current = (0.0, math.radians(179.0), 0.0)
        result = _make_compatible_euler_angles(current, previous)
        assert abs(result[1] - math.radians(-181.0)) < 1e-6

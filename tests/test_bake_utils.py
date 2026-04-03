"""F12 베이크 유틸리티 단위 테스트 (Blender 불필요)."""

import json

from arp_utils import deserialize_bone_pairs, serialize_bone_pairs


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

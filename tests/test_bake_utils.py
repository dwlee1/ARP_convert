"""F12 리타겟 위임 유틸리티 단위 테스트 (Blender 불필요)."""

import json

import arp_utils
from arp_utils import (
    _POLE_CTRL_PATTERN,
    _classify_ctrl,
    _override_bones_map,
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


class TestClassifyCtrl:
    def test_root_master_converts_to_root(self):
        result = _classify_ctrl("c_root_master.x", False)
        assert result["ctrl"] == "c_root.x"
        assert result["set_as_root"] is True
        assert result["location"] is True
        assert result["ik"] is False

    def test_root_direct_keeps_set_as_root(self):
        result = _classify_ctrl("c_root.x", False)
        assert result["ctrl"] == "c_root.x"
        assert result["set_as_root"] is True
        assert result["location"] is True
        assert result["ik"] is False

    def test_traj_is_location_set_as_root(self):
        result = _classify_ctrl("c_traj", False)
        assert result["ctrl"] == "c_traj"
        assert result["set_as_root"] is True
        assert result["location"] is True
        assert result["ik"] is False

    def test_foot_ik_is_ik_mode(self):
        result = _classify_ctrl("c_foot_ik.l", False)
        assert result["ctrl"] == "c_foot_ik.l"
        assert result["ik"] is True
        assert result["location"] is False
        assert result["set_as_root"] is False

    def test_foot_ik_dupli_is_ik_mode(self):
        result = _classify_ctrl("c_foot_ik_dupli_001.r", False)
        assert result["ik"] is True
        assert result["location"] is False

    def test_hand_ik_is_ik_mode(self):
        result = _classify_ctrl("c_hand_ik.l", False)
        assert result["ik"] is True
        assert result["location"] is False

    def test_spine_is_ik_worldspace(self):
        result = _classify_ctrl("c_spine_01.x", False)
        assert result["ctrl"] == "c_spine_01.x"
        assert result["location"] is False
        assert result["ik"] is True
        assert result["set_as_root"] is False

    def test_thigh_b_is_ik_worldspace(self):
        result = _classify_ctrl("c_thigh_b.l", False)
        assert result["location"] is False
        assert result["ik"] is True

    def test_custom_bone_uses_location_not_ik(self):
        result = _classify_ctrl("DEF-eye_L", True)
        assert result["location"] is True
        assert result["ik"] is False
        assert result["set_as_root"] is False

    def test_non_custom_bone_still_uses_ik(self):
        result = _classify_ctrl("c_some_ctrl.x", False)
        assert result["ik"] is True
        assert result["location"] is False

    def test_tail_is_ik_worldspace(self):
        result = _classify_ctrl("c_tail_01.x", False)
        assert result["location"] is False
        assert result["ik"] is True

    def test_head_is_ik_worldspace(self):
        result = _classify_ctrl("c_head.x", False)
        assert result["location"] is False
        assert result["ik"] is True


class TestPoleFiltering:
    def test_leg_pole_matches(self):
        assert _POLE_CTRL_PATTERN.match("c_leg_pole.l")
        assert _POLE_CTRL_PATTERN.match("c_leg_pole.r")

    def test_leg_pole_dupli_matches(self):
        assert _POLE_CTRL_PATTERN.match("c_leg_pole_dupli_001.l")
        assert _POLE_CTRL_PATTERN.match("c_leg_pole_dupli_001.r")

    def test_arm_pole_matches(self):
        assert _POLE_CTRL_PATTERN.match("c_arm_pole.l")

    def test_non_pole_does_not_match(self):
        assert not _POLE_CTRL_PATTERN.match("c_foot_ik.l")
        assert not _POLE_CTRL_PATTERN.match("c_thigh_b.l")
        assert not _POLE_CTRL_PATTERN.match("c_spine_01.x")


class DummyBonesMapEntry:
    def __init__(self, source_bone, name=""):
        self.source_bone = source_bone
        self.name = name
        self.location = False
        self.ik = False
        self.set_as_root = False


class DummyScene:
    def __init__(self, entries, bones_map_index=0):
        self.bones_map_v2 = entries
        self.bones_map_index = bones_map_index
        self.arp_remap_allow_root_update = True


class TestOverrideBonesMap:
    def test_traj_wins_single_root_slot(self):
        entries = [
            DummyBonesMapEntry("DEF-pelvis"),
            DummyBonesMapEntry("DEF-root"),
        ]
        scene = DummyScene(entries, bones_map_index=0)
        arp_utils.bpy.context.scene = scene

        _override_bones_map(
            [
                ("DEF-pelvis", "c_root.x", False),
                ("DEF-root", "c_traj", False),
            ]
        )

        assert entries[0].name == "c_root.x"
        assert entries[0].set_as_root is False
        assert entries[1].name == "c_traj"
        assert entries[1].set_as_root is True
        assert scene.bones_map_index == 1

    def test_root_becomes_root_when_traj_absent(self):
        entries = [
            DummyBonesMapEntry("DEF-pelvis"),
        ]
        scene = DummyScene(entries, bones_map_index=0)
        arp_utils.bpy.context.scene = scene

        _override_bones_map(
            [
                ("DEF-pelvis", "c_root.x", False),
            ]
        )

        assert entries[0].name == "c_root.x"
        assert entries[0].set_as_root is True
        assert scene.bones_map_index == 0

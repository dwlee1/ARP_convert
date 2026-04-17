"""Tests for tools/fbx_preprocess.py — Phase 2 후보 A pure helpers."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import fbx_preprocess as pre

# ──────────────────────────────────────────────────────────────────────
# A-1: 컨트롤러 본 식별 + 제거 계획
# ──────────────────────────────────────────────────────────────────────


class TestIsControllerBone:
    def test_fk_suffix_uppercase(self):
        assert pre.is_controller_bone("chest_FK")
        assert pre.is_controller_bone("spine01_FK")

    def test_nomove_suffix(self):
        assert pre.is_controller_bone("chest_nomove")

    def test_ik_suffix(self):
        assert pre.is_controller_bone("hand_IK")

    def test_ctrl_suffix(self):
        assert pre.is_controller_bone("head_ctrl")

    def test_pole_suffix_with_blender_side(self):
        assert pre.is_controller_bone("leg_pole.l")
        assert pre.is_controller_bone("leg_pole.r")

    def test_pole_suffix_with_unity_side(self):
        assert pre.is_controller_bone("leg_pole_L")
        assert pre.is_controller_bone("leg_pole_R")

    def test_normal_bones_are_not_controllers(self):
        assert not pre.is_controller_bone("head")
        assert not pre.is_controller_bone("spine01")
        assert not pre.is_controller_bone("eye_L")
        assert not pre.is_controller_bone("DEF-pelvis")
        assert not pre.is_controller_bone("foot_L")  # _L 자체는 side, controller 아님


class TestPlanControllerRemoval:
    def test_simple_chain_reparents_child_to_root(self):
        bones = {
            "root": {"parent": None},
            "ctrl_FK": {"parent": "root"},
            "child": {"parent": "ctrl_FK"},
        }
        plan = pre.plan_controller_removal(bones)
        assert plan["remove"] == ["ctrl_FK"]
        assert plan["reparent"] == {"child": "root"}

    def test_nested_controllers_reparent_to_first_deform_ancestor(self):
        bones = {
            "root": {"parent": None},
            "c1_FK": {"parent": "root"},
            "c2_nomove": {"parent": "c1_FK"},
            "child": {"parent": "c2_nomove"},
        }
        plan = pre.plan_controller_removal(bones)
        assert set(plan["remove"]) == {"c1_FK", "c2_nomove"}
        assert plan["reparent"] == {"child": "root"}

    def test_rabbit_fk_chain_with_head_underneath(self):
        """rabbit 실측: spine01_FK → chest_FK → chest_nomove → head."""
        bones = {
            "root": {"parent": None},
            "center": {"parent": "root"},
            "spine01_FK": {"parent": "center"},
            "chest_FK": {"parent": "spine01_FK"},
            "chest_nomove": {"parent": "chest_FK"},
            "head": {"parent": "chest_nomove"},
            "eye_L": {"parent": "head"},
        }
        plan = pre.plan_controller_removal(bones)
        assert set(plan["remove"]) == {"spine01_FK", "chest_FK", "chest_nomove"}
        # head가 center로 reparent (가장 가까운 비-컨트롤러 조상)
        assert plan["reparent"] == {"head": "center"}
        # eye_L은 head 자식이고 head는 그대로 유지되므로 reparent 안 함
        assert "eye_L" not in plan["reparent"]

    def test_no_controllers_means_empty_plan(self):
        bones = {"root": {"parent": None}, "child": {"parent": "root"}}
        plan = pre.plan_controller_removal(bones)
        assert plan["remove"] == []
        assert plan["reparent"] == {}

    def test_controller_at_root_makes_children_orphan(self):
        """컨트롤러 본이 root이고 그 자식이 있으면 자식은 None(top-level)으로."""
        bones = {
            "root_FK": {"parent": None},
            "child": {"parent": "root_FK"},
        }
        plan = pre.plan_controller_removal(bones)
        assert plan["remove"] == ["root_FK"]
        assert plan["reparent"] == {"child": None}


class TestMirrorReparent:
    """B-1: 컨트롤러의 mirror deform 본이 있으면 climb 대신 mirror로 reparent."""

    def test_chest_nomove_reparents_head_to_chest_when_chest_exists(self):
        """rabbit 핵심 케이스: chest 존재 시 head → chest (center가 아님)."""
        bones = {
            "root": {"parent": None},
            "center": {"parent": "root"},
            "spine01": {"parent": "center"},
            "chest": {"parent": "spine01"},
            "spine01_FK": {"parent": "center"},
            "chest_FK": {"parent": "spine01_FK"},
            "chest_nomove": {"parent": "chest_FK"},
            "head": {"parent": "chest_nomove"},
        }
        plan = pre.plan_controller_removal(bones)
        assert plan["reparent"] == {"head": "chest"}

    def test_no_mirror_falls_back_to_ancestor_climb(self):
        """mirror 본이 없으면 기존 동작(비-컨트롤러 조상으로 climb) 유지."""
        bones = {
            "root": {"parent": None},
            "ctrl_FK": {"parent": "root"},
            "child": {"parent": "ctrl_FK"},
        }
        plan = pre.plan_controller_removal(bones)
        assert plan["reparent"] == {"child": "root"}

    def test_mirror_preserves_side_suffix(self):
        """`leg_pole.l` → mirror = `leg.l` (side suffix 보존)."""
        bones = {
            "root": {"parent": None},
            "leg.l": {"parent": "root"},
            "leg_pole.l": {"parent": "root"},
            "child": {"parent": "leg_pole.l"},
        }
        plan = pre.plan_controller_removal(bones)
        assert plan["reparent"] == {"child": "leg.l"}

    def test_mirror_with_unity_side_suffix(self):
        """`hand_IK_L` → mirror = `hand_L`."""
        bones = {
            "root": {"parent": None},
            "hand_L": {"parent": "root"},
            "hand_IK_L": {"parent": "root"},
            "child": {"parent": "hand_IK_L"},
        }
        plan = pre.plan_controller_removal(bones)
        assert plan["reparent"] == {"child": "hand_L"}

    def test_mirror_target_must_be_non_controller(self):
        """mirror 후보가 다른 컨트롤러면 사용하지 않고 climb."""
        bones = {
            "root": {"parent": None},
            "chest_FK": {
                "parent": "root"
            },  # mirror 후보 'chest' = 컨트롤러 아님이지만 본 자체 없음
            "head": {"parent": "chest_FK"},
        }
        plan = pre.plan_controller_removal(bones)
        # chest 본 없음 → climb to root
        assert plan["reparent"] == {"head": "root"}


# ──────────────────────────────────────────────────────────────────────
# A-2: 고아 본 감지 (parent=None인데 primary root가 아닌 본)
# ──────────────────────────────────────────────────────────────────────


class TestFindOrphanBones:
    def test_single_root_has_no_orphans(self):
        bones = {
            "root": {"parent": None},
            "child": {"parent": "root"},
        }
        assert pre.find_orphan_bones(bones) == []

    def test_secondary_root_named_root_wins_as_primary(self):
        """이름이 'root'인 본이 있으면 그게 primary, 다른 parent=None은 orphan."""
        bones = {
            "root": {"parent": None},
            "Food": {"parent": None},  # rabbit 실측: 고아 본 (오타)
            "center": {"parent": "root"},
        }
        assert pre.find_orphan_bones(bones) == ["Food"]

    def test_largest_subtree_wins_when_no_root_named(self):
        """이름 힌트 없으면 자손 가장 많은 본이 primary."""
        bones = {
            "Hips": {"parent": None},
            "spine": {"parent": "Hips"},
            "chest": {"parent": "spine"},
            "Stray": {"parent": None},
        }
        assert pre.find_orphan_bones(bones) == ["Stray"]

    def test_only_one_top_level_bone_no_orphan(self):
        bones = {"root": {"parent": None}}
        assert pre.find_orphan_bones(bones) == []


# ──────────────────────────────────────────────────────────────────────
# A-3: leaf 본 tail 길이 정규화
# ──────────────────────────────────────────────────────────────────────


class TestComputeLeafTailShrink:
    def test_leaf_with_same_length_as_parent_gets_shrunk(self):
        """rabbit 실측: eye_L length=0.3049 == head length=0.3049."""
        bones = {
            "head": {"parent": "chest", "length": 0.3049},
            "chest": {"parent": "root", "length": 0.1989},
            "root": {"parent": None, "length": 0.5},
            "eye_L": {"parent": "head", "length": 0.3049},
            "mouth": {"parent": "head", "length": 0.3049},
        }
        result = pre.compute_leaf_tail_shrink(bones, ratio=0.1)
        # eye_L, mouth만 shrink. head는 children 있으므로 leaf 아님
        assert set(result.keys()) == {"eye_L", "mouth"}
        # 새 길이 = parent length * ratio = 0.3049 * 0.1
        assert result["eye_L"] == pytest_almost(0.3049 * 0.1)
        assert result["mouth"] == pytest_almost(0.3049 * 0.1)

    def test_leaf_with_different_length_kept(self):
        """leaf지만 parent와 길이 다르면 그대로 둔다 (정상적으로 export된 leaf)."""
        bones = {
            "root": {"parent": None, "length": 1.0},
            "child": {"parent": "root", "length": 0.5},  # leaf, but length != parent
        }
        assert pre.compute_leaf_tail_shrink(bones, ratio=0.1) == {}

    def test_non_leaf_never_shrunk(self):
        bones = {
            "root": {"parent": None, "length": 1.0},
            "mid": {"parent": "root", "length": 1.0},  # 길이 같지만 자식 있음
            "leaf": {"parent": "mid", "length": 0.3},
        }
        assert pre.compute_leaf_tail_shrink(bones, ratio=0.1) == {}

    def test_root_leaf_alone_kept(self):
        """root이면서 leaf이면 parent 없으니 비교 불가 → 변경 안 함."""
        bones = {"root": {"parent": None, "length": 1.0}}
        assert pre.compute_leaf_tail_shrink(bones, ratio=0.1) == {}

    def test_tolerance_for_floating_point_compare(self):
        """길이 비교는 tolerance 허용 (FBX float 정밀도)."""
        bones = {
            "head": {"parent": None, "length": 0.3049},
            "leaf": {"parent": "head", "length": 0.3049000001},
        }
        result = pre.compute_leaf_tail_shrink(bones, ratio=0.1)
        assert "leaf" in result


def pytest_almost(value, tol=1e-6):
    """간단한 float 비교 헬퍼 (pytest.approx 대체)."""
    import pytest

    return pytest.approx(value, abs=tol)

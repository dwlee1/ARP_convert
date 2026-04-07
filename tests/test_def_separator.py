"""DEF 본 분리 모듈 단위 테스트.

resolve_def_parents는 순수 함수로 Blender 없이 테스트 가능.
create_def_bones는 Blender API 의존이므로 여기서는 테스트하지 않는다.
"""

import sys
from pathlib import Path

import pytest

# scripts/ 경로 추가
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


# arp_def_separator는 bpy를 top-level import하므로 mock 필요
@pytest.fixture(autouse=True)
def _mock_blender(monkeypatch):
    """Blender 모듈 mock으로 import 가능하게."""
    import types

    # bpy mock
    bpy_mock = types.ModuleType("bpy")
    bpy_mock.ops = types.SimpleNamespace()
    bpy_mock.types = types.SimpleNamespace()
    bpy_mock.data = types.SimpleNamespace()
    bpy_mock.context = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "bpy", bpy_mock)

    # bpy.props mock
    bpy_props = types.ModuleType("bpy.props")
    monkeypatch.setitem(sys.modules, "bpy.props", bpy_props)

    # mathutils mock
    mathutils_mock = types.ModuleType("mathutils")

    class MockVector:
        def __init__(self, *args):
            pass

    mathutils_mock.Vector = MockVector
    monkeypatch.setitem(sys.modules, "mathutils", mathutils_mock)

    # arp_utils mock (log 등)
    arp_utils_mock = types.ModuleType("arp_utils")
    arp_utils_mock.log = lambda *a, **k: None
    arp_utils_mock.ensure_object_mode = lambda: None
    arp_utils_mock.select_only = lambda *a: None
    arp_utils_mock.BAKE_PAIRS_KEY = "arpconv_bone_pairs"
    arp_utils_mock.find_arp_armature = lambda: None
    arp_utils_mock.run_arp_operator = lambda *a, **k: None
    arp_utils_mock.serialize_bone_pairs = lambda x: str(x)
    monkeypatch.setitem(sys.modules, "arp_utils", arp_utils_mock)

    # 이미 로드된 모듈 제거 (재import 강제)
    for mod in list(sys.modules):
        if mod.startswith("arp_def_separator"):
            del sys.modules[mod]


def _import_resolve():
    from arp_def_separator import DEF_PREFIX, resolve_def_parents

    return DEF_PREFIX, resolve_def_parents


# ═══════════════════════════════════════════════════════════════
# 테스트 픽스처: 여우 리그 기준 역할 맵
# ═══════════════════════════════════════════════════════════════

FOX_ROLES = {
    "root": ["Pelvis"],
    "spine": ["Spine01", "Spine02", "Spine03"],
    "neck": ["Neck"],
    "head": ["Head"],
    "back_leg_l": ["BackThigh_L", "BackShin_L", "BackAnkle_L"],
    "back_leg_r": ["BackThigh_R", "BackShin_R", "BackAnkle_R"],
    "back_foot_l": ["BackFoot_L", "BackToe_L"],
    "back_foot_r": ["BackFoot_R", "BackToe_R"],
    "front_leg_l": ["FrontShoulder_L", "FrontArm_L", "FrontForearm_L"],
    "front_leg_r": ["FrontShoulder_R", "FrontArm_R", "FrontForearm_R"],
    "front_foot_l": ["FrontFoot_L"],
    "front_foot_r": ["FrontFoot_R"],
    "ear_l": ["Ear01_L", "Ear02_L"],
    "ear_r": ["Ear01_R", "Ear02_R"],
    "tail": ["Tail01", "Tail02", "Tail03", "Tail04"],
    "unmapped": ["Eye_L", "Eye_R", "Jaw"],
}


class TestResolveDEFParents:
    """resolve_def_parents 순수 함수 테스트."""

    def test_root_has_no_parent(self):
        _prefix, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Pelvis"] is None

    def test_spine_first_bone_parent_is_root(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Spine01"] == f"{DEF_PREFIX}Pelvis"

    def test_spine_chain_order(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Spine02"] == f"{DEF_PREFIX}Spine01"
        assert parents["Spine03"] == f"{DEF_PREFIX}Spine02"

    def test_neck_parent_is_last_spine(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Neck"] == f"{DEF_PREFIX}Spine03"

    def test_head_parent_is_last_neck(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Head"] == f"{DEF_PREFIX}Neck"

    def test_tail_first_bone_parent_is_root(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Tail01"] == f"{DEF_PREFIX}Pelvis"

    def test_tail_chain_order(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Tail02"] == f"{DEF_PREFIX}Tail01"
        assert parents["Tail03"] == f"{DEF_PREFIX}Tail02"
        assert parents["Tail04"] == f"{DEF_PREFIX}Tail03"

    def test_back_leg_first_parent_is_root(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["BackThigh_L"] == f"{DEF_PREFIX}Pelvis"
        assert parents["BackThigh_R"] == f"{DEF_PREFIX}Pelvis"

    def test_back_leg_chain(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["BackShin_L"] == f"{DEF_PREFIX}BackThigh_L"
        assert parents["BackAnkle_L"] == f"{DEF_PREFIX}BackShin_L"

    def test_front_leg_first_parent_is_last_spine(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["FrontShoulder_L"] == f"{DEF_PREFIX}Spine03"
        assert parents["FrontShoulder_R"] == f"{DEF_PREFIX}Spine03"

    def test_back_foot_parent_is_last_leg(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["BackFoot_L"] == f"{DEF_PREFIX}BackAnkle_L"
        assert parents["BackToe_L"] == f"{DEF_PREFIX}BackFoot_L"

    def test_front_foot_parent_is_last_front_leg(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["FrontFoot_L"] == f"{DEF_PREFIX}FrontForearm_L"

    def test_ear_parent_is_head(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Ear01_L"] == f"{DEF_PREFIX}Head"
        assert parents["Ear01_R"] == f"{DEF_PREFIX}Head"

    def test_ear_chain_order(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert parents["Ear02_L"] == f"{DEF_PREFIX}Ear01_L"

    def test_unmapped_not_in_parents(self):
        """unmapped 본(eye, jaw 등)은 DEF 계층에 포함되지 않는다."""
        _, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        assert "Eye_L" not in parents
        assert "Eye_R" not in parents
        assert "Jaw" not in parents

    def test_total_bone_count(self):
        """unmapped 제외 모든 역할 본이 parents에 포함된다."""
        _, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents(FOX_ROLES)
        expected = sum(len(bones) for role, bones in FOX_ROLES.items() if role != "unmapped")
        assert len(parents) == expected


class TestResolveDEFParentsMinimal:
    """최소 역할 맵으로 엣지 케이스 테스트."""

    def test_root_only(self):
        _, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents({"root": ["Root"]})
        assert parents == {"Root": None}

    def test_no_neck(self):
        """neck 없으면 head가 spine 마지막에 붙는다."""
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        roles = {
            "root": ["Root"],
            "spine": ["Spine01"],
            "head": ["Head"],
        }
        parents = resolve_def_parents(roles)
        assert parents["Head"] == f"{DEF_PREFIX}Spine01"

    def test_empty_roles(self):
        _, resolve_def_parents = _import_resolve()
        parents = resolve_def_parents({})
        assert parents == {}

    def test_single_spine(self):
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        roles = {
            "root": ["Root"],
            "spine": ["Spine"],
        }
        parents = resolve_def_parents(roles)
        assert parents["Spine"] == f"{DEF_PREFIX}Root"

    def test_multi_neck(self):
        """neck 2개면 체인으로 이어진다."""
        DEF_PREFIX, resolve_def_parents = _import_resolve()
        roles = {
            "root": ["Root"],
            "spine": ["Spine"],
            "neck": ["Neck01", "Neck02"],
            "head": ["Head"],
        }
        parents = resolve_def_parents(roles)
        assert parents["Neck01"] == f"{DEF_PREFIX}Spine"
        assert parents["Neck02"] == f"{DEF_PREFIX}Neck01"
        assert parents["Head"] == f"{DEF_PREFIX}Neck02"


class TestDEFPrefix:
    """DEF_PREFIX 상수 테스트."""

    def test_prefix_value(self):
        DEF_PREFIX, _ = _import_resolve()
        assert DEF_PREFIX == "DEF-"

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "unity_migration"

import build_migration_inventory as bmi


def test_parse_meta_guid_extracts_top_level_guid():
    meta_path = FIXTURE_DIR / "rabbit_animation.fbx.meta"
    assert bmi.parse_meta_guid(meta_path) == "f01ef593d9cf73a4e94a2ab37b4745c1"


def test_parse_meta_guid_returns_none_if_missing(tmp_path):
    bad_meta = tmp_path / "no_guid.meta"
    bad_meta.write_text("fileFormatVersion: 2\n", encoding="utf-8")
    assert bmi.parse_meta_guid(bad_meta) is None


def test_parse_meta_clip_names_extracts_ordered_list():
    meta_path = FIXTURE_DIR / "rabbit_animation.fbx.meta"
    clips = bmi.parse_meta_clip_names(meta_path)
    assert clips == ["Rabbit_idle", "Rabbit_walk", "Rabbit_run"]


def test_parse_meta_clip_names_empty_when_no_table(tmp_path):
    meta = tmp_path / "no_clips.fbx.meta"
    meta.write_text("guid: abc\nModelImporter:\n  serializedVersion: 1\n", encoding="utf-8")
    assert bmi.parse_meta_clip_names(meta) == []


def test_parse_meta_clip_names_ignores_second_outside_table(tmp_path: Path) -> None:
    meta = tmp_path / "mixed.fbx.meta"
    meta.write_text(
        "guid: abc\n"
        "ModelImporter:\n"
        "  internalIDToNameTable:\n"
        "  - first:\n"
        "      74: 7400000\n"
        "    second: ClipA\n"
        "  externalObjects:\n"
        "  - first: {type: Mesh, assembly: a, ns: '', name: Mesh}\n"
        "    second: should_not_appear\n",
        encoding="utf-8",
    )
    assert bmi.parse_meta_clip_names(meta) == ["ClipA"]


def test_find_controllers_referencing_guid_returns_matches_only():
    rabbit_guid = "f01ef593d9cf73a4e94a2ab37b4745c1"
    matches = bmi.find_controllers_referencing_guid(FIXTURE_DIR, rabbit_guid)
    names = sorted(p.name for p in matches)
    assert names == ["AnimalController_0_Rabbit.controller"]


def test_find_controllers_referencing_guid_empty_when_no_match():
    matches = bmi.find_controllers_referencing_guid(FIXTURE_DIR, "0" * 32)
    assert matches == []


def test_find_controllers_referencing_guid_only_matches_m_motion():
    rabbit_guid = "f01ef593d9cf73a4e94a2ab37b4745c1"
    matches = bmi.find_controllers_referencing_guid(FIXTURE_DIR, rabbit_guid)
    names = sorted(p.name for p in matches)
    assert "ControllerWithNonMotionGuid.controller" not in names
    assert names == ["AnimalController_0_Rabbit.controller"]


def test_find_controllers_referencing_guid_case_insensitive_on_guid():
    rabbit_guid_upper = "F01EF593D9CF73A4E94A2AB37B4745C1"
    matches = bmi.find_controllers_referencing_guid(FIXTURE_DIR, rabbit_guid_upper)
    names = sorted(p.name for p in matches)
    assert names == ["AnimalController_0_Rabbit.controller"]


def test_count_prefabs_referencing_guid_only_counts_matches():
    rabbit_guid = "f01ef593d9cf73a4e94a2ab37b4745c1"
    assert bmi.count_prefabs_referencing_guid(FIXTURE_DIR, rabbit_guid) == 2


def test_count_prefabs_returns_zero_when_no_match():
    assert bmi.count_prefabs_referencing_guid(FIXTURE_DIR, "0" * 32) == 0


def test_count_prefabs_only_counts_m_source_prefab_field():
    rabbit_guid = "f01ef593d9cf73a4e94a2ab37b4745c1"
    # PrefabWithNonSourceGuid has rabbit guid in m_CorrespondingSourceObject (non-match)
    # but m_SourcePrefab there points to a different guid, so total should still be 2.
    assert bmi.count_prefabs_referencing_guid(FIXTURE_DIR, rabbit_guid) == 2


def test_count_prefabs_case_insensitive_on_guid():
    rabbit_guid_upper = "F01EF593D9CF73A4E94A2AB37B4745C1"
    assert bmi.count_prefabs_referencing_guid(FIXTURE_DIR, rabbit_guid_upper) == 2

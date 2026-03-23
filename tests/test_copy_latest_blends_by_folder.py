import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import copy_latest_blends_by_folder as clb


def write_file(path: Path, content: str = "blend data") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def set_mtime(path: Path, timestamp: int) -> None:
    os.utime(path, (timestamp, timestamp))


def test_selects_latest_blend_per_folder(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"
    dest = tmp_path / "Asset" / "latest_blends_by_folder"

    older = write_file(source / "animal" / "fox_old.blend")
    newer = write_file(source / "animal" / "fox_new.blend")
    write_file(source / "animal" / "fox_new.blend1")

    set_mtime(older, 100)
    set_mtime(newer, 200)

    copied = clb.copy_latest_blends(source, dest)

    assert len(copied) == 1
    assert not (dest / "animal" / "fox_old.blend").exists()
    assert (dest / "animal" / "fox_new.blend").exists()
    assert not (dest / "animal" / "fox_new.blend1").exists()


def test_preserves_relative_paths_for_duplicate_filenames(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"
    dest = tmp_path / "Asset" / "latest_blends_by_folder"

    first = write_file(source / "group_a" / "same.blend")
    second = write_file(source / "group_b" / "same.blend")

    set_mtime(first, 100)
    set_mtime(second, 200)

    copied = clb.copy_latest_blends(source, dest)

    assert len(copied) == 2
    assert (dest / "group_a" / "same.blend").exists()
    assert (dest / "group_b" / "same.blend").exists()


def test_tie_breaker_uses_path_string_when_mtime_matches(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"

    alpha = write_file(source / "animal" / "alpha.blend")
    omega = write_file(source / "animal" / "omega.blend")

    set_mtime(alpha, 100)
    set_mtime(omega, 100)

    selected = clb.select_latest_by_parent([alpha, omega])

    assert selected[alpha.parent] == omega


def test_existing_destination_is_recreated(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"
    dest = tmp_path / "Asset" / "latest_blends_by_folder"

    latest = write_file(source / "animal" / "fox.blend")
    stale_output = write_file(dest / "stale.txt", "old output")

    set_mtime(latest, 300)
    set_mtime(stale_output, 100)

    clb.copy_latest_blends(source, dest)

    assert not stale_output.exists()
    assert (dest / "animal" / "fox.blend").exists()


def test_dest_inside_source_is_rejected(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"
    dest = source / "latest"

    write_file(source / "animal" / "fox.blend")

    with pytest.raises(ValueError, match="source 내부"):
        clb.copy_latest_blends(source, dest)


def test_dest_ancestor_of_source_is_rejected(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"
    dest = tmp_path / "Asset"

    write_file(source / "animal" / "fox.blend")

    with pytest.raises(ValueError, match="상위 경로"):
        clb.copy_latest_blends(source, dest)


def test_guess_animal_name_collapses_animation_variants():
    assert clb.guess_animal_name("baby_duck_run.blend") == "baby_duck"
    assert clb.guess_animal_name("baby_duck_swim_idle.blend") == "baby_duck"
    assert clb.guess_animal_name("Fox_AllAni_260318_RigConvert.blend") == "fox"
    assert clb.guess_animal_name("bear_AllAni_statue.blend") == "bear"
    assert clb.guess_animal_name("Baby_Tiger_roar01.blend") == "baby_tiger"
    assert clb.guess_animal_name("Baby_panda_ReTargetTest.blend") == "baby_panda"
    assert clb.guess_animal_name("albatross_Aniamtion2.blend") == "albatross"
    assert clb.guess_animal_name("albatross_flight004.blend") == "albatross"


def test_animal_mode_excludes_helper_directories_and_selects_latest(tmp_path: Path):
    source = tmp_path / "Asset" / "BlenderFile"
    dest = tmp_path / "Asset" / "latest_blends_by_animal"

    included_older = write_file(source / "normal" / "baby_duck_run.blend")
    included_newer = write_file(source / "2025" / "baby_duck_walk.blend")
    excluded_ui = write_file(source / "2026" / "UI" / "baby_duck_idle.blend")
    excluded_backup = write_file(source / "normal" / "BackUp" / "baby_duck_pose.blend")

    set_mtime(included_older, 100)
    set_mtime(included_newer, 200)
    set_mtime(excluded_ui, 300)
    set_mtime(excluded_backup, 400)

    copied = clb.copy_latest_blends(
        source,
        dest,
        group_by="animal",
        excluded_dir_names=clb.DEFAULT_EXCLUDED_DIRS_FOR_ANIMAL,
    )

    assert len(copied) == 1
    assert (dest / "baby_duck_walk.blend").exists()
    assert not (dest / "baby_duck_idle.blend").exists()
    assert not (dest / "baby_duck_pose.blend").exists()


def test_unique_dest_path_renames_on_filename_collision(tmp_path: Path):
    dest = tmp_path / "Asset" / "latest_blends_by_animal"
    used_names = {"shared.blend"}
    src = tmp_path / "source" / "shared.blend"
    write_file(src)

    resolved = clb.unique_dest_path(dest, src, "dogs", used_names)

    assert resolved.name == "dogs__shared.blend"

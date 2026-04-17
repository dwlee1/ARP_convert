import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

FIXTURE_CSV = (
    PROJECT_ROOT / "tests" / "fixtures" / "unity_migration" / "migration_inventory_sample.csv"
)

import fbx_to_blend as ftb


def test_lookup_row_by_id_finds_rabbit():
    row = ftb.lookup_row(FIXTURE_CSV, "Rabbit")
    assert row["animation_fbx_path"].endswith("rabbit_animation.fbx")
    assert row["model_fbx_paths"] == ["Rabbit_DutchBrown.fbx", "Animal_2002.fbx"]


def test_lookup_row_raises_for_unknown_id():
    with pytest.raises(KeyError, match="Unknown id"):
        ftb.lookup_row(FIXTURE_CSV, "ghostzebra")


def test_resolve_fbx_paths_returns_absolute():
    row = ftb.lookup_row(FIXTURE_CSV, "Rabbit")
    unity_root = Path("C:/Unity")
    anim, models = ftb.resolve_fbx_paths(row, unity_root)
    assert anim == unity_root / "Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx"
    assert models == [
        unity_root / "Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx",
        unity_root / "Assets/5_Models/02. Animals/00.Rabbit/Animal_2002.fbx",
    ]

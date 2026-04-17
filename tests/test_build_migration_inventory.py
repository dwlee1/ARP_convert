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

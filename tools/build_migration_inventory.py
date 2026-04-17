"""Unity 프로젝트 animation FBX 인벤토리 CSV 생성.

Usage:
    python tools/build_migration_inventory.py \\
        --unity-root "C:/Users/manag/GitProject/LittleWitchForestMobile" \\
        --output docs/MigrationInventory.csv
"""

from __future__ import annotations

import re
from pathlib import Path

_GUID_RE = re.compile(r"^guid:\s*([0-9a-f]{32})\s*$", re.MULTILINE)


def parse_meta_guid(meta_path: Path) -> str | None:
    """.meta 파일 최상위 `guid:` 라인에서 32자리 hex 추출."""
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _GUID_RE.search(text)
    return m.group(1) if m else None


_CLIP_NAME_RE = re.compile(r"^\s*second:\s*(\S.*?)\s*$", re.MULTILINE)


def parse_meta_clip_names(meta_path: Path) -> list[str]:
    """`internalIDToNameTable` 하위 `second: <name>` 라인을 순서대로 수집."""
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if "internalIDToNameTable:" not in text:
        return []
    return _CLIP_NAME_RE.findall(text.split("internalIDToNameTable:", 1)[1])

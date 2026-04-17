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


def _extract_table_block(text: str) -> str:
    """Return only the content belonging to `internalIDToNameTable:`.

    Scans for the marker line, records its indentation depth, then collects
    subsequent lines until a non-blank sibling key at the *same* indent level
    is encountered.  YAML sequence items (`- `) at that indent are part of the
    block; bare keys at that indent are siblings (end of block).
    """
    lines_all = text.splitlines()
    marker = "internalIDToNameTable:"
    start_idx = None
    marker_indent = 0
    for i, line in enumerate(lines_all):
        stripped = line.lstrip()
        if stripped.startswith(marker):
            marker_indent = len(line) - len(stripped)
            start_idx = i + 1
            break
    if start_idx is None:
        return ""
    collected: list[str] = []
    for line in lines_all[start_idx:]:
        if line.strip() == "":
            collected.append(line)
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.lstrip()
        # A sibling key at the same indent ends the block.
        # YAML list items (`- `) at the same indent are still part of the block.
        if indent == marker_indent and not stripped.startswith("- "):
            break
        if indent < marker_indent:
            break
        collected.append(line)
    return "\n".join(collected)


def parse_meta_clip_names(meta_path: Path) -> list[str]:
    """`internalIDToNameTable` 하위 `second: <name>` 라인을 순서대로 수집."""
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if "internalIDToNameTable:" not in text:
        return []
    return _CLIP_NAME_RE.findall(_extract_table_block(text))


def find_controllers_referencing_guid(search_root: Path, target_guid: str) -> list[Path]:
    """search_root 아래 *.controller 파일 중 m_Motion에서 target_guid 참조하는 것."""
    needle = f"guid: {target_guid}"
    matches: list[Path] = []
    for ctrl in search_root.rglob("*.controller"):
        try:
            if needle in ctrl.read_text(encoding="utf-8"):
                matches.append(ctrl)
        except OSError:
            continue
    return matches

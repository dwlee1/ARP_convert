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
    needle = f"guid: {target_guid.lower()}"
    matches: list[Path] = []
    for ctrl in search_root.rglob("*.controller"):
        try:
            text = ctrl.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if "m_Motion" in line and needle in line:
                matches.append(ctrl)
                break
    return matches


def count_prefabs_referencing_guid(search_root: Path, target_guid: str) -> int:
    """search_root 아래 *.prefab 중 m_SourcePrefab이 target_guid를 참조하는 파일 수."""
    needle = f"guid: {target_guid.lower()}"
    count = 0
    for pf in search_root.rglob("*.prefab"):
        try:
            text = pf.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            if "m_SourcePrefab" in line and needle in line:
                count += 1
                break
    return count


def _derive_id_from_folder(animation_fbx_path: Path) -> str:
    """부모 폴더명을 id로 사용. `00.Rabbit` → `Rabbit`."""
    folder = animation_fbx_path.parent.name
    if "." in folder:
        folder = folder.split(".", 1)[1]
    return folder


def build_row(animation_fbx: Path, unity_root: Path) -> dict:
    """animation FBX 1개에 대한 CSV row 조립. guid/클립/컨트롤러/프리팹 참조 계산."""
    meta = animation_fbx.with_suffix(animation_fbx.suffix + ".meta")
    guid = parse_meta_guid(meta) or ""
    clip_names = parse_meta_clip_names(meta)

    model_fbxs = sorted(
        p.name for p in animation_fbx.parent.glob("*.fbx") if p.name != animation_fbx.name
    )

    controllers_root = unity_root / "Assets" / "6_Animations" / "Animals" / "Controllers"
    prefabs_root = unity_root / "Assets" / "3_Prefabs" / "Animals"

    controller_paths = (
        [
            str(p.relative_to(unity_root)).replace("\\", "/")
            for p in find_controllers_referencing_guid(controllers_root, guid)
        ]
        if guid
        else []
    )
    prefab_count = count_prefabs_referencing_guid(prefabs_root, guid) if guid else 0

    return {
        "id": _derive_id_from_folder(animation_fbx),
        "animation_fbx_path": str(animation_fbx.relative_to(unity_root)).replace("\\", "/"),
        "animation_fbx_guid": guid,
        "model_fbx_paths": model_fbxs,
        "controller_paths": controller_paths,
        "prefab_count": prefab_count,
        "clip_count": len(clip_names),
        "clip_names": clip_names,
        "locomotion": "pending",
        "scope": "pending",
        "source_blend_hint": "",
        "status": "not_started",
        "notes": "",
    }

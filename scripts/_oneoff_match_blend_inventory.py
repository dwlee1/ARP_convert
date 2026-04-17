"""One-off: match Unity in_scope rows to Blender inventory rows.

Fills docs/MigrationInventory.csv `source_blend_hint` column with the
matching `Relative_Path` from Asset/Blender/animal_blend_inventory.csv.

Delete this script after use. Re-running is idempotent.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = REPO_ROOT / "Asset" / "Blender"
MIGRATION_CSV = REPO_ROOT / "docs" / "MigrationInventory.csv"
BLEND_CSV = ASSET_ROOT / "animal_blend_inventory.csv"

# Fill after 1st run as needed. Key = normalized Unity id, value = normalized Animal_EN.
ALIAS_TABLE: dict[str, str] = {}


def normalize(name: str) -> str:
    """Lowercase, drop whitespace, drop parens content, drop slash-tail, keep alnum only."""
    s = re.sub(r"\([^)]*\)", "", name)
    s = s.split("/")[0]
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def match_by_normalized(unity_id: str, blend_rows: list[dict]) -> dict | None:
    target = normalize(unity_id)
    for row in blend_rows:
        if normalize(row["Animal_EN"]) == target:
            return row
    return None


def match_by_path(unity_id: str, blend_rows: list[dict]) -> dict | None:
    needle = unity_id.lower()
    for row in blend_rows:
        if needle in row["Relative_Path"].lower():
            return row
    return None


def match_by_alias(unity_id: str, blend_rows: list[dict]) -> dict | None:
    alias = ALIAS_TABLE.get(normalize(unity_id))
    if not alias:
        return None
    for row in blend_rows:
        if normalize(row["Animal_EN"]) == alias:
            return row
    return None


def verify_file_exists(relative_path: str) -> bool:
    return (ASSET_ROOT / relative_path).is_file()


def forward_slash(path: str) -> str:
    return path.replace("\\", "/")


def main() -> None:
    with BLEND_CSV.open(encoding="utf-8") as f:
        blend_rows = list(csv.DictReader(f))

    with MIGRATION_CSV.open(encoding="utf-8") as f:
        unity_rows = list(csv.DictReader(f))
        unity_fieldnames = list(unity_rows[0].keys()) if unity_rows else []

    counters = {"normalized": 0, "path": 0, "alias": 0, "unresolved": 0}
    details: list[tuple[str, str, str]] = []  # (id, tag, path-or-message)

    for row in unity_rows:
        if row.get("scope") != "in_scope":
            continue
        uid = row["id"]

        hit = match_by_normalized(uid, blend_rows)
        tag = "normalized"
        if not hit:
            hit = match_by_path(uid, blend_rows)
            tag = "path"
        if not hit:
            hit = match_by_alias(uid, blend_rows)
            tag = "alias"

        if hit and verify_file_exists(hit["Relative_Path"]):
            rel = forward_slash(hit["Relative_Path"])
            row["source_blend_hint"] = rel
            counters[tag] += 1
            details.append((uid, tag, rel))
        else:
            row["source_blend_hint"] = "???"
            counters["unresolved"] += 1
            reason = "file missing" if hit else "no match"
            details.append((uid, "???", reason))

    with MIGRATION_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=unity_fieldnames)
        writer.writeheader()
        writer.writerows(unity_rows)

    print(f"Matched (normalized): {counters['normalized']}")
    print(f"Matched (path fallback): {counters['path']}")
    print(f"Matched (alias): {counters['alias']}")
    print(f"Unresolved: {counters['unresolved']}")
    print()
    print("=== Per-entry detail ===")
    for uid, tag, info in details:
        print(f"{uid:16} [{tag:10}] {info}")


if __name__ == "__main__":
    main()

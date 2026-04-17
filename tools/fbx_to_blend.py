"""Unity FBX들을 하나의 blend로 재구성.

외부 실행 (Blender headless):
    blender --background --python tools/fbx_to_blend.py -- \\
        --csv docs/MigrationInventory.csv \\
        --id Rabbit \\
        --unity-root "C:/Users/manag/GitProject/LittleWitchForestMobile" \\
        --output pilot/rabbit_unity_source.blend

`bpy` 없이도 임포트 가능하도록 헬퍼와 Blender 본문을 분리한다.
"""

from __future__ import annotations

import csv
from pathlib import Path


def lookup_row(csv_path: Path, target_id: str) -> dict:
    """CSV에서 id가 일치하는 row를 dict로 반환. 없으면 KeyError."""
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            if raw["id"] == target_id:
                return {
                    **raw,
                    "model_fbx_paths": [
                        s for s in (raw.get("model_fbx_paths") or "").split(";") if s
                    ],
                    "clip_names": [s for s in (raw.get("clip_names") or "").split(";") if s],
                }
    raise KeyError(f"Unknown id: {target_id}")


def resolve_fbx_paths(row: dict, unity_root: Path) -> tuple[Path, list[Path]]:
    """row → (animation_fbx 절대경로, [model_fbx 절대경로...])."""
    anim = unity_root / row["animation_fbx_path"]
    anim_folder = anim.parent
    models = [anim_folder / name for name in row["model_fbx_paths"]]
    return anim, models

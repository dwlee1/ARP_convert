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

import argparse
import csv
import sys
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


def _reconstruct_in_blender(anim_fbx: Path, model_fbxs: list[Path], output: Path) -> None:
    """Blender 내부 전용 — factory reset → animation FBX import → model FBX import → mesh reparent → preprocess → save."""
    import bpy  # Blender 런타임에만 존재

    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.import_scene.fbx(filepath=str(anim_fbx))
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError(f"animation FBX에 Armature 없음: {anim_fbx}")
    master_arm = armatures[0]
    master_arm.name = "Armature_" + output.stem

    for model_fbx in model_fbxs:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=str(model_fbx))
        added = [obj for obj in bpy.data.objects if obj not in before]

        # 중복 armature는 삭제, mesh는 master armature로 re-parent
        for obj in list(added):
            if obj.type == "ARMATURE":
                bpy.data.objects.remove(obj, do_unlink=True)
            elif obj.type == "MESH":
                obj.parent = master_arm
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE":
                        mod.object = master_arm

    stats = _apply_preprocess(master_arm)
    print(f"[fbx_to_blend] preprocess: {stats}")

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


def _apply_preprocess(armature) -> dict:
    """armature에 fbx_preprocess 3단계(A-1/A-2/A-3) 적용. 통계 dict 반환."""
    import bpy

    tools_dir = str(Path(__file__).parent)
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import fbx_preprocess as pre

    bones_data = {
        b.name: {
            "parent": b.parent.name if b.parent else None,
            "length": b.length,
        }
        for b in armature.data.bones
    }

    a1_plan = pre.plan_controller_removal(bones_data)
    a2_orphans = pre.find_orphan_bones(bones_data)
    a3_shrink = pre.compute_leaf_tail_shrink(bones_data, ratio=0.1)

    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT")
    eb = armature.data.edit_bones

    for child_name, new_parent_name in a1_plan["reparent"].items():
        if child_name not in eb:
            continue
        eb[child_name].parent = eb.get(new_parent_name) if new_parent_name else None

    for name in a1_plan["remove"]:
        if name in eb:
            eb.remove(eb[name])

    for name, new_length in a3_shrink.items():
        if name not in eb:
            continue
        b = eb[name]
        direction = (b.tail - b.head).normalized()
        b.tail = b.head + direction * new_length

    bpy.ops.object.mode_set(mode="OBJECT")

    if a2_orphans:
        print(f"[fbx_to_blend] A-2 orphans (보존, 어태치먼트일 수 있음 — 수동 검토): {a2_orphans}")

    return {
        "controllers_removed": len(a1_plan["remove"]),
        "controllers_reparented": len(a1_plan["reparent"]),
        "orphans_reported": len(a2_orphans),
        "leaves_shrunk": len(a3_shrink),
    }


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        # Blender `--python ... -- --id X` 호출: `--` 이후만 파싱
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1 :]
        else:
            argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Unity FBX → 통합 blend 재구성")
    parser.add_argument("--csv", required=True, type=Path, help="MigrationInventory.csv 경로")
    parser.add_argument("--id", dest="target_id", required=True, help="CSV의 id 컬럼")
    parser.add_argument("--unity-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    row = lookup_row(args.csv, args.target_id)
    anim, models = resolve_fbx_paths(row, args.unity_root)

    for p in [anim, *models]:
        if not p.is_file():
            raise FileNotFoundError(p)

    _reconstruct_in_blender(anim, models, args.output)
    print(f"[fbx_to_blend] saved: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

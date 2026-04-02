"""
extract_blend_identity.py
=========================
Blender 내부에서 현재 열린 .blend의 리그/애니메이션/메시 메타데이터를 추출한다.

사용법:
  blender --background file.blend --python tools/blend_identity/extract_blend_identity.py -- --output out.json
"""

import hashlib
import json
import os
import re
import sys

import bpy


def parse_args():
    argv = sys.argv
    if "--" not in argv:
        return {}

    args = {}
    custom_args = argv[argv.index("--") + 1 :]
    i = 0
    while i < len(custom_args):
        if custom_args[i] == "--output" and i + 1 < len(custom_args):
            args["output"] = custom_args[i + 1]
            i += 2
        else:
            i += 1
    return args


def normalize_name(name):
    value = name.strip().lower()
    value = re.sub(r"\(.*?\)", "", value)
    value = re.sub(r"[\s\-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def sha1_of(value):
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def find_source_armature():
    preferred_obj = None
    preferred_count = -1
    fallback_obj = None
    fallback_count = -1

    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        total = len(obj.data.bones)
        if total > fallback_count:
            fallback_obj = obj
            fallback_count = total

        c_bones = len([b for b in obj.data.bones if b.name.startswith("c_")])
        if c_bones > 5:
            continue
        if total > preferred_count:
            preferred_obj = obj
            preferred_count = total

    return preferred_obj or fallback_obj


def collect_armature_meta(obj):
    bones = []
    deform_count = 0
    for bone in obj.data.bones:
        parent_name = bone.parent.name if bone.parent else ""
        if bone.use_deform:
            deform_count += 1
        bones.append(
            {
                "name": bone.name,
                "norm_name": normalize_name(bone.name),
                "parent": parent_name,
                "norm_parent": normalize_name(parent_name) if parent_name else "",
                "use_deform": bool(bone.use_deform),
            }
        )

    bones.sort(key=lambda item: item["norm_name"])

    bone_signature_rows = [
        (item["norm_name"], item["norm_parent"], item["use_deform"]) for item in bones
    ]

    return {
        "name": obj.name,
        "data_name": obj.data.name,
        "bone_count": len(obj.data.bones),
        "deform_bone_count": deform_count,
        "bone_names": [item["name"] for item in bones],
        "bone_signature": sha1_of(bone_signature_rows),
    }


def collect_actions():
    actions = []
    for action in bpy.data.actions:
        actions.append(
            {
                "name": action.name,
                "norm_name": normalize_name(action.name),
                "frame_start": int(action.frame_range[0]),
                "frame_end": int(action.frame_range[1]),
                "fcurve_count": len(action.fcurves),
            }
        )

    actions.sort(key=lambda item: item["norm_name"])
    return actions


def collect_bound_meshes(source_armature):
    bound_meshes = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and mod.object == source_armature:
                bound_meshes.append(obj)
                break
    return bound_meshes


def collect_mesh_meta(mesh_objects):
    meshes = []
    for obj in mesh_objects:
        data_name = obj.data.name if obj.data else ""
        vert_count = len(obj.data.vertices) if obj.data else 0
        meshes.append(
            {
                "object_name": obj.name,
                "norm_object_name": normalize_name(obj.name),
                "data_name": data_name,
                "norm_data_name": normalize_name(data_name),
                "vertex_count": vert_count,
                "material_slot_count": len(obj.material_slots),
            }
        )

    meshes.sort(key=lambda item: item["norm_object_name"])
    return meshes


def build_fingerprints(source_armature_meta, actions, mesh_meta):
    action_name_rows = sorted(item["norm_name"] for item in actions)
    action_detail_rows = [
        (item["norm_name"], item["frame_start"], item["frame_end"], item["fcurve_count"])
        for item in actions
    ]
    mesh_name_rows = [(item["norm_object_name"], item["norm_data_name"]) for item in mesh_meta]
    mesh_detail_rows = [
        (
            item["norm_object_name"],
            item["norm_data_name"],
            item["vertex_count"],
            item["material_slot_count"],
        )
        for item in mesh_meta
    ]

    return {
        "source_bone_signature": source_armature_meta["bone_signature"]
        if source_armature_meta
        else "",
        "action_name_signature": sha1_of(action_name_rows),
        "action_detail_signature": sha1_of(action_detail_rows),
        "mesh_name_signature": sha1_of(mesh_name_rows),
        "mesh_detail_signature": sha1_of(mesh_detail_rows),
        "rig_action_name_signature": sha1_of(
            [
                source_armature_meta["bone_signature"] if source_armature_meta else "",
                sha1_of(action_name_rows),
            ]
        ),
        "rig_action_detail_signature": sha1_of(
            [
                source_armature_meta["bone_signature"] if source_armature_meta else "",
                sha1_of(action_detail_rows),
            ]
        ),
    }


def main():
    args = parse_args()
    output_path = args.get("output")
    if not output_path:
        raise SystemExit("--output 경로가 필요합니다.")

    source_armature = find_source_armature()
    armatures = [collect_armature_meta(obj) for obj in bpy.data.objects if obj.type == "ARMATURE"]
    source_armature_meta = collect_armature_meta(source_armature) if source_armature else None
    actions = collect_actions()
    mesh_objects = (
        collect_bound_meshes(source_armature)
        if source_armature
        else [obj for obj in bpy.data.objects if obj.type == "MESH"]
    )
    mesh_meta = collect_mesh_meta(mesh_objects)
    fingerprints = build_fingerprints(source_armature_meta, actions, mesh_meta)

    payload = {
        "blend_path": bpy.data.filepath,
        "blend_name": os.path.basename(bpy.data.filepath),
        "source_armature": source_armature_meta,
        "armatures": armatures,
        "actions": actions,
        "bound_meshes": mesh_meta,
        "fingerprints": fingerprints,
    }

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

    print(
        json.dumps(
            {
                "blend_name": payload["blend_name"],
                "source_armature": source_armature_meta["name"] if source_armature_meta else "",
                "action_count": len(actions),
                "mesh_count": len(mesh_meta),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

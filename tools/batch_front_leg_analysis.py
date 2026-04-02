"""
4족 동물 앞다리 구조 일괄 분석.
Usage: blender --background --python batch_front_leg_analysis.py -- <blend1> <name1> <blend2> <name2> ...
"""

import json
import sys

import bpy


def get_armature():
    best = None
    best_count = 0
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            count = len(obj.data.bones)
            if count > best_count:
                best_count = count
                best = obj
    return best


def trace_deform_chain(bone):
    """deform 본만 따라가며 체인 추출."""
    chain = [bone.name]
    current = bone
    while True:
        children = [c for c in current.children if c.use_deform]
        if not children:
            break
        # 가장 아래로 내려가는 자식
        best = min(children, key=lambda c: c.tail_local[2])
        chain.append(best.name)
        current = best
    return chain


def analyze_front_legs(arm):
    """앞다리 체인을 이름 기반 + 구조 기반으로 찾는다."""
    bones = arm.data.bones
    deform_bones = {b.name: b for b in bones if b.use_deform}

    # 모든 deform 본을 분류
    all_bone_names = sorted(deform_bones.keys())

    # 앞다리 체인 찾기: shoulder 또는 upperarm에서 시작
    front_chains_L = []
    front_chains_R = []

    for bname, bone in deform_bones.items():
        name_lower = bname.lower()
        # shoulder 또는 upperarm으로 시작하는 체인 (부모가 비-arm 계열)
        is_chain_start = False
        if "shoulder" in name_lower:
            is_chain_start = True
        elif "upperarm" in name_lower:
            # 부모가 shoulder가 아닌 경우만 (shoulder가 있으면 거기서 시작)
            parent_name = bone.parent.name.lower() if bone.parent else ""
            if "shoulder" not in parent_name:
                is_chain_start = True

        if is_chain_start:
            chain = trace_deform_chain(bone)
            if (
                "_l" in bname.lower()
                or bname.endswith("_L")
                or ".l" in bname.lower()
                or bname.endswith(".L")
                or "_left" in bname.lower()
            ):
                front_chains_L.append(chain)
            elif (
                "_r" in bname.lower()
                or bname.endswith("_R")
                or ".r" in bname.lower()
                or bname.endswith(".R")
                or "_right" in bname.lower()
            ):
                front_chains_R.append(chain)

    # 2) 뒷다리도 찾기 (비교용)
    back_chains_L = []
    back_chains_R = []
    for bname, bone in deform_bones.items():
        name_lower = bname.lower()
        if "thigh" in name_lower or (
            "leg" in name_lower
            and "fore" not in name_lower
            and bone.parent
            and "thigh" not in bone.parent.name.lower()
            and "leg" not in bone.parent.name.lower()
        ):
            # thigh에서 시작
            if "thigh" in name_lower:
                parent_name = bone.parent.name.lower() if bone.parent else ""
                if "thigh" not in parent_name:
                    chain = trace_deform_chain(bone)
                    if "_l" in bname.lower() or bname.endswith("_L") or ".l" in bname.lower():
                        back_chains_L.append(chain)
                    elif "_r" in bname.lower() or bname.endswith("_R") or ".r" in bname.lower():
                        back_chains_R.append(chain)

    # 3) 이름 패턴 분류
    # front_leg 체인이 없으면 구조 기반으로 찾기
    if not front_chains_L:
        # 모든 deform 본을 순회하며, 위치가 앞쪽(+Y 작은 값)이고 아래로 내려가는 체인 찾기
        # spine을 먼저 찾고, spine의 앞쪽 절반에서 내려가는 가지 찾기
        pass

    return {
        "front_leg_L": front_chains_L,
        "front_leg_R": front_chains_R,
        "back_leg_L": back_chains_L,
        "back_leg_R": back_chains_R,
        "all_deform_bones": all_bone_names,
    }


def analyze_file(blend_path, animal_name):
    try:
        bpy.ops.wm.open_mainfile(filepath=blend_path)
    except Exception as e:
        return {"animal": animal_name, "error": str(e)}

    arm = get_armature()
    if not arm:
        return {"animal": animal_name, "error": "No armature found"}

    result = analyze_front_legs(arm)
    result["animal"] = animal_name
    result["armature"] = arm.name
    result["deform_count"] = len([b for b in arm.data.bones if b.use_deform])
    return result


if __name__ == "__main__":
    argv = sys.argv
    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
    else:
        args = []

    # 인자: blend_path name blend_path name ...
    results = []
    i = 0
    while i < len(args) - 1:
        blend_path = args[i]
        animal_name = args[i + 1]
        result = analyze_file(blend_path, animal_name)
        results.append(result)
        i += 2

    print("===JSON_START===")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print("===JSON_END===")

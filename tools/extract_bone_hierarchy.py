"""
Blender 백그라운드 모드에서 실행: 4족 동물 본 구조 추출
Usage: blender --background --python extract_bone_hierarchy.py -- <blend_file>
"""

import json
import sys

import bpy


def get_armature():
    """씬에서 가장 큰 아마추어를 찾는다."""
    best = None
    best_count = 0
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            count = len(obj.data.bones)
            if count > best_count:
                best_count = count
                best = obj
    return best


def trace_hierarchy(bone, depth=0):
    """본 하이어라키를 딕셔너리로 변환."""
    info = {
        "name": bone.name,
        "depth": depth,
        "head": [round(v, 4) for v in bone.head_local],
        "tail": [round(v, 4) for v in bone.tail_local],
        "children": [],
        "use_deform": bone.use_deform,
    }
    for child in bone.children:
        info["children"].append(trace_hierarchy(child, depth + 1))
    return info


def find_front_leg_chain(armature_obj):
    """
    앞다리 체인을 찾는다.
    전략: 루트에서 spine 방향(+Z or +Y)을 추적, spine 끝 근처에서
    아래(-Z)로 내려가는 가지를 찾음.
    """
    bones = armature_obj.data.bones

    # deform 본만
    deform_bones = [b for b in bones if b.use_deform]

    # 이름 기반으로 앞다리 관련 본 찾기
    front_leg_keywords = [
        "shoulder",
        "upperarm",
        "arm",
        "hand",
        "finger",
        "clavicle",
        "humerus",
        "radius",
        "wrist",
        "paw",
        "front_leg",
        "frontleg",
        "f_leg",
        "fore",
    ]

    front_bones = {}
    for b in deform_bones:
        name_lower = b.name.lower()
        for kw in front_leg_keywords:
            if kw in name_lower:
                front_bones[b.name] = {
                    "keyword": kw,
                    "parent": b.parent.name if b.parent else None,
                    "children": [c.name for c in b.children if c.use_deform],
                    "head": [round(v, 4) for v in b.head_local],
                    "tail": [round(v, 4) for v in b.tail_local],
                }
                break

    return front_bones


def trace_chain_from(bone):
    """본에서 체인을 따라가며 이름 리스트 반환 (deform만)."""
    chain = [bone.name]
    current = bone
    while True:
        deform_children = [c for c in current.children if c.use_deform]
        if len(deform_children) == 0:
            break
        elif len(deform_children) == 1:
            chain.append(deform_children[0].name)
            current = deform_children[0]
        else:
            # 가장 긴 체인을 가진 자식 선택
            best = None
            best_len = 0
            for c in deform_children:
                sub = trace_chain_from(c)
                if len(sub) > best_len:
                    best_len = len(sub)
                    best = c
            if best:
                chain.append(best.name)
                current = best
            else:
                break
    return chain


def find_downward_chains(armature_obj):
    """
    spine에서 아래로 내려가는 모든 체인을 찾는다.
    spine = 루트에서 시작해 +Z 방향으로 올라가는 체인.
    """
    bones = armature_obj.data.bones

    # 루트 찾기 (부모 없는 deform 본)
    roots = [b for b in bones if b.parent is None and b.use_deform]
    if not roots:
        roots = [b for b in bones if b.parent is None]

    if not roots:
        return {}

    root = roots[0]

    # spine 추적: 루트에서 +Z 방향
    spine = [root.name]
    current = root
    while True:
        children = [c for c in current.children if c.use_deform]
        # Z가 올라가는 자식 중 가장 높은 것
        up_children = []
        for c in children:
            dz = c.tail_local[2] - c.head_local[2]
            if dz > 0 or c.tail_local[2] > current.head_local[2]:
                up_children.append((c, c.tail_local[2]))

        if not up_children:
            break

        up_children.sort(key=lambda x: x[1], reverse=True)
        spine.append(up_children[0][0].name)
        current = up_children[0][0]

    spine_set = set(spine)

    # spine 각 본에서 아래로 내려가는 가지 찾기
    chains = {}
    for spine_bone_name in spine:
        bone = bones[spine_bone_name]
        for child in bone.children:
            if not child.use_deform or child.name in spine_set:
                continue
            # 아래로 내려가는지 확인
            dz = child.tail_local[2] - child.head_local[2]
            if dz < -0.001:  # 아래로 향함
                chain = trace_chain_from(child)
                # 어느 쪽인지 (X 좌표로 판단)
                side = "L" if child.head_local[0] > 0 else "R"
                # spine 위치로 front/back 판단
                spine_idx = spine.index(spine_bone_name)
                pos = "front" if spine_idx > len(spine) * 0.4 else "back"

                key = f"{pos}_{side}_{spine_bone_name}"
                chains[key] = {
                    "spine_origin": spine_bone_name,
                    "spine_position": f"{spine_idx}/{len(spine)}",
                    "side": side,
                    "position": pos,
                    "chain": chain,
                    "chain_length": len(chain),
                }

    return {
        "spine": spine,
        "spine_length": len(spine),
        "downward_chains": chains,
    }


def analyze_file(blend_path):
    """blend 파일의 아마추어 구조를 분석."""
    bpy.ops.wm.open_mainfile(filepath=blend_path)

    arm = get_armature()
    if not arm:
        return {"error": "No armature found"}

    bones = arm.data.bones
    deform_bones = [b for b in bones if b.use_deform]

    # 전체 deform 본 이름 리스트 (계층 순)
    all_deform = []
    for b in deform_bones:
        depth = 0
        p = b.parent
        while p:
            depth += 1
            p = p.parent
        all_deform.append(
            {
                "name": b.name,
                "depth": depth,
                "parent": b.parent.name if b.parent else None,
                "children": [c.name for c in b.children if c.use_deform],
                "head_z": round(b.head_local[2], 4),
                "head_x": round(b.head_local[0], 4),
            }
        )
    all_deform.sort(key=lambda x: x["depth"])

    # 앞다리 관련 본 (이름 기반)
    front_leg_info = find_front_leg_chain(arm)

    # 구조 기반 체인 분석
    structure = find_downward_chains(arm)

    return {
        "armature": arm.name,
        "total_bones": len(bones),
        "deform_bones_count": len(deform_bones),
        "all_deform_bones": all_deform,
        "front_leg_keyword_matches": front_leg_info,
        "structure_analysis": structure,
    }


if __name__ == "__main__":
    argv = sys.argv
    # '--' 이후 인자 파싱
    if "--" in argv:
        args = argv[argv.index("--") + 1 :]
    else:
        args = []

    if not args:
        print("Usage: blender --background --python extract_bone_hierarchy.py -- <blend_file>")
        sys.exit(1)

    blend_path = args[0]
    result = analyze_file(blend_path)
    print("===JSON_START===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print("===JSON_END===")

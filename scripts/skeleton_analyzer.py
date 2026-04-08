"""
스켈레톤 구조 분석기 (메인 모듈 + 재수출 파사드)
=================================================
소스 deform 본의 하이어라키/위치/방향을 분석하여
이름에 의존하지 않는 구조 기반 본 역할 식별.

핵심 분석 함수(analyze_skeleton)와 Preview Armature 생성/읽기를 담당하며,
skeleton_detection / arp_mapping 의 모든 public 심볼을 재수출하여
기존 ``from skeleton_analyzer import X`` 구문을 유지한다.

Entrypoints:
  analyze_skeleton(armature) -> analysis dict (bone_data, chains, unmapped, confidence)
  create_preview_armature(source, analysis) -> Preview Armature object
  read_preview_roles(preview) -> {role: [bone_names]}
  discover_arp_ref_chains(arp) -> {role: [ref_names]}
  build_preview_to_ref_mapping(preview, arp) -> {preview_bone: ref_bone}
  map_role_chain(role, src_bones, tgt_refs) -> {src: tgt}

Consumes: bpy Armature objects
Produces: analysis dict, Preview Armature, role/ref mappings
"""

from collections import defaultdict

import bpy

# ── skeleton_detection 에서 직접 사용하는 심볼 ──
from skeleton_detection import (
    DEBUG,
    FACE_BONE_KEYWORDS,
    ROLE_COLORS,
    ROLE_PROP_KEY,
    _reconstruct_spatial_hierarchy,
    build_preview_parent_overrides,
    count_descendants,
    extract_bone_data,
    filter_deform_bones,
    find_downward_branches,
    find_head_features,
    find_pole_vectors,
    find_root_bone,
    find_tail_chain,
    get_weighted_bone_names,
    split_leg_foot,
    trace_spine_chain,
    vec_dot,
)

VIRTUAL_NECK_BONE = "__virtual_neck__"
VIRTUAL_NECK_RATIO = 0.35


# ═══════════════════════════════════════════════════════════════
# 메인 분석 함수
# ═══════════════════════════════════════════════════════════════


def analyze_skeleton(armature_obj):
    """
    소스 아마추어의 deform 본을 분석하여 구조적 역할을 식별.

    Returns:
        dict: 분석 결과 (chains, unmapped, confidence 등)
    """
    # 1. 본 데이터 추출
    all_bones = extract_bone_data(armature_obj)
    weighted_bones = get_weighted_bone_names(armature_obj)
    deform_bones, excluded_zero_weight = filter_deform_bones(all_bones, weighted_bones)
    original_deform_bones = {
        name: dict(info, children=list(info.get("children", [])))
        for name, info in deform_bones.items()
    }

    # 디버그: 재구성 전 상태
    parentless_before = sum(1 for b in deform_bones.values() if b["parent"] is None)
    if DEBUG:
        print(
            f"[DEBUG] deform 본 총 {len(deform_bones)}개, 재구성 전 parentless: {parentless_before}"
        )
        for name, b in deform_bones.items():
            print(f"  [DEBUG] {name}: parent={b['parent']}, children={b['children']}")

    _reconstruct_spatial_hierarchy(deform_bones, all_bones, original_deform_bones)

    # 디버그: 재구성 후 상태
    parentless_after = sum(1 for b in deform_bones.values() if b["parent"] is None)
    if DEBUG:
        print(f"[DEBUG] 재구성 후 parentless: {parentless_after}")
        if parentless_after != parentless_before:
            for name, b in deform_bones.items():
                print(f"  [DEBUG-after] {name}: parent={b['parent']}, children={b['children']}")

    if not deform_bones:
        return {"error": "deform 본이 없습니다.", "chains": {}, "unmapped": [], "confidence": 0}

    # 2. 루트 찾기
    root_result = find_root_bone(deform_bones)
    if not root_result:
        return {
            "error": "루트 본을 찾을 수 없습니다.",
            "chains": {},
            "unmapped": list(deform_bones.keys()),
            "confidence": 0,
        }

    root_name = root_result[0]
    root_confidence = root_result[1]

    # 3. 스파인 체인 트레이싱
    spine_chain = trace_spine_chain(root_name, deform_bones)

    # 루트를 스파인에서 분리 (root는 별도 역할)
    if len(spine_chain) > 1:
        spine_body = spine_chain[1:]  # root 제외
    else:
        spine_body = []

    # 스파인에서 head/neck 분리 (구조 기반)
    head_name = None
    neck_bones = []
    spine_only = list(spine_body)

    if len(spine_body) >= 2:
        head_name = spine_body[-1]

        if len(spine_body) >= 3:
            # 구조 기반 neck 감지: head 앞에서 길이/방향 변화가 큰 구간
            core_bones = spine_body[:-2] if len(spine_body) > 3 else spine_body[:1]
            avg_len = (
                sum(deform_bones[n]["length"] for n in core_bones) / len(core_bones)
                if core_bones
                else 1.0
            )

            neck_start = len(spine_body) - 1  # 기본: head만 분리
            for i in range(len(spine_body) - 2, 0, -1):
                bone = deform_bones[spine_body[i]]
                prev_bone = deform_bones[spine_body[i - 1]]
                length_ratio = bone["length"] / avg_len if avg_len > 0 else 1.0
                dot = vec_dot(bone["direction"], prev_bone["direction"])

                # 스파인 대비 짧거나 방향이 크게 변하면 neck
                is_neck = (length_ratio < 0.7) or (dot < 0.7 and length_ratio < 1.0)
                if is_neck:
                    neck_start = i
                else:
                    break

            spine_only = spine_body[:neck_start]
            neck_bones = spine_body[neck_start:-1]

            # 최소 1개 spine 본 보장
            if not spine_only and neck_bones:
                spine_only = [neck_bones[0]]
                neck_bones = neck_bones[1:]
        else:
            spine_only = spine_body[:-1]

    # 4. 다리 찾기
    branches = find_downward_branches(spine_chain, deform_bones)
    legs = classify_legs(branches, spine_chain, deform_bones)

    # 4b. 다리/발 자동 분리
    leg_foot_pairs = {}
    for key in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
        if legs.get(key):
            leg_part, foot_part = split_leg_foot(legs[key], deform_bones)
            legs[key] = leg_part
            if foot_part:
                foot_key = key.replace("_leg_", "_foot_")
                leg_foot_pairs[foot_key] = foot_part

    # 5. 꼬리 찾기
    tail_chain = find_tail_chain(root_name, spine_chain, deform_bones)

    # 5b. IK pole vector 탐색 (전체 본에서, deform 여부 무관)
    pole_vectors = find_pole_vectors(all_bones, legs, leg_foot_pairs)

    # 6. 얼굴 특징 찾기 (ear 분리)
    face_features = (
        find_head_features(head_name, deform_bones)
        if head_name
        else {"face_bones": [], "ear_l": [], "ear_r": []}
    )

    # 7. 매핑된/미매핑 본 분류
    mapped_bones = set()
    mapped_bones.add(root_name)
    mapped_bones.update(spine_only)
    mapped_bones.update(neck_bones)
    if head_name:
        mapped_bones.add(head_name)
    for key in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
        if legs.get(key):
            mapped_bones.update(legs[key])
    for _key, foot_bones in leg_foot_pairs.items():
        mapped_bones.update(foot_bones)
    if tail_chain:
        mapped_bones.update(tail_chain)
    # face_bones는 매핑하지 않음 — unmapped에 포함시켜 cc_ 커스텀 본으로 처리
    mapped_bones.update(face_features.get("ear_l", []))
    mapped_bones.update(face_features.get("ear_r", []))

    unmapped = [name for name in deform_bones if name not in mapped_bones]

    # 8. 결과 구성
    chains = {}
    chains["root"] = {"bones": [root_name], "confidence": root_confidence}

    if spine_only:
        chains["spine"] = {"bones": spine_only, "confidence": 0.9}
    if neck_bones:
        chains["neck"] = {"bones": neck_bones, "confidence": 0.85}
    if head_name:
        chains["head"] = {"bones": [head_name], "confidence": 0.95}

    for key in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
        if legs.get(key):
            chains[key] = {"bones": legs[key], "confidence": 0.9}

    for key, foot_bones in leg_foot_pairs.items():
        chains[key] = {"bones": foot_bones, "confidence": 0.85}

    if tail_chain:
        chains["tail"] = {"bones": tail_chain, "confidence": 0.85}

    # ear 독립 역할
    if face_features.get("ear_l"):
        chains["ear_l"] = {"bones": face_features["ear_l"], "confidence": 0.9}
    if face_features.get("ear_r"):
        chains["ear_r"] = {"bones": face_features["ear_r"], "confidence": 0.9}

    # 전체 신뢰도
    if chains:
        avg_confidence = sum(c["confidence"] for c in chains.values()) / len(chains)
    else:
        avg_confidence = 0

    return {
        "source_armature": armature_obj.name,
        "chains": chains,
        "unmapped": unmapped,
        "confidence": round(avg_confidence, 2),
        "bone_data": deform_bones,  # 위치 정보 포함
        "pole_vectors": pole_vectors,  # IK pole vector 위치
        "preview_parent_overrides": build_preview_parent_overrides(unmapped, original_deform_bones),
        "excluded_zero_weight": excluded_zero_weight,
    }


# ═══════════════════════════════════════════════════════════════
# classify_legs — analyze_skeleton 내부에서 사용
# ═══════════════════════════════════════════════════════════════
# skeleton_detection 에서 가져오되, 이 모듈의 네임스페이스에도 존재해야 함
from skeleton_detection import classify_legs

# ═══════════════════════════════════════════════════════════════
# Preview Armature 생성
# ═══════════════════════════════════════════════════════════════


def create_preview_armature(source_obj, analysis):
    """
    소스 deform 본을 복제하여 Preview Armature를 생성.
    역할별로 본 그룹 + 색상을 설정.

    Args:
        source_obj: 소스 Armature 오브젝트
        analysis: analyze_skeleton() 결과

    Returns:
        bpy.types.Object: 생성된 Preview Armature 오브젝트
    """
    bone_data = analysis.get("bone_data", {})
    chains = analysis.get("chains", {})
    unmapped_list = analysis.get("unmapped", [])
    preview_parent_overrides = analysis.get("preview_parent_overrides", {})

    if not bone_data:
        return None

    # 본 이름 → 역할 매핑 구성
    bone_to_role = {}
    for role, chain_info in chains.items():
        for bone_name in chain_info["bones"]:
            bone_to_role[bone_name] = role
    for bone_name in unmapped_list:
        bone_to_role[bone_name] = "unmapped"

    # Object 모드 확보
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # 새 Armature 데이터 생성
    arm_data = bpy.data.armatures.new(f"{source_obj.name}_preview")
    arm_data.display_type = "OCTAHEDRAL"
    preview_obj = bpy.data.objects.new(f"{source_obj.name}_preview", arm_data)

    # 씬에 추가
    bpy.context.collection.objects.link(preview_obj)

    # 소스와 같은 위치/회전/스케일
    preview_obj.matrix_world = source_obj.matrix_world.copy()

    # Edit Mode 진입하여 본 생성
    bpy.ops.object.select_all(action="DESELECT")
    preview_obj.select_set(True)
    bpy.context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = preview_obj.data.edit_bones
    preview_matrix_inv = preview_obj.matrix_world.inverted()

    # 소스에서 Edit Mode 본 데이터 읽기 (bone_data에 이미 월드 좌표 있음)
    # deform 본만 생성
    created_bones = {}
    for bone_name, binfo in bone_data.items():
        ebone = edit_bones.new(bone_name)

        # 월드 좌표 → Preview 로컬 좌표
        from mathutils import Vector

        world_head = Vector(binfo["head"])
        world_tail = Vector(binfo["tail"])
        ebone.head = preview_matrix_inv @ world_head
        ebone.tail = preview_matrix_inv @ world_tail
        ebone.roll = binfo["roll"]
        ebone.use_deform = True

        created_bones[bone_name] = ebone

    # 부모-자식 관계 설정
    for bone_name, binfo in bone_data.items():
        parent_name = (
            preview_parent_overrides[bone_name]
            if bone_name in preview_parent_overrides
            else binfo["parent"]
        )
        if parent_name and parent_name in created_bones:
            ebone = created_bones[bone_name]
            parent_ebone = created_bones[parent_name]
            ebone.parent = parent_ebone

            # 연결 여부: head가 부모 tail에 충분히 가까우면 connected
            if (ebone.head - parent_ebone.tail).length < 0.001:
                ebone.use_connect = True

    # neck 역할이 없고 head가 spine 끝에 바로 붙어 있으면 preview에서 virtual neck 생성
    has_neck_chain = bool(chains.get("neck", {}).get("bones"))
    head_chain = chains.get("head", {}).get("bones", [])
    spine_chain = chains.get("spine", {}).get("bones", [])
    if (not has_neck_chain) and head_chain and spine_chain:
        head_name = head_chain[0]
        head_ebone = created_bones.get(head_name)
        if head_ebone and head_ebone.parent:
            original_head = head_ebone.head.copy()
            original_tail = head_ebone.tail.copy()
            head_vector = original_tail - original_head

            if head_vector.length > 0.001:
                split_point = original_head.lerp(original_tail, VIRTUAL_NECK_RATIO)
                parent_ebone = head_ebone.parent
                original_connect = head_ebone.use_connect

                neck_ebone = edit_bones.new(VIRTUAL_NECK_BONE)
                neck_ebone.head = original_head
                neck_ebone.tail = split_point
                neck_ebone.roll = head_ebone.roll
                neck_ebone.use_deform = True
                neck_ebone.parent = parent_ebone
                neck_ebone.use_connect = original_connect

                head_ebone.head = split_point
                head_ebone.parent = neck_ebone
                head_ebone.use_connect = True

                created_bones[VIRTUAL_NECK_BONE] = neck_ebone
                bone_to_role[VIRTUAL_NECK_BONE] = "neck"

    bpy.ops.object.mode_set(mode="OBJECT")

    # 본 그룹 + 색상 설정 (Pose Mode에서)
    bpy.ops.object.mode_set(mode="POSE")

    # Blender 4.x: bone_color 사용 (bone_groups 대신)
    # 아래에서 개별 본에 색상 직접 설정

    # 각 본에 역할 커스텀 프로퍼티 + 색상 설정
    for bone_name in created_bones:
        pbone = preview_obj.pose.bones.get(bone_name)
        if pbone is None:
            continue

        role = bone_to_role.get(bone_name, "unmapped")
        color = ROLE_COLORS.get(role, ROLE_COLORS["unmapped"])

        # 역할 커스텀 프로퍼티 저장
        pbone[ROLE_PROP_KEY] = role

        # Blender 4.x 본 색상 설정
        pbone.color.palette = "CUSTOM"
        pbone.color.custom.normal = color
        pbone.color.custom.select = tuple(min(c + 0.3, 1.0) for c in color)
        pbone.color.custom.active = tuple(min(c + 0.5, 1.0) for c in color)

    bpy.ops.object.mode_set(mode="OBJECT")

    return preview_obj


def create_preview_from_def_bones(source_obj, analysis):
    """DEF 본 기반 Preview Armature 생성.

    소스 아마추어에 이미 생성된 DEF-* 본의 clean hierarchy를 반영하여
    Preview를 만든다. 본 이름에서 DEF- 접두사를 제거하여 downstream 호환성 유지.
    unmapped 본(eye, jaw 등)은 DEF에 없으므로 원본 deform 본에서 복사.

    Args:
        source_obj: DEF 본이 생성된 소스 Armature 오브젝트
        analysis: analyze_skeleton() 결과

    Returns:
        bpy.types.Object: 생성된 Preview Armature 오브젝트
    """
    from mathutils import Vector

    from arp_def_separator import DEF_PREFIX

    chains = analysis.get("chains", {})
    unmapped_list = analysis.get("unmapped", [])
    bone_data = analysis.get("bone_data", {})

    if not bone_data:
        return None

    # 역할 매핑 구성
    bone_to_role = {}
    for role, chain_info in chains.items():
        for bone_name in chain_info["bones"]:
            bone_to_role[bone_name] = role
    for bone_name in unmapped_list:
        bone_to_role[bone_name] = "unmapped"

    # Object 모드 확보
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    # 새 Armature 데이터 생성
    arm_data = bpy.data.armatures.new(f"{source_obj.name}_preview")
    arm_data.display_type = "OCTAHEDRAL"
    preview_obj = bpy.data.objects.new(f"{source_obj.name}_preview", arm_data)
    bpy.context.collection.objects.link(preview_obj)
    preview_obj.matrix_world = source_obj.matrix_world.copy()

    # ── 소스 Edit Mode: DEF 본 + unmapped 원본 본 데이터 수집 ──
    bpy.ops.object.select_all(action="DESELECT")
    source_obj.select_set(True)
    bpy.context.view_layer.objects.active = source_obj
    bpy.ops.object.mode_set(mode="EDIT")

    src_edit = source_obj.data.edit_bones
    src_matrix = source_obj.matrix_world

    # DEF 본 수집 (이름에서 DEF- 제거)
    def_bone_data = {}  # {stripped_name: {head, tail, roll, parent_stripped}}
    for eb in src_edit:
        if not eb.name.startswith(DEF_PREFIX):
            continue
        stripped = eb.name[len(DEF_PREFIX) :]
        parent_stripped = None
        if eb.parent and eb.parent.name.startswith(DEF_PREFIX):
            parent_stripped = eb.parent.name[len(DEF_PREFIX) :]
        def_bone_data[stripped] = {
            "head": src_matrix @ eb.head.copy(),
            "tail": src_matrix @ eb.tail.copy(),
            "roll": eb.roll,
            "parent": parent_stripped,
        }

    # unmapped 본 수집 (DEF에 없는 원본 deform 본)
    unmapped_bone_data = {}
    for bone_name in unmapped_list:
        if bone_name in def_bone_data:
            continue  # DEF에 이미 있으면 스킵
        eb = src_edit.get(bone_name)
        if eb is None:
            continue
        # 부모 결정: 원본 부모가 DEF에 있으면 해당 본, 아니면 원본 계층 추적
        parent_name = None
        parent_eb = eb.parent
        while parent_eb:
            candidate = parent_eb.name
            if candidate in def_bone_data:
                parent_name = candidate
                break
            # DEF- 접두사 본의 stripped 이름도 확인
            if candidate.startswith(DEF_PREFIX):
                stripped_candidate = candidate[len(DEF_PREFIX) :]
                if stripped_candidate in def_bone_data:
                    parent_name = stripped_candidate
                    break
            parent_eb = parent_eb.parent

        unmapped_bone_data[bone_name] = {
            "head": src_matrix @ eb.head.copy(),
            "tail": src_matrix @ eb.tail.copy(),
            "roll": eb.roll,
            "parent": parent_name,
        }

    bpy.ops.object.mode_set(mode="OBJECT")

    # ── Preview Edit Mode: 본 생성 ──
    bpy.ops.object.select_all(action="DESELECT")
    preview_obj.select_set(True)
    bpy.context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = preview_obj.data.edit_bones
    preview_matrix_inv = preview_obj.matrix_world.inverted()

    created_bones = {}

    # DEF 기반 본 생성 (원본 이름으로)
    for bone_name, binfo in def_bone_data.items():
        ebone = edit_bones.new(bone_name)
        ebone.head = preview_matrix_inv @ binfo["head"]
        ebone.tail = preview_matrix_inv @ binfo["tail"]
        ebone.roll = binfo["roll"]
        ebone.use_deform = True
        created_bones[bone_name] = ebone

    # unmapped 본 생성
    for bone_name, binfo in unmapped_bone_data.items():
        ebone = edit_bones.new(bone_name)
        ebone.head = preview_matrix_inv @ binfo["head"]
        ebone.tail = preview_matrix_inv @ binfo["tail"]
        ebone.roll = binfo["roll"]
        ebone.use_deform = True
        created_bones[bone_name] = ebone

    # 부모-자식 관계 설정
    all_bone_data = {**def_bone_data, **unmapped_bone_data}
    for bone_name, binfo in all_bone_data.items():
        parent_name = binfo["parent"]
        if parent_name and parent_name in created_bones:
            ebone = created_bones[bone_name]
            parent_ebone = created_bones[parent_name]
            ebone.parent = parent_ebone
            if (ebone.head - parent_ebone.tail).length < 0.001:
                ebone.use_connect = True

    # Virtual neck 생성 (기존 로직과 동일)
    has_neck_chain = bool(chains.get("neck", {}).get("bones"))
    head_chain = chains.get("head", {}).get("bones", [])
    spine_chain = chains.get("spine", {}).get("bones", [])
    if (not has_neck_chain) and head_chain and spine_chain:
        head_name = head_chain[0]
        head_ebone = created_bones.get(head_name)
        if head_ebone and head_ebone.parent:
            original_head = head_ebone.head.copy()
            original_tail = head_ebone.tail.copy()
            head_vector = original_tail - original_head

            if head_vector.length > 0.001:
                split_point = original_head.lerp(original_tail, VIRTUAL_NECK_RATIO)
                parent_ebone = head_ebone.parent
                original_connect = head_ebone.use_connect

                neck_ebone = edit_bones.new(VIRTUAL_NECK_BONE)
                neck_ebone.head = original_head
                neck_ebone.tail = split_point
                neck_ebone.roll = head_ebone.roll
                neck_ebone.use_deform = True
                neck_ebone.parent = parent_ebone
                neck_ebone.use_connect = original_connect

                head_ebone.head = split_point
                head_ebone.parent = neck_ebone
                head_ebone.use_connect = True

                created_bones[VIRTUAL_NECK_BONE] = neck_ebone
                bone_to_role[VIRTUAL_NECK_BONE] = "neck"

    bpy.ops.object.mode_set(mode="OBJECT")

    # ── Pose Mode: 역할 + 색상 설정 ──
    bpy.ops.object.mode_set(mode="POSE")

    for bone_name in created_bones:
        pbone = preview_obj.pose.bones.get(bone_name)
        if pbone is None:
            continue

        role = bone_to_role.get(bone_name, "unmapped")
        color = ROLE_COLORS.get(role, ROLE_COLORS["unmapped"])

        pbone[ROLE_PROP_KEY] = role

        pbone.color.palette = "CUSTOM"
        pbone.color.custom.normal = color
        pbone.color.custom.select = tuple(min(c + 0.3, 1.0) for c in color)
        pbone.color.custom.active = tuple(min(c + 0.5, 1.0) for c in color)

    bpy.ops.object.mode_set(mode="OBJECT")

    return preview_obj


# ═══════════════════════════════════════════════════════════════
# chains / roles 유틸리티
# ═══════════════════════════════════════════════════════════════


def chains_to_flat_roles(analysis):
    """analysis chains -> flat {role: [bone_names]} 변환.

    analyze_skeleton()의 chains 형태:
        {role: {"bones": [...], "confidence": float}}
    를 create_def_bones / resolve_def_parents가 기대하는:
        {role: [bone_names]}
    로 변환한다.  unmapped 목록도 포함.
    """
    roles = {}
    for role, chain_info in analysis.get("chains", {}).items():
        roles[role] = list(chain_info["bones"])
    unmapped = analysis.get("unmapped", [])
    if unmapped:
        roles["unmapped"] = list(unmapped)
    return roles


def read_preview_roles(preview_obj):
    """
    Preview Armature의 본 역할 정보를 읽어서 analysis 형식으로 반환.
    사용자가 수정한 역할을 반영.

    Returns:
        dict: {role: [bone_names], ...}
    """
    roles = defaultdict(list)

    for pbone in preview_obj.pose.bones:
        role = pbone.get(ROLE_PROP_KEY, "unmapped")
        roles[role].append(pbone.name)

    # 각 역할 내에서 하이어라키 순서(부모->자식)로 정렬
    for role in roles:
        bone_names = roles[role]

        # depth 기준 정렬
        def get_depth(name):
            depth = 0
            bone = preview_obj.data.bones.get(name)
            while bone and bone.parent:
                depth += 1
                bone = bone.parent
            return depth

        roles[role] = sorted(bone_names, key=get_depth)

    return dict(roles)


def preview_to_analysis(preview_obj):
    """
    Preview Armature를 analysis dict로 변환.
    사용자 수정이 반영된 최종 매핑 생성에 사용.

    Returns:
        dict: analyze_skeleton() 결과와 동일한 형식
    """
    roles = read_preview_roles(preview_obj)

    chains = {}
    unmapped = []

    for role, bone_names in roles.items():
        if role == "unmapped":
            unmapped = bone_names
        else:
            chains[role] = {
                "bones": bone_names,
                "confidence": 1.0,  # 사용자 확인 완료
            }

    # bone_data 추출 (위치 정보)
    bone_data = extract_bone_data(preview_obj)
    deform_bones = {name: bone_data[name] for name in bone_data if bone_data[name]["is_deform"]}

    return {
        "source_armature": preview_obj.name,
        "chains": chains,
        "unmapped": unmapped,
        "confidence": 1.0,
        "bone_data": deform_bones,
    }


# ═══════════════════════════════════════════════════════════════
# 하위 호환: skeleton_detection, arp_mapping의 public 심볼 재수출
# 기존 from skeleton_analyzer import X 구문이 계속 동작하도록 함
# ═══════════════════════════════════════════════════════════════
from arp_mapping import *  # noqa: F403
from skeleton_detection import *  # noqa: F403

"""
DEF 본 분리 모듈
================
소스 아마추어의 deform 본마다 DEF-{name} 복제본을 만들어
역할 기반 해부학적 계층 구조를 구축한다.

설계: docs/DEF_BoneSeparator.md

핵심 결정:
- DEF 본은 use_deform=False (리타겟 전용)
- 원본 본은 use_deform 유지 (메시 변형 담당)
- VG rename 안 함
- Copy Transforms: DEF → 원본 (WORLD space)
- bone_pairs에서 src_name은 DEF-{원본이름}
"""

import bpy
from mathutils import Vector

from arp_utils import log

DEF_PREFIX = "DEF-"
DEF_COLLECTION_NAME = "DEF"


# ═══════════════════════════════════════════════════════════════
# 역할 기반 부모 결정 (순수 함수 — Blender 의존 없음)
# ═══════════════════════════════════════════════════════════════

# 체인 역할 그룹: 역할 내 본 순서대로 이전 DEF 본이 부모
_CHAIN_ROLES = {"spine", "neck", "tail", "ear_l", "ear_r"}

# 다리 역할: 첫 본(thigh/shoulder)의 부모가 body 루트에 붙음
_LEG_ROLES = {
    "back_leg_l",
    "back_leg_r",
    "front_leg_l",
    "front_leg_r",
}

# foot 역할: 해당 leg 마지막 DEF 본에 붙음
_FOOT_ROLES = {
    "back_foot_l",
    "back_foot_r",
    "front_foot_l",
    "front_foot_r",
}

# foot → leg 매핑
_FOOT_TO_LEG = {
    "back_foot_l": "back_leg_l",
    "back_foot_r": "back_leg_r",
    "front_foot_l": "front_leg_l",
    "front_foot_r": "front_leg_r",
}

# leg → 부모 루트 결정
_LEG_PARENT_ROLE = {
    "back_leg_l": "root",
    "back_leg_r": "root",
    "front_leg_l": "spine",  # spine 마지막 DEF 본 (chest)
    "front_leg_r": "spine",
}


def resolve_def_parents(roles, armature_root=None):
    """역할 맵에서 각 본의 DEF 부모 이름을 결정한다.

    Args:
        roles: {role: [bone_names]} — read_preview_roles 결과
        armature_root: 소스 아마추어의 최상위 본 이름 (예: "root").
                       지정하면 DEF-{armature_root}를 최상위로 생성하고,
                       기존 최상위 본들과 unmapped 본들을 그 아래에 배치.

    Returns:
        dict: {bone_name: def_parent_name_or_None}
              def_parent_name은 "DEF-{parent_bone}" 형태이거나
              None(최상위)
    """
    parents = {}

    # 각 역할의 본 리스트를 참조하기 위한 헬퍼
    def _bones(role):
        return roles.get(role, [])

    def _def(name):
        return f"{DEF_PREFIX}{name}"

    # root — 최상위
    root_bones = _bones("root")
    for bone in root_bones:
        parents[bone] = None

    # spine — 첫 본은 root에, 나머지는 이전 spine에
    spine_bones = _bones("spine")
    for i, bone in enumerate(spine_bones):
        if i == 0:
            parents[bone] = _def(root_bones[0]) if root_bones else None
        else:
            parents[bone] = _def(spine_bones[i - 1])

    # neck — 첫 본은 spine 마지막에, 나머지는 이전 neck에
    neck_bones = _bones("neck")
    for i, bone in enumerate(neck_bones):
        if i == 0:
            parents[bone] = _def(spine_bones[-1]) if spine_bones else None
        else:
            parents[bone] = _def(neck_bones[i - 1])

    # head — neck 마지막에
    head_bones = _bones("head")
    neck_last = (
        _def(neck_bones[-1]) if neck_bones else (_def(spine_bones[-1]) if spine_bones else None)
    )
    for bone in head_bones:
        parents[bone] = neck_last

    # tail — 첫 본은 root에, 나머지는 이전 tail에
    tail_bones = _bones("tail")
    for i, bone in enumerate(tail_bones):
        if i == 0:
            parents[bone] = _def(root_bones[0]) if root_bones else None
        else:
            parents[bone] = _def(tail_bones[i - 1])

    # legs — 첫 본은 pelvis(root) 또는 chest(spine 마지막), 체인 내부는 이전 DEF
    for leg_role in sorted(_LEG_ROLES):
        leg_bones = _bones(leg_role)
        parent_role = _LEG_PARENT_ROLE[leg_role]
        if parent_role == "root":
            first_parent = _def(root_bones[0]) if root_bones else None
        else:
            first_parent = _def(spine_bones[-1]) if spine_bones else None

        for i, bone in enumerate(leg_bones):
            if i == 0:
                parents[bone] = first_parent
            else:
                parents[bone] = _def(leg_bones[i - 1])

    # feet — leg 마지막 DEF에 붙고, 체인 내부는 이전 foot DEF
    for foot_role in sorted(_FOOT_ROLES):
        foot_bones = _bones(foot_role)
        leg_role = _FOOT_TO_LEG[foot_role]
        leg_bones = _bones(leg_role)
        first_parent = _def(leg_bones[-1]) if leg_bones else None

        for i, bone in enumerate(foot_bones):
            if i == 0:
                parents[bone] = first_parent
            else:
                parents[bone] = _def(foot_bones[i - 1])

    # ears — head DEF에 붙음, 체인 내부는 이전 ear DEF
    for ear_role in ("ear_l", "ear_r"):
        ear_bones = _bones(ear_role)
        head_parent = _def(head_bones[0]) if head_bones else neck_last

        for i, bone in enumerate(ear_bones):
            if i == 0:
                parents[bone] = head_parent
            else:
                parents[bone] = _def(ear_bones[i - 1])

    # unmapped 본 — armature_root가 지정되면 DEF 계층에 포함
    unmapped_bones = _bones("unmapped")
    if armature_root and unmapped_bones:
        for bone in unmapped_bones:
            parents[bone] = _def(armature_root)

    # armature_root 처리: 최상위 DEF 본으로 추가,
    # 기존 최상위(None) 본들을 그 아래에 재배치
    if armature_root:
        for bone in list(parents):
            if parents[bone] is None and bone != armature_root:
                parents[bone] = _def(armature_root)
        parents[armature_root] = None

    return parents


# ═══════════════════════════════════════════════════════════════
# Blender 연동: DEF 본 생성 + 계층 + constraint + collection
# ═══════════════════════════════════════════════════════════════


def _purge_existing_def_bones(source_obj):
    """기존 DEF 본과 관련 constraint를 모두 제거한다 (멱등성 보장).

    역할 변경 후 재실행 시 오래된 DEF 계층이 남는 것을 방지한다.
    """
    from arp_utils import ensure_object_mode, select_only

    arm = source_obj.data
    existing_def = [b.name for b in arm.bones if b.name.startswith(DEF_PREFIX)]
    if not existing_def:
        return

    log(f"DEF 본 퍼지: 기존 {len(existing_def)}개 제거")

    # Pose Mode: DEF 본의 constraint 제거
    bpy.context.view_layer.objects.active = source_obj
    ensure_object_mode()
    select_only(source_obj)
    bpy.ops.object.mode_set(mode="POSE")
    for def_name in existing_def:
        pbone = source_obj.pose.bones.get(def_name)
        if pbone:
            for ct in list(pbone.constraints):
                pbone.constraints.remove(ct)

    # Edit Mode: DEF 본 삭제
    bpy.ops.object.mode_set(mode="EDIT")
    edit_bones = arm.edit_bones
    for def_name in existing_def:
        eb = edit_bones.get(def_name)
        if eb:
            edit_bones.remove(eb)

    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"  DEF 본 퍼지 완료: {len(existing_def)}개 삭제")


def create_def_bones(source_obj, roles):
    """소스 아마추어에 DEF 본 계층을 생성한다.

    Args:
        source_obj: 소스 아마추어 오브젝트
        roles: {role: [bone_names]} — read_preview_roles 결과

    Returns:
        set: 생성된 DEF 본 이름 집합
    """
    if source_obj is None or source_obj.type != "ARMATURE":
        log("DEF 분리: 소스 아마추어 없음, 스킵", "WARN")
        return set()

    arm = source_obj.data

    # 소스 아마추어의 최상위 본 탐색
    armature_root = None
    for bone in arm.bones:
        if bone.parent is None:
            armature_root = bone.name
            break

    parent_map = resolve_def_parents(roles, armature_root=armature_root)

    # unmapped 본의 부모를 소스 계층에서 탐색하여 보정
    # resolve_def_parents는 순수 함수라 소스 계층을 모르므로
    # DEF-root를 기본 부모로 넣는다. 여기서 실제 조상을 추적.
    unmapped = roles.get("unmapped", [])
    if unmapped and armature_root:
        mapped_bones = set(parent_map) - set(unmapped) - {armature_root}
        for bone_name in unmapped:
            src_bone = arm.bones.get(bone_name)
            if src_bone is None:
                continue
            # 소스 계층을 위로 탐색 → DEF가 존재하는 첫 조상 찾기
            ancestor = src_bone.parent
            while ancestor:
                if ancestor.name in mapped_bones:
                    parent_map[bone_name] = f"{DEF_PREFIX}{ancestor.name}"
                    break
                ancestor = ancestor.parent
            # 조상을 못 찾으면 DEF-root 유지 (resolve_def_parents 기본값)

    if not parent_map:
        log("DEF 분리: 역할 매핑 비어있음, 스킵", "WARN")
        return set()

    # ── 멱등성: 기존 DEF 본 제거 후 재생성 ──
    _purge_existing_def_bones(source_obj)

    # 생성 대상 필터링
    bones_to_create = {}
    for bone_name, def_parent in parent_map.items():
        def_name = f"{DEF_PREFIX}{bone_name}"
        if bone_name.startswith(DEF_PREFIX):
            log(f"  DEF 스킵 (원본이 DEF-): {bone_name}", "DEBUG")
            continue
        # 소스에 실제로 존재하는 본인지 확인
        if arm.bones.get(bone_name) is None:
            log(f"  DEF 스킵 (본 미발견): {bone_name}", "DEBUG")
            continue
        bones_to_create[bone_name] = (def_name, def_parent)

    if not bones_to_create:
        log("DEF 분리: 생성할 본 없음")
        return set()

    log(f"DEF 본 생성 시작: {len(bones_to_create)}개")

    # ── Edit Mode: 본 생성 + 위치 복사 + 계층 설정 ──
    from arp_utils import ensure_object_mode, select_only

    bpy.context.view_layer.objects.active = source_obj
    ensure_object_mode()
    select_only(source_obj)
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = arm.edit_bones
    created_names = set()

    # 1단계: DEF 본 생성 + 위치 복사
    for bone_name, (def_name, _def_parent) in bones_to_create.items():
        src_eb = edit_bones.get(bone_name)
        if src_eb is None:
            continue

        def_eb = edit_bones.new(def_name)
        def_eb.head = src_eb.head.copy()
        def_eb.tail = src_eb.tail.copy()
        def_eb.roll = src_eb.roll
        def_eb.use_deform = False  # 리타겟 전용, 메시 변형 안 함
        def_eb.use_connect = False
        created_names.add(def_name)

    # 2단계: 부모-자식 계층 설정 (모든 본이 생성된 후)
    for _bone_name, (def_name, def_parent) in bones_to_create.items():
        def_eb = edit_bones.get(def_name)
        if def_eb is None:
            continue

        if def_parent is not None:
            parent_eb = edit_bones.get(def_parent)
            if parent_eb is not None:
                def_eb.parent = parent_eb
            else:
                log(f"  DEF 부모 미발견: {def_name} → {def_parent}", "WARN")
        # def_parent is None → root, 부모 없음

    bpy.ops.object.mode_set(mode="OBJECT")

    # ── Pose Mode: Copy Transforms constraint 추가 ──
    ensure_object_mode()
    select_only(source_obj)
    bpy.ops.object.mode_set(mode="POSE")

    for bone_name in bones_to_create:
        def_name = f"{DEF_PREFIX}{bone_name}"
        if def_name not in created_names:
            continue

        pbone = source_obj.pose.bones.get(def_name)
        if pbone is None:
            continue

        ct = pbone.constraints.new("COPY_TRANSFORMS")
        ct.name = "DEF_CopyTransforms"
        ct.target = source_obj
        ct.subtarget = bone_name
        ct.target_space = "WORLD"
        ct.owner_space = "WORLD"

    bpy.ops.object.mode_set(mode="OBJECT")

    # ── Bone Collection 생성 ──
    _ensure_def_collection(arm, created_names)

    log(f"DEF 본 생성 완료: {len(created_names)}개")
    return created_names


def _ensure_def_collection(armature_data, def_bone_names):
    """DEF bone collection을 생성하고 DEF 본을 할당한다."""
    # Blender 4.0+ BoneCollection API
    if not hasattr(armature_data, "collections"):
        log("DEF collection: BoneCollection API 미지원, 스킵", "WARN")
        return

    # 기존 DEF 컬렉션 찾기 또는 생성
    def_coll = armature_data.collections.get(DEF_COLLECTION_NAME)
    if def_coll is None:
        def_coll = armature_data.collections.new(DEF_COLLECTION_NAME)
        log(f"  Bone Collection '{DEF_COLLECTION_NAME}' 생성")

    # DEF 본 할당
    assigned = 0
    for bone_name in def_bone_names:
        bone = armature_data.bones.get(bone_name)
        if bone is not None:
            def_coll.assign(bone)
            assigned += 1

    log(f"  DEF collection 할당: {assigned}개")

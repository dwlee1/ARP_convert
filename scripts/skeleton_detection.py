"""
스켈레톤 구조 감지 모듈
=======================
벡터 유틸리티, 상수, 체인 감지 등 ARP에 의존하지 않는
순수 구조 분석 로직을 담당한다.

skeleton_analyzer.py에서 분리됨.
"""

import json
import math
import os
from collections import defaultdict

import bpy

DEBUG = os.environ.get("BLENDER_RIG_DEBUG", "").lower() in ("1", "true")

# __all__ 정의: from skeleton_detection import * 에서 _접두사 심볼도 포함
__all__ = [
    "BACKWARD_THRESHOLD",
    "CC_NAME_PATTERNS",
    "CENTER_X_RATIO",
    # 상수
    "DEBUG",
    "DOWNWARD_THRESHOLD",
    "EAR_KEYWORDS",
    "FACE_BONE_KEYWORDS",
    "FACE_ONLY_KEYWORDS",
    "LATERAL_THRESHOLD",
    "MAX_EAR_CHAIN_LENGTH",
    "MIN_LEG_CHAIN_LENGTH",
    "POLE_KEYWORDS",
    "ROLE_COLORS",
    "ROLE_PROP_KEY",
    "ROOT_NAME_HINTS",
    "UPWARD_THRESHOLD",
    "_extract_bone_from_data_path",
    # Shape key
    "_extract_shape_key_name",
    # 공간 재구성
    "_reconstruct_spatial_hierarchy",
    "build_preview_parent_overrides",
    "classify_legs",
    # 구조 식별
    "count_descendants",
    # 본 추출
    "extract_bone_data",
    "filter_deform_bones",
    "find_downward_branches",
    "find_head_features",
    # Pole / Head
    "find_pole_vectors",
    "find_root_bone",
    "find_tail_chain",
    "get_weighted_bone_names",
    # 하이어라키
    "order_bones_by_hierarchy",
    "scan_shape_key_drivers",
    "split_leg_foot",
    "trace_chain",
    "trace_spine_chain",
    "vec_add",
    "vec_avg",
    "vec_dot",
    "vec_length",
    "vec_normalize",
    "vec_scale",
    # 벡터 유틸리티
    "vec_sub",
]

# ═══════════════════════════════════════════════════════════════
# 상수
# ═══════════════════════════════════════════════════════════════

# 방향 임계값 (Blender 좌표계: Z=위, Y=앞, X=좌우)
UPWARD_THRESHOLD = 0.3
DOWNWARD_THRESHOLD = -0.3
BACKWARD_THRESHOLD = -0.3
CENTER_X_RATIO = 0.5  # avg_bone_length에 곱하여 L/R 분류 임계값 계산
LATERAL_THRESHOLD = 0.1
MIN_LEG_CHAIN_LENGTH = 2
MAX_EAR_CHAIN_LENGTH = 3

# 얼굴 본 키워드 (스파인 후보 제외용)
FACE_BONE_KEYWORDS = ["eye", "ear", "jaw", "mouth", "tongue"]

# cc_ 커스텀 본 강제 전환 패턴 — 이 패턴이 포함된 본은 어떤 역할이든 cc_ 후보
CC_NAME_PATTERNS = ["eye", "jaw", "mouth", "tongue", "food"]

ROOT_NAME_HINTS = {"pelvis", "hips", "hip", "root"}

# 역할 커스텀 프로퍼티 키
ROLE_PROP_KEY = "arp_role"

# 역할별 본 그룹 색상 (Blender 테마 색상 인덱스)
ROLE_COLORS = {
    "root": (1.0, 0.9, 0.0),  # 노랑
    "spine": (0.2, 0.4, 1.0),  # 파랑
    "neck": (0.2, 0.4, 1.0),  # 파랑
    "head": (0.2, 0.4, 1.0),  # 파랑
    "back_leg_l": (1.0, 0.2, 0.2),  # 빨강
    "back_leg_r": (1.0, 0.2, 0.2),  # 빨강
    "back_foot_l": (0.7, 0.1, 0.1),  # 진빨강
    "back_foot_r": (0.7, 0.1, 0.1),  # 진빨강
    "front_leg_l": (0.2, 0.8, 0.2),  # 초록
    "front_leg_r": (0.2, 0.8, 0.2),  # 초록
    "front_foot_l": (0.1, 0.5, 0.1),  # 진초록
    "front_foot_r": (0.1, 0.5, 0.1),  # 진초록
    "ear_l": (0.0, 0.8, 0.8),  # 시안
    "ear_r": (0.0, 0.8, 0.8),  # 시안
    "tail": (1.0, 0.5, 0.0),  # 주황
    "trajectory": (0.8, 0.8, 0.0),  # 연노랑
    "unmapped": (0.5, 0.5, 0.5),  # 회색
}


# ═══════════════════════════════════════════════════════════════
# 벡터 유틸리티 (외부 의존성 없음)
# ═══════════════════════════════════════════════════════════════


def vec_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vec_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vec_scale(v, s):
    return (v[0] * s, v[1] * s, v[2] * s)


def vec_length(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def vec_normalize(v):
    l = vec_length(v)
    if l < 1e-8:
        return (0, 0, 0)
    return (v[0] / l, v[1] / l, v[2] / l)


def vec_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vec_avg(vectors):
    n = len(vectors)
    if n == 0:
        return (0, 0, 0)
    s = (0, 0, 0)
    for v in vectors:
        s = vec_add(s, v)
    return vec_scale(s, 1.0 / n)


# ═══════════════════════════════════════════════════════════════
# 하이어라키 유틸리티
# ═══════════════════════════════════════════════════════════════


def order_bones_by_hierarchy(bone_names, bone_data):
    """
    parent -> child 순서를 보장하도록 본 이름을 하이어라키 기준으로 정렬.
    같은 depth의 형제 순서는 입력 순서를 유지한다.

    Args:
        bone_names: 정렬할 본 이름 리스트
        bone_data: {bone_name: {'parent': parent_name, ...}} 형식의 dict

    Returns:
        list[str]: 부모가 항상 자식보다 먼저 오는 순서
    """
    if not bone_names:
        return []

    ordered_input = []
    seen = set()
    for bone_name in bone_names:
        if bone_name and bone_name not in seen:
            ordered_input.append(bone_name)
            seen.add(bone_name)

    index_map = {name: idx for idx, name in enumerate(ordered_input)}
    bone_set = set(ordered_input)
    children_map = defaultdict(list)
    roots = []
    missing = []

    for bone_name in ordered_input:
        info = bone_data.get(bone_name)
        if info is None:
            missing.append(bone_name)
            continue

        parent_name = info.get("parent")
        if parent_name in bone_set and parent_name != bone_name:
            children_map[parent_name].append(bone_name)
        else:
            roots.append(bone_name)

    def sort_key(name):
        return (index_map.get(name, 10**9), name)

    roots.sort(key=sort_key)
    for child_names in children_map.values():
        child_names.sort(key=sort_key)

    ordered = []
    visited = set()

    def visit(bone_name):
        if bone_name in visited:
            return
        visited.add(bone_name)
        ordered.append(bone_name)
        for child_name in children_map.get(bone_name, []):
            visit(child_name)

    for bone_name in roots:
        visit(bone_name)

    remaining = [name for name in ordered_input if name not in visited and name not in missing]
    remaining.sort(key=sort_key)
    for bone_name in remaining:
        visit(bone_name)

    for bone_name in missing:
        if bone_name not in visited:
            ordered.append(bone_name)
            visited.add(bone_name)

    return ordered


def build_preview_parent_overrides(bone_names, original_bone_data):
    """
    Preview 생성 시 특정 본들의 부모를 원본 deform 하이어라키 기준으로 강제한다.

    Args:
        bone_names: override 대상 본 이름 리스트
        original_bone_data: spatial 재구성 전 deform bone_data

    Returns:
        dict: {bone_name: parent_name_or_None}
    """
    overrides = {}
    if not bone_names or not original_bone_data:
        return overrides

    valid_bones = set(original_bone_data.keys())
    for bone_name in bone_names:
        info = original_bone_data.get(bone_name)
        if info is None:
            continue

        parent_name = info.get("parent")
        if parent_name in valid_bones and parent_name != bone_name:
            overrides[bone_name] = parent_name
        else:
            overrides[bone_name] = None

    return overrides


# ═══════════════════════════════════════════════════════════════
# 본 데이터 추출
# ═══════════════════════════════════════════════════════════════


def extract_bone_data(armature_obj):
    """
    아마추어에서 모든 본의 월드 좌표, 하이어라키, deform 여부를 추출.
    Edit Mode 진입 필요.

    Returns:
        dict: {bone_name: {head, tail, roll, parent, children, is_deform, direction, length}}
    """
    # Object 모드로 전환 (활성 객체 없거나 삭제된 경우 대응)
    try:
        current = bpy.context.view_layer.objects.active
        if current and current.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    except (RuntimeError, ReferenceError):
        pass

    # 아마추어 선택 & 활성화 (select_all도 실패할 수 있음)
    try:
        bpy.ops.object.select_all(action="DESELECT")
    except RuntimeError:
        pass
    armature_obj.hide_set(False)
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode="EDIT")

    world_matrix = armature_obj.matrix_world
    bones = {}

    for ebone in armature_obj.data.edit_bones:
        head_world = world_matrix @ ebone.head.copy()
        tail_world = world_matrix @ ebone.tail.copy()

        head_t = (head_world.x, head_world.y, head_world.z)
        tail_t = (tail_world.x, tail_world.y, tail_world.z)

        direction = vec_normalize(vec_sub(tail_t, head_t))
        length = vec_length(vec_sub(tail_t, head_t))

        bones[ebone.name] = {
            "name": ebone.name,
            "head": head_t,
            "tail": tail_t,
            "roll": ebone.roll,
            "parent": ebone.parent.name if ebone.parent else None,
            "children": [c.name for c in ebone.children],
            "is_deform": ebone.use_deform,
            "direction": direction,
            "length": length,
            "use_connect": ebone.use_connect,
        }

    bpy.ops.object.mode_set(mode="OBJECT")
    return bones


def get_weighted_bone_names(armature_obj, threshold=0.001):
    """
    아마추어에 연결된 메시의 vertex group을 스캔하여
    실제 웨이트가 있는 본 이름 집합을 반환.

    Args:
        armature_obj: 아마추어 오브젝트
        threshold: 최소 웨이트 임계값 (이 값 이하는 무시)

    Returns:
        set[str]: 웨이트가 있는 본 이름 집합. 메시가 없으면 None 반환.
    """
    mesh_children = [
        child for child in bpy.data.objects if child.type == "MESH" and child.parent == armature_obj
    ]
    if not mesh_children:
        return None

    weighted = set()
    for mesh_obj in mesh_children:
        vg_names = {vg.index: vg.name for vg in mesh_obj.vertex_groups}
        for v in mesh_obj.data.vertices:
            for g in v.groups:
                if g.weight > threshold and g.group in vg_names:
                    weighted.add(vg_names[g.group])
    return weighted


def filter_deform_bones(all_bones, weighted_bones=None):
    """
    deform 본만 추출하고, deform 본 간의 하이어라키를 재구성.
    비-deform 중간 본을 건너뛰어 직접적인 부모-자식 관계를 유지.

    Args:
        all_bones: 전체 본 딕셔너리
        weighted_bones: 웨이트가 있는 본 이름 집합 (None이면 웨이트 필터링 안 함)

    Returns:
        tuple: (deform_bones dict, excluded_info list)
            excluded_info: [{"name": str, "parent": str|None}, ...] 웨이트 0 제외 본과
            가장 가까운 포함된 deform 조상 정보
    """
    deform_names = {name for name, b in all_bones.items() if b["is_deform"]}
    excluded_info = []
    if weighted_bones is not None:
        excluded_names = deform_names - weighted_bones
        if excluded_names and DEBUG:
            print(f"[DEBUG] 웨이트 0 deform 본 제외: {sorted(excluded_names)}")
        included = deform_names & weighted_bones
        for name in sorted(excluded_names):
            parent_name = all_bones[name]["parent"]
            while parent_name and parent_name not in included:
                parent_name = all_bones[parent_name]["parent"]
            excluded_info.append({"name": name, "parent": parent_name})
        deform_names = included
    deform_bones = {}

    for name in deform_names:
        b = dict(all_bones[name])

        # 부모 찾기: deform 본인 가장 가까운 조상
        parent_name = b["parent"]
        while parent_name and parent_name not in deform_names:
            parent_name = all_bones[parent_name]["parent"]
        b["parent"] = parent_name

        # 자식 찾기: deform 본인 직접 후손
        deform_children = []
        queue = list(b["children"])
        while queue:
            child_name = queue.pop(0)
            if child_name in deform_names:
                deform_children.append(child_name)
            elif child_name in all_bones:
                queue.extend(all_bones[child_name]["children"])
        b["children"] = deform_children

        deform_bones[name] = b

    return deform_bones, excluded_info


# ═══════════════════════════════════════════════════════════════
# 공간 하이어라키 재구성
# ═══════════════════════════════════════════════════════════════


def _reconstruct_spatial_hierarchy(deform_bones, all_bones, original_hierarchy=None):
    """
    parent=None인 deform 본에 대해 공간 관계로 부모-자식 관계를 보완.

    filter_deform_bones가 non-deform 중간 본을 건너뛰면서
    형제 브랜치 간 연결이 끊어질 수 있음.

    4단계 탐색:
      1) deform 본 tail→head 직접 매칭
      2) all_bones(non-deform 포함) tail→head 매칭 후 deform 조상 추적
      3) deform 본 간 head→head 근접 매칭 (같은 관절에서 분기하는 경우)
      4) 최소 거리 기반 광범위 검색 (사지 연결)
    """
    total = len(deform_bones)
    if total == 0:
        return

    deform_names = set(deform_bones.keys())

    def _find_deform_ancestor(bone_name):
        """all_bones에서 deform 조상을 찾아 올라감."""
        ancestor = all_bones.get(bone_name, {}).get("parent")
        while ancestor:
            if ancestor in deform_names:
                return ancestor
            ancestor = all_bones.get(ancestor, {}).get("parent")
        return None

    # ── Step 0: non-deform 투과 (collapse) ──
    # 원본 계층에서 non-deform 본을 건너뛰어 deform 본 간 부모-자식을 확립.
    # RECON-1(tail→head) 후에 실행되어야 형제 중 연결된 본을 찾을 수 있음.
    def _run_collapse():
        collapse_connected = 0
        for name in list(deform_names):
            bone = deform_bones[name]
            if bone["parent"] is not None:
                continue

            # 1) 원본 계층에서 deform 조상 탐색
            deform_parent = _find_deform_ancestor(name)
            if deform_parent:
                _try_set_parent(name, deform_parent, "collapse")
                collapse_connected += 1
                continue

            # 2) 같은 non-deform 부모를 공유하는 deform 형제 탐색
            orig_parent = all_bones.get(name, {}).get("parent")
            if not orig_parent or orig_parent in deform_names:
                continue

            # 형제 중 이미 트리에 연결된 본 우선, 없으면 가장 가까운 형제
            siblings = [
                sib_name
                for sib_name in deform_names
                if all_bones.get(sib_name, {}).get("parent") == orig_parent and sib_name != name
            ]
            if not siblings:
                continue

            # ROOT_NAME_HINTS 본은 형제의 자식이 되면 안 됨 — 스킵
            name_is_root = any(h in name.lower() for h in ROOT_NAME_HINTS)
            if name_is_root:
                continue

            # 이미 트리에 연결된 형제 우선 (RECON-1/2/3 후이므로 spine 트리 확립됨)
            connected_sibs = [s for s in siblings if deform_bones[s]["parent"] is not None]
            if not connected_sibs:
                # 아직 아무 형제도 tree에 연결되지 않음 → collapse를 skip하고 RECON-4에 맡김.
                # 대칭 쌍(L/R suffix) 본들끼리 collapse로 parent-child가 되는 것을 방지.
                # 예: Fox의 shoulder_L/R이 chest_fk(non-deform)를 공유할 때,
                #     둘 중 하나가 다른 하나의 parent가 되면 앞다리 분기가 1개로 줄어
                #     classify_legs가 front_leg_l/r 모두를 감지하지 못한다.
                continue
            pool = connected_sibs

            best_sib, best_dist = None, float("inf")
            for sib_name in pool:
                dist = vec_length(vec_sub(deform_bones[sib_name]["head"], bone["head"]))
                if dist < best_dist:
                    best_dist = dist
                    best_sib = sib_name
            if best_sib:
                _try_set_parent(name, best_sib, "sibling")
                collapse_connected += 1

        if DEBUG and collapse_connected:
            print(f"  [COLLAPSE] {collapse_connected}개 본 연결됨")
        return collapse_connected > 0

    def _try_set_parent(child_name, parent_name, method):
        """순환 방지 후 부모 설정."""
        if parent_name == child_name:
            return False
        ancestor = parent_name
        visited = set()
        while ancestor and ancestor not in visited:
            if ancestor == child_name:
                print(f"    → 순환 감지 ({method}), 건너뜀")
                return False
            visited.add(ancestor)
            ancestor = deform_bones[ancestor]["parent"]
        bone = deform_bones[child_name]
        bone["parent"] = parent_name
        if child_name not in deform_bones[parent_name]["children"]:
            deform_bones[parent_name]["children"].append(child_name)
        print(f"    → {child_name} 부모를 {parent_name}로 설정 ({method})")
        return True

    def _min_bone_distance(bone_a, bone_b):
        """두 본 사이의 최소 거리 (head/tail 4조합 중 최소)."""
        return min(
            vec_length(vec_sub(bone_a["tail"], bone_b["head"])),
            vec_length(vec_sub(bone_a["head"], bone_b["head"])),
            vec_length(vec_sub(bone_a["tail"], bone_b["tail"])),
            vec_length(vec_sub(bone_a["head"], bone_b["tail"])),
        )

    avg_len = sum(b["length"] for b in deform_bones.values()) / total
    threshold_tight = max(avg_len * 0.3, 1e-4)
    threshold_head = max(avg_len * 0.5, 1e-4)
    threshold_broad = max(avg_len * 1.5, 1e-4)

    def _run_step(parentless, step_func):
        """한 RECON 단계를 모든 parentless 본에 대해 실행. 연결된 본 제거."""
        remaining = []
        changed = False
        for name in parentless:
            if deform_bones[name]["parent"] is not None:
                continue
            if step_func(name):
                changed = True
            else:
                remaining.append(name)
        return remaining, changed

    def _step1(name):
        bone = deform_bones[name]
        best_parent, best_dist = None, threshold_tight
        for other_name, other_bone in deform_bones.items():
            if other_name == name:
                continue
            dist = vec_length(vec_sub(other_bone["tail"], bone["head"]))
            if dist < best_dist:
                best_dist = dist
                best_parent = other_name
        if best_parent:
            if DEBUG:
                print(f"  [RECON-1] {name}: tail→head match={best_parent}, dist={best_dist:.6f}")
            return _try_set_parent(name, best_parent, "tail→head")
        return False

    def _step2(name):
        bone = deform_bones[name]
        best_bridge, best_bridge_dist = None, threshold_tight
        for other_name, other_bone in all_bones.items():
            if other_name == name or other_name in deform_names:
                continue
            dist = vec_length(vec_sub(other_bone["tail"], bone["head"]))
            if dist < best_bridge_dist:
                deform_anc = _find_deform_ancestor(other_name)
                if deform_anc and deform_anc != name:
                    best_bridge_dist = dist
                    best_bridge = deform_anc
        if best_bridge:
            if DEBUG:
                print(f"  [RECON-2] {name}: bridge→{best_bridge}, dist={best_bridge_dist:.6f}")
            return _try_set_parent(name, best_bridge, "bridge")
        return False

    def _step3(name):
        bone = deform_bones[name]
        best_head, best_head_dist = None, threshold_head
        for other_name, other_bone in deform_bones.items():
            if other_name == name:
                continue
            dist = vec_length(vec_sub(other_bone["head"], bone["head"]))
            if dist < best_head_dist:
                best_head_dist = dist
                best_head = other_name
        if not best_head:
            return False

        name_is_root = any(h in name.lower() for h in ROOT_NAME_HINTS)
        other_is_root = any(h in best_head.lower() for h in ROOT_NAME_HINTS)
        other_has_parent = deform_bones[best_head]["parent"] is not None

        if DEBUG:
            print(f"  [RECON-3] {name}: head≈head {best_head}, dist={best_head_dist:.6f}")

        if name_is_root and not other_is_root:
            if deform_bones[best_head]["parent"] is None:
                return _try_set_parent(best_head, name, "head≈head-rootname")
        elif other_is_root and not name_is_root:
            return _try_set_parent(name, best_head, "head≈head-rootname")
        elif other_has_parent:
            return _try_set_parent(name, best_head, "head≈head")
        else:
            my_desc = count_descendants(name, deform_bones)
            other_desc = count_descendants(best_head, deform_bones)
            if my_desc <= other_desc:
                return _try_set_parent(best_head, name, "head≈head-hub")
            else:
                return _try_set_parent(name, best_head, "head≈head-hub")
        return False

    def _step4(name):
        bone = deform_bones[name]
        # 원본에서 고립 본(부모도 자식도 없음)은 RECON-4 제외 → unmapped로 유지
        orig = (original_hierarchy or {}).get(name)
        if orig and orig["parent"] is None and not orig["children"]:
            if DEBUG:
                print(f"  [RECON-4] {name}: 고립 본 → 스킵")
            return False
        my_descendants = set()
        _collect = [name]
        while _collect:
            _cur = _collect.pop()
            for _ch in deform_bones[_cur]["children"]:
                if _ch not in my_descendants:
                    my_descendants.add(_ch)
                    _collect.append(_ch)

        best_near, best_near_dist = None, threshold_broad
        for other_name, other_bone in deform_bones.items():
            if other_name == name or other_name in my_descendants:
                continue
            in_tree = other_bone["parent"] is not None or len(other_bone["children"]) > 0
            if not in_tree:
                continue
            dist = _min_bone_distance(other_bone, bone)
            if dist < best_near_dist:
                best_near_dist = dist
                best_near = other_name

        if best_near:
            if DEBUG:
                print(f"  [RECON-4] {name}: nearest={best_near}, dist={best_near_dist:.6f}")

            # 방향 판단: ROOT_NAME_HINT 또는 후손 수가 많은 쪽이 부모
            name_is_root = any(h in name.lower() for h in ROOT_NAME_HINTS)
            other_is_root = any(h in best_near.lower() for h in ROOT_NAME_HINTS)
            other_parentless = deform_bones[best_near]["parent"] is None

            if other_parentless:
                other_desc = count_descendants(best_near, deform_bones)
                if name_is_root and not other_is_root:
                    return _try_set_parent(best_near, name, "nearest-rootname")
                elif not name_is_root and other_is_root:
                    return _try_set_parent(name, best_near, "nearest-rootname")
                elif len(my_descendants) > other_desc:
                    return _try_set_parent(best_near, name, "nearest-hub")
                else:
                    return _try_set_parent(name, best_near, "nearest")
            else:
                return _try_set_parent(name, best_near, "nearest")
        else:
            if DEBUG:
                print(f"  [RECON-?] {name}: 연결 실패 (threshold={threshold_broad:.6f})")
            return False

    # 반복: 각 패스에서 RECON-1→2→3→4 순서로 전체 실행
    for _pass in range(4):
        parentless = [n for n, b in deform_bones.items() if b["parent"] is None]
        if len(parentless) <= 1:
            break

        any_changed = False
        rest, ch = _run_step(parentless, _step1)
        any_changed |= ch
        rest, ch = _run_step(rest, _step2)
        any_changed |= ch
        rest, ch = _run_step(rest, _step3)
        any_changed |= ch
        # RECON-1/2/3 후 collapse: spine 트리가 확립된 상태에서 형제 연결
        ch_collapse = _run_collapse()
        any_changed |= ch_collapse
        if ch_collapse:
            rest = [n for n in rest if deform_bones[n]["parent"] is None]
        rest, ch = _run_step(rest, _step4)
        any_changed |= ch

        if not any_changed:
            break


# ═══════════════════════════════════════════════════════════════
# 구조 식별
# ═══════════════════════════════════════════════════════════════


def count_descendants(bone_name, bones):
    """하위 본 수 재귀 카운트"""
    count = 0
    for child in bones[bone_name]["children"]:
        count += 1 + count_descendants(child, bones)
    return count


def find_root_bone(deform_bones):
    """
    루트 본 식별.
    가중 스코어: 후손 수(0.5) + 중심 근접(0.3) + 최상위(0.2)
    """
    candidates = []

    # 모든 본의 중심점 계산
    all_heads = [b["head"] for b in deform_bones.values()]
    center_of_mass = vec_avg(all_heads)

    max_descendants = max(count_descendants(name, deform_bones) for name in deform_bones)
    if max_descendants == 0:
        max_descendants = 1

    # 전체 아마추어 크기 (거리 정규화용)
    max_dist = 0
    for b in deform_bones.values():
        d = vec_length(vec_sub(b["head"], center_of_mass))
        if d > max_dist:
            max_dist = d
    if max_dist < 1e-8:
        max_dist = 1.0

    for name, bone in deform_bones.items():
        # 후손 수 점수
        desc_count = count_descendants(name, deform_bones)
        score_descendants = desc_count / max_descendants

        # 중심 근접 점수 (가까울수록 높음)
        dist_to_center = vec_length(vec_sub(bone["head"], center_of_mass))
        score_center = 1.0 - min(dist_to_center / max_dist, 1.0)

        # 최상위 점수 (부모 없으면 1.0, 있으면 깊이에 따라 감소)
        depth = 0
        p = bone["parent"]
        while p:
            depth += 1
            p = deform_bones[p]["parent"] if p in deform_bones else None
        score_top = 1.0 / (1.0 + depth)

        total = score_descendants * 0.5 + score_center * 0.3 + score_top * 0.2
        candidates.append(
            (
                name,
                total,
                {
                    "descendants": score_descendants,
                    "center": score_center,
                    "top": score_top,
                },
            )
        )

    candidates.sort(key=lambda x: x[1], reverse=True)
    # 디버그: 상위 5개 후보 출력
    print("[DEBUG] root 후보 (상위 5):")
    for name, score, details in candidates[:5]:
        desc = count_descendants(name, deform_bones)
        print(
            f"  {name}: total={score:.3f} desc={details['descendants']:.3f}({desc}) "
            f"center={details['center']:.3f} top={details['top']:.3f}"
        )
    return candidates[0] if candidates else None


def trace_spine_chain(root_name, deform_bones):
    """
    루트에서 위(+Z)로 가장 긴 체인을 추적.
    각 분기점에서 +Z 방향에 가장 가까운 자식을 선택.
    """
    # center_x 정규화용 스케일 상대 임계값 (본 평균 길이 기반)
    avg_bone_len = sum(b["length"] for b in deform_bones.values()) / max(len(deform_bones), 1)
    center_threshold = max(avg_bone_len * 0.5, 0.01)

    chain = []
    current = root_name

    while current:
        bone = deform_bones[current]
        chain.append(current)

        children = bone["children"]
        if not children:
            break

        # 얼굴 본 키워드가 포함된 자식은 스파인 후보에서 제외
        spine_candidates = []
        for child_name in children:
            child = deform_bones[child_name]
            is_face = any(kw in child_name.lower() for kw in FACE_BONE_KEYWORDS)
            if not is_face:
                spine_candidates.append(child_name)

        if not spine_candidates:
            # look-through: face 본의 손자 중 non-face + 후손이 있으면 spine 후보로 복원
            for child_name in children:
                child = deform_bones[child_name]
                for gc_name in child.get("children", []):
                    if gc_name not in deform_bones:
                        continue
                    gc_is_face = any(kw in gc_name.lower() for kw in FACE_BONE_KEYWORDS)
                    if not gc_is_face and count_descendants(gc_name, deform_bones) > 0:
                        spine_candidates.append(child_name)
                        break
            if not spine_candidates:
                if DEBUG:
                    print(
                        f"[DEBUG] trace_spine_chain: 모든 자식이 face 본 "
                        f"(parent={current}, children={children}), spine 추적 중단"
                    )
                break

        # 스파인 후보 중 최선 자식 선택
        # 가중치: 후손 수(0.5) + +Z 방향(0.2) + 위치 Z 변화(0.15) + 중심 X(0.15)
        # 사족 동물은 척추가 수평(+Y)이므로 방향보다 후손 수를 우선
        best_child = None
        best_score = -float("inf")

        max_desc = (
            max(
                (count_descendants(c, deform_bones) for c in spine_candidates),
                default=1,
            )
            or 1
        )

        for child_name in spine_candidates:
            child = deform_bones[child_name]
            dir_z = child["direction"][2]
            # 자식 head가 부모 head와 같은 위치이면 자식 tail의 Z를 기준으로 판단
            pos_z_delta = child["head"][2] - bone["head"][2]
            if abs(pos_z_delta) < 1e-6:
                pos_z_delta = child["tail"][2] - bone["head"][2]
            desc_count = count_descendants(child_name, deform_bones)
            center_x = 1.0 - min(abs(child["head"][0]) / center_threshold, 1.0)

            score = (
                dir_z * 0.2
                + (1.0 if pos_z_delta > 0 else -0.5) * 0.15
                + (desc_count / max_desc) * 0.5
                + center_x * 0.15
            )

            if score > best_score:
                best_score = score
                best_child = child_name

        # 스코어가 너무 낮으면 스파인이 아닌 다른 방향 (다리/꼬리)
        if best_score < DOWNWARD_THRESHOLD and len(chain) > 2:
            break

        # head 감지: face 자식이 필터링된 상태에서 best_child에 후손이 없으면
        # 장식 본(flower 등)이지 spine 연속이 아님 → 중단
        if count_descendants(best_child, deform_bones) == 0 and len(spine_candidates) < len(
            children
        ):
            break

        current = best_child

    return chain


def find_downward_branches(spine_chain, deform_bones):
    """
    스파인 체인에서 아래(-Z)로 분기하는 모든 체인을 찾기.
    Returns: [(branch_point_name, chain_names_list), ...]
    """
    branches = []
    spine_set = set(spine_chain)

    def _is_downward(bone_data, ref_head_z):
        return bone_data["direction"][2] < DOWNWARD_THRESHOLD or (
            bone_data["direction"][2] < 0 and bone_data["tail"][2] < ref_head_z
        )

    for spine_bone_name in spine_chain:
        bone = deform_bones[spine_bone_name]
        for child_name in bone["children"]:
            if child_name in spine_set:
                continue

            child = deform_bones[child_name]
            # 아래로 향하는 체인인지 확인
            # 1. 방향이 강하게 아래(-Z)이거나
            # 2. 방향이 약간이라도 아래이면서 tail이 부모 head보다 아래인 경우
            if _is_downward(child, bone["head"][2]):
                # 체인 따라가기
                chain = trace_chain(child_name, deform_bones, spine_set)
                if len(chain) >= MIN_LEG_CHAIN_LENGTH:
                    branches.append((spine_bone_name, chain))
            else:
                # 중간 허브 본(예: shoulder_L)을 통해 분기하는 경우 — 손자 본 탐색
                downward_gcs = []
                for gc_name in child["children"]:
                    if gc_name in spine_set or gc_name not in deform_bones:
                        continue
                    gc = deform_bones[gc_name]
                    if _is_downward(gc, child["head"][2]):
                        downward_gcs.append(gc_name)
                # hub 본은 전용 허브(하향 grandchild 1개)일 때만 체인에 포함
                # 다중 분기(hip_01 등)는 공유 분기점이므로 hub 제외
                include_hub = len(downward_gcs) == 1
                for gc_name in downward_gcs:
                    chain = trace_chain(gc_name, deform_bones, spine_set)
                    if len(chain) >= MIN_LEG_CHAIN_LENGTH:
                        if include_hub:
                            chain = [child_name, *chain]
                        branches.append((spine_bone_name, chain))

    # orphan 본 탐색: 부모가 없는 deform 본 중 하향 본이 있으면
    # 가장 가까운 spine 본에 연결해 다리 후보로 추가
    already_found = set()
    for _, chain in branches:
        already_found.update(chain)

    orphans = [
        name
        for name, b in deform_bones.items()
        if b["parent"] is None and name not in spine_set and name not in already_found
    ]
    if orphans:
        from skeleton_detection import vec_length, vec_sub

        for orphan_name in orphans:
            orphan = deform_bones[orphan_name]
            if not _is_downward(orphan, orphan["head"][2]):
                # hub 패턴: orphan 자체가 하향이 아니면 자식 확인
                downward_children = [
                    c
                    for c in orphan["children"]
                    if c in deform_bones
                    and c not in spine_set
                    and c not in already_found
                    and _is_downward(deform_bones[c], orphan["head"][2])
                ]
                if not downward_children:
                    continue
                # 자식부터 체인 시작, orphan을 hub로 포함
                for dc_name in downward_children:
                    chain = trace_chain(dc_name, deform_bones, spine_set)
                    if len(chain) >= MIN_LEG_CHAIN_LENGTH:
                        full_chain = [orphan_name, *chain]
                        # 가장 가까운 spine 본 찾기
                        nearest_spine = min(
                            spine_chain,
                            key=lambda s: vec_length(
                                vec_sub(deform_bones[s]["head"], orphan["head"])
                            ),
                        )
                        branches.append((nearest_spine, full_chain))
                        already_found.update(full_chain)
            else:
                chain = trace_chain(orphan_name, deform_bones, spine_set)
                if len(chain) >= MIN_LEG_CHAIN_LENGTH:
                    nearest_spine = min(
                        spine_chain,
                        key=lambda s: vec_length(vec_sub(deform_bones[s]["head"], orphan["head"])),
                    )
                    branches.append((nearest_spine, chain))
                    already_found.update(chain)

    return branches


def trace_chain(start_name, deform_bones, exclude_set=None):
    """
    시작 본에서 체인을 끝까지 따라가기.
    분기가 있으면 가장 긴 경로 선택.
    """
    if exclude_set is None:
        exclude_set = set()

    chain = [start_name]
    current = start_name

    while True:
        bone = deform_bones[current]
        children = [c for c in bone["children"] if c not in exclude_set]

        if not children:
            break

        if len(children) == 1:
            chain.append(children[0])
            current = children[0]
        else:
            # 여러 자식: 가장 긴 하위 체인을 가진 자식 선택
            best_child = None
            best_len = 0
            for child_name in children:
                sub_chain = trace_chain(child_name, deform_bones, exclude_set)
                if len(sub_chain) > best_len:
                    best_len = len(sub_chain)
                    best_child = child_name
            if best_child:
                chain.append(best_child)
                current = best_child
            else:
                break

    return chain


def classify_legs(branches, spine_chain, deform_bones):
    """
    다리 후보를 앞/뒤 + L/R로 분류.
    스파인 부착 위치: 하단(root 근처) = 뒷다리, 상단(head 근처) = 앞다리.
    X좌표: 양수 = L, 음수 = R (Blender 기본)
    """
    if not branches:
        return {}

    # 적응형 L/R 분류 임계값: 리그 스케일에 비례
    if deform_bones:
        avg_bone_length = sum(b["length"] for b in deform_bones.values()) / len(deform_bones)
    else:
        avg_bone_length = 0.1
    center_x_threshold = avg_bone_length * CENTER_X_RATIO

    # 스파인 인덱스 매핑 (0=하단, len-1=상단)
    spine_index = {name: i for i, name in enumerate(spine_chain)}

    # 실제 다리 분기 위치 기준으로 중간점 계산
    # (neck/head가 spine_chain에 포함되어도 다리 분류에 영향 안 줌)
    branch_indices = [spine_index.get(bp, 0) for bp, _ in branches]
    unique_indices = set(branch_indices)
    if len(unique_indices) >= 2:
        spine_mid = (min(branch_indices) + max(branch_indices)) / 2.0
    else:
        spine_mid = len(spine_chain) / 2.0

    result = {
        "back_leg_l": None,
        "back_leg_r": None,
        "front_leg_l": None,
        "front_leg_r": None,
    }

    # 분기점의 스파인 위치로 앞/뒤 분류
    back_candidates = []
    front_candidates = []

    for branch_point, chain in branches:
        idx = spine_index.get(branch_point, 0)
        # 체인의 평균 X 좌표로 좌우 판별
        avg_x = sum(deform_bones[name]["head"][0] for name in chain) / len(chain)

        info = {
            "chain": chain,
            "branch_point": branch_point,
            "spine_idx": idx,
            "avg_x": avg_x,
            "side": "l"
            if avg_x > center_x_threshold
            else ("r" if avg_x < -center_x_threshold else "c"),
        }

        if idx < spine_mid:
            back_candidates.append(info)
        else:
            front_candidates.append(info)

    # L/R 쌍 매칭
    def assign_pair(candidates, prefix):
        left = [c for c in candidates if c["side"] == "l"]
        right = [c for c in candidates if c["side"] == "r"]

        if left:
            result[f"{prefix}_l"] = left[0]["chain"]
        if right:
            result[f"{prefix}_r"] = right[0]["chain"]

    assign_pair(back_candidates, "back_leg")
    assign_pair(front_candidates, "front_leg")

    return result


def split_leg_foot(chain, deform_bones):
    """
    다리 체인을 상부(leg)와 하부(foot)로 자동 분리.

    분리 기준: 체인 하단에서 방향이 -Z(아래)에서 수평/전방으로 전환되는 지점.
    전환이 불명확하면 마지막 1본을 foot으로 분리.

    Returns:
        (leg_bones, foot_bones): 각각 본 이름 리스트
    """
    if len(chain) <= 2:
        # 2본 이하: 분리하지 않음 (전체가 leg)
        return chain, []

    # 아래에서 위로 올라가며 -Z 방향이 시작되는 지점을 찾는다
    foot_start = len(chain)

    for i in range(len(chain) - 1, -1, -1):
        bone = deform_bones[chain[i]]
        if bone["direction"][2] < DOWNWARD_THRESHOLD:
            foot_start = i + 1
            break

    if foot_start >= len(chain):
        # 모든 본이 아래로 향함 → 마지막 1본을 foot으로 분리
        foot_bone_count = 1
        if len(chain) >= 5:
            penultimate = chain[-2].lower()
            last = chain[-1].lower()
            if "hand" in penultimate and "finger" in last:
                foot_bone_count = 2
        foot_start = len(chain) - foot_bone_count

    leg = chain[:foot_start]
    foot = chain[foot_start:]

    # leg가 비면 첫 번째 foot 본을 leg로 이동
    if not leg and foot:
        leg = [foot[0]]
        foot = foot[1:]

    return leg, foot


def find_tail_chain(root_name, spine_chain, deform_bones):
    """
    루트에서 spine 반대 방향으로 가는 꼬리 체인 찾기.
    중간 허브 본(예: hip_01)을 통해 분기하는 꼬리도 탐색.
    """
    spine_set = set(spine_chain)

    # spine 방향 파악: 꼬리는 이 방향의 반대
    if len(spine_chain) > 1:
        spine_dir = deform_bones[spine_chain[1]]["direction"]
    else:
        spine_dir = (0, -1, 0)

    # 후보 수집: root 직계 자식 + spine 본의 비-spine 자식의 자식(허브 경유)
    candidates = []
    # 1) root 직계 자식
    for child_name in deform_bones[root_name]["children"]:
        if child_name not in spine_set:
            candidates.append(child_name)

    # 2) spine 본의 비-spine 중간 허브 본을 통한 손자 본
    for sp_name in spine_chain:
        for child_name in deform_bones[sp_name]["children"]:
            if child_name in spine_set or child_name not in deform_bones:
                continue
            child = deform_bones[child_name]
            # 아래로 향하지 않는 중간 본의 자식 중 꼬리 후보 탐색
            if child["direction"][2] >= DOWNWARD_THRESHOLD:
                for gc_name in child["children"]:
                    if gc_name in spine_set or gc_name not in deform_bones:
                        continue
                    gc = deform_bones[gc_name]
                    # 아래로 향하는 본은 다리이므로 제외
                    if gc["direction"][2] >= DOWNWARD_THRESHOLD:
                        candidates.append(gc_name)

    best_chain = None
    best_score = -float("inf")

    for child_name in candidates:
        child = deform_bones[child_name]
        avg_x = abs(child["head"][0])

        # spine 반대 방향 점수 (dot이 음수 = 반대 방향 = 꼬리)
        anti_spine = -vec_dot(child["direction"], spine_dir)
        center_x = 1.0 - min(avg_x / 0.1, 1.0)

        chain = trace_chain(child_name, deform_bones, spine_set)
        if len(chain) < 1:
            continue
        # 체인 길이 보너스: 더 긴 체인을 우선 (부모 본이 포함된 체인 선호)
        chain_bonus = len(chain) * 0.05
        score = anti_spine * 0.4 + center_x * 0.3 + chain_bonus

        if score > best_score:
            best_score = score
            best_chain = chain

    return best_chain


# ═══════════════════════════════════════════════════════════════
# Shape Key 드라이버 스캔
# ═══════════════════════════════════════════════════════════════


def _extract_shape_key_name(data_path):
    """드라이버 data_path에서 shape key 이름 추출.

    예: 'key_blocks["SmileMouth"].value' → 'SmileMouth'
    """
    import re

    m = re.search(r'key_blocks\["([^"]+)"\]', data_path)
    return m.group(1) if m else data_path


def _extract_bone_from_data_path(data_path):
    """SINGLE_PROP 드라이버의 data_path에서 본 이름 추출.

    예: 'pose.bones["BoneName"]["prop"]' → 'BoneName'
    """
    import re

    m = re.search(r'pose\.bones\["([^"]+)"\]', data_path)
    return m.group(1) if m else None


def scan_shape_key_drivers(armature_obj):
    """소스 아마추어에 연결된 메시의 shape key 드라이버 스캔.

    Args:
        armature_obj: 소스 아마추어 오브젝트

    Returns:
        tuple: (drivers_info, driver_bones)
            drivers_info: 드라이버 정보 리스트
            driver_bones: 드라이버에 사용되는 컨트롤러 본 이름 집합
    """
    driver_bones = set()
    drivers_info = []

    for child in armature_obj.children:
        if child.type != "MESH":
            continue
        mesh = child.data
        if not mesh.shape_keys or not mesh.shape_keys.animation_data:
            continue
        for fc in mesh.shape_keys.animation_data.drivers:
            sk_name = _extract_shape_key_name(fc.data_path)
            for var in fc.driver.variables:
                for target in var.targets:
                    if target.id != armature_obj:
                        continue
                    if var.type == "TRANSFORMS":
                        bone_name = target.bone_target
                        if not bone_name:
                            continue
                        driver_bones.add(bone_name)
                        drivers_info.append(
                            {
                                "shape_key": sk_name,
                                "mesh_name": child.name,
                                "bone_name": bone_name,
                                "var_type": "TRANSFORMS",
                                "var_name": var.name,
                                "transform_type": target.transform_type,
                                "transform_space": target.transform_space,
                            }
                        )
                    elif var.type == "SINGLE_PROP":
                        bone_name = _extract_bone_from_data_path(target.data_path)
                        if not bone_name:
                            continue
                        driver_bones.add(bone_name)
                        drivers_info.append(
                            {
                                "shape_key": sk_name,
                                "mesh_name": child.name,
                                "bone_name": bone_name,
                                "var_type": "SINGLE_PROP",
                                "var_name": var.name,
                                "data_path": target.data_path,
                            }
                        )

    return drivers_info, driver_bones


# ═══════════════════════════════════════════════════════════════
# Pole Vector / Head Features
# ═══════════════════════════════════════════════════════════════

POLE_KEYWORDS = ["pole", "knee", "elbow"]


def find_pole_vectors(all_bones, legs, leg_foot_pairs):
    """
    전체 본(deform + non-deform)에서 IK pole vector 본을 찾아 다리에 매칭.

    Args:
        all_bones: 전체 본 딕셔너리 (extract_bone_data 결과)
        legs: {"back_leg_l": [...], ...} 다리 체인
        leg_foot_pairs: {"back_foot_l": [...], ...} 발 체인

    Returns:
        dict: {"back_leg_l": {"name": ..., "head": (x,y,z)}, ...}
    """
    # 1. 이름 기반 pole 후보 수집
    pole_candidates = []
    for name, bone in all_bones.items():
        name_lower = name.lower()
        if any(kw in name_lower for kw in POLE_KEYWORDS):
            pole_candidates.append(bone)

    if not pole_candidates:
        return {}

    # 2. 각 다리 체인의 중간점 계산
    leg_keys = ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]
    leg_midpoints = {}
    for key in leg_keys:
        chain = legs.get(key, [])
        foot_key = key.replace("_leg_", "_foot_")
        foot_chain = leg_foot_pairs.get(foot_key, [])
        full_chain = list(chain) + list(foot_chain)
        if not full_chain:
            continue

        # 체인의 첫 번째 본 head와 마지막 본 tail의 중간점
        first_bone = all_bones.get(full_chain[0])
        last_bone = all_bones.get(full_chain[-1])
        if first_bone and last_bone:
            mid = tuple((first_bone["head"][i] + last_bone["tail"][i]) / 2 for i in range(3))
            leg_midpoints[key] = mid

    if not leg_midpoints:
        return {}

    # 3. 각 pole 후보를 가장 가까운 다리에 매칭
    pole_vectors = {}
    used_poles = set()

    for key, midpoint in leg_midpoints.items():
        best_pole = None
        best_dist = float("inf")

        for pole in pole_candidates:
            if pole["name"] in used_poles:
                continue
            dist = vec_length(vec_sub(pole["head"], midpoint))
            if dist < best_dist:
                best_dist = dist
                best_pole = pole

        if best_pole:
            pole_vectors[key] = {
                "name": best_pole["name"],
                "head": best_pole["head"],
            }
            used_poles.add(best_pole["name"])

    return pole_vectors


EAR_KEYWORDS = ["ear"]
# ear를 제외한 face 키워드
FACE_ONLY_KEYWORDS = ["eye", "jaw", "mouth", "tongue"]


def find_head_features(head_name, deform_bones):
    """
    head 본의 자식에서 얼굴 특징 식별.
    ear는 독립 역할로 분리 (ARP ear_ref 직접 매핑).
    나머지(eye, jaw, mouth, tongue)는 cc_ 커스텀 본.
    """
    features = {
        "face_bones": [],  # cc_ 커스텀 본 (eye, jaw, mouth, tongue)
        "ear_l": [],  # 귀 좌 체인
        "ear_r": [],  # 귀 우 체인
    }

    if head_name not in deform_bones:
        return features

    head = deform_bones[head_name]

    def collect_subtree(bone_name):
        """본과 그 하위 본 모두 수집"""
        result = [bone_name]
        if bone_name in deform_bones:
            for child in deform_bones[bone_name]["children"]:
                result.extend(collect_subtree(child))
        return result

    # Pass 1: 키워드 기반 분류 (ear, face)
    remaining = []
    for child_name in head["children"]:
        if child_name not in deform_bones:
            continue
        child = deform_bones[child_name]
        name_lower = child_name.lower()

        # ear 키워드 체크 → 독립 역할
        is_ear = any(kw in name_lower for kw in EAR_KEYWORDS)
        if is_ear:
            subtree = collect_subtree(child_name)
            avg_x = child["head"][0]
            if avg_x > 0:
                features["ear_l"].extend(subtree)
            else:
                features["ear_r"].extend(subtree)
            continue

        # face 키워드 체크 → cc_ 커스텀 본
        is_face = any(kw in name_lower for kw in FACE_ONLY_KEYWORDS)
        if is_face:
            subtree = collect_subtree(child_name)
            features["face_bones"].extend(subtree)
        else:
            remaining.append(child_name)

    # Pass 2: 키워드 없는 본 — 키워드 귀가 이미 있으면 face로, 없으면 구조 감지
    keyword_ears_found = bool(features["ear_l"]) or bool(features["ear_r"])

    for child_name in remaining:
        child = deform_bones[child_name]
        chain = trace_chain(child_name, deform_bones, set())

        if not keyword_ears_found and len(chain) <= MAX_EAR_CHAIN_LENGTH:
            avg_x = sum(deform_bones[n]["head"][0] for n in chain) / len(chain)
            dir_x = abs(child["direction"][0])

            # 측면으로 뻗거나 중심에서 벗어나 있으면 귀로 추정
            if dir_x > 0.3 or abs(avg_x) > LATERAL_THRESHOLD:
                if avg_x > 0:
                    features["ear_l"].extend(chain)
                else:
                    features["ear_r"].extend(chain)
                continue

        features["face_bones"].extend(chain)

    return features

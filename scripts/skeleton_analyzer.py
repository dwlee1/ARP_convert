"""
스켈레톤 구조 분석기
====================
소스 deform 본의 하이어라키/위치/방향을 분석하여
이름에 의존하지 않는 구조 기반 본 역할 식별.

사용법:
  from skeleton_analyzer import analyze_skeleton, generate_arp_mapping
  analysis = analyze_skeleton(armature_obj)
  mapping = generate_arp_mapping(analysis)
"""

import json
import math
import os
from collections import defaultdict

import bpy

DEBUG = os.environ.get("BLENDER_RIG_DEBUG", "").lower() in ("1", "true")

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

# ARP dog 프리셋 ref 본 구조
ARP_REF_MAP = {
    "root": ["root_ref.x"],
    "spine": ["spine_01_ref.x", "spine_02_ref.x", "spine_03_ref.x"],
    "neck": ["neck_ref.x"],
    "head": ["head_ref.x"],
    "back_leg_l": ["thigh_b_ref.l", "thigh_ref.l", "leg_ref.l"],
    "back_leg_r": ["thigh_b_ref.r", "thigh_ref.r", "leg_ref.r"],
    "back_foot_l": ["foot_ref.l", "toes_ref.l"],
    "back_foot_r": ["foot_ref.r", "toes_ref.r"],
    "front_leg_l": ["thigh_b_ref_dupli_001.l", "thigh_ref_dupli_001.l", "leg_ref_dupli_001.l"],
    "front_leg_r": ["thigh_b_ref_dupli_001.r", "thigh_ref_dupli_001.r", "leg_ref_dupli_001.r"],
    "front_foot_l": ["foot_ref_dupli_001.l", "toes_ref_dupli_001.l"],
    "front_foot_r": ["foot_ref_dupli_001.r", "toes_ref_dupli_001.r"],
    "tail": ["tail_00_ref.x", "tail_01_ref.x", "tail_02_ref.x", "tail_03_ref.x"],
    "ear_l": ["ear_01_ref.l", "ear_02_ref.l"],
    "ear_r": ["ear_01_ref.r", "ear_02_ref.r"],
}

# ARP 컨트롤러 본 매핑 (.bmap용)
ARP_CTRL_MAP = {
    "root": ["c_root_master.x"],
    "spine": ["c_spine_01.x", "c_spine_02.x", "c_spine_03.x"],
    "neck": ["c_neck.x"],
    "head": ["c_head.x"],
    "back_leg_l": ["c_thigh_b.l", "c_thigh_fk.l", "c_leg_fk.l"],
    "back_leg_r": ["c_thigh_b.r", "c_thigh_fk.r", "c_leg_fk.r"],
    "back_foot_l": ["c_foot_fk.l", "c_toes_fk.l"],
    "back_foot_r": ["c_foot_fk.r", "c_toes_fk.r"],
    "front_leg_l": ["c_shoulder.l", "c_arm_fk.l", "c_forearm_fk.l"],
    "front_leg_r": ["c_shoulder.r", "c_arm_fk.r", "c_forearm_fk.r"],
    "front_foot_l": ["c_hand_fk.l"],
    "front_foot_r": ["c_hand_fk.r"],
    "tail": ["c_tail_00.x", "c_tail_01.x", "c_tail_02.x", "c_tail_03.x"],
    "ear_l": ["c_ear_01.l", "c_ear_02.l"],
    "ear_r": ["c_ear_01.r", "c_ear_02.r"],
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


ROOT_NAME_HINTS = {"pelvis", "hips", "hip", "root"}


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
            center_x = 1.0 - min(abs(child["head"][0]) / 0.1, 1.0)

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
                # 중간 허브 본(예: hip_01)을 통해 분기하는 경우 — 손자 본 탐색
                for gc_name in child["children"]:
                    if gc_name in spine_set or gc_name not in deform_bones:
                        continue
                    gc = deform_bones[gc_name]
                    if _is_downward(gc, child["head"][2]):
                        chain = trace_chain(gc_name, deform_bones, spine_set)
                        if len(chain) >= MIN_LEG_CHAIN_LENGTH:
                            branches.append((spine_bone_name, chain))

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
        foot_start = len(chain) - 1

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

        score = anti_spine * 0.6 + center_x * 0.4

        if score > best_score:
            chain = trace_chain(child_name, deform_bones, spine_set)
            # 꼬리는 1본 이상 (일부 리그는 단일 본 tail)
            if len(chain) >= 1:
                best_score = score
                best_chain = chain

    return best_chain


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


def remap_shape_key_drivers(armature_obj, source_armature, arp_armature):
    """메시의 shape key 드라이버 타겟을 소스에서 ARP 아마추어로 리맵.

    원본 본 이름을 유지하므로 bone_target 변경은 불필요하고,
    target.id만 source → ARP로 교체한다.

    Args:
        armature_obj: 소스 아마추어 (드라이버가 참조하는 원래 아마추어)
        source_armature: 소스 아마추어 오브젝트 (== armature_obj, 명시적 전달)
        arp_armature: ARP 아마추어 오브젝트

    Returns:
        int: 리맵된 드라이버 변수 수
    """
    remapped = 0
    for child in armature_obj.children:
        if child.type != "MESH":
            continue
        mesh = child.data
        if not mesh.shape_keys or not mesh.shape_keys.animation_data:
            continue
        for fc in mesh.shape_keys.animation_data.drivers:
            for var in fc.driver.variables:
                for target in var.targets:
                    if target.id == source_armature:
                        target.id = arp_armature
                        remapped += 1
    return remapped


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
# 체인 길이 매칭
# ═══════════════════════════════════════════════════════════════


def match_chain_lengths(source_bones, target_refs):
    """
    소스 본 리스트와 ARP ref 본 리스트의 길이가 다를 때 매칭.

    Returns:
        dict: {source_bone_name: arp_ref_name}
    """
    s_len = len(source_bones)
    t_len = len(target_refs)

    if s_len == 0 or t_len == 0:
        return {}

    mapping = {}

    if s_len == t_len:
        # 1:1 매칭
        for i in range(s_len):
            mapping[source_bones[i]] = target_refs[i]

    elif s_len > t_len:
        # 소스가 더 많음: 모든 소스를 가장 가까운 타겟에 many-to-one 매핑
        for s_idx in range(s_len):
            t_float = s_idx * (t_len - 1) / (s_len - 1)
            t_idx = round(t_float)
            mapping[source_bones[s_idx]] = target_refs[t_idx]

    else:
        # 소스가 더 적음: 루트부터 순서대로
        for i in range(s_len):
            mapping[source_bones[i]] = target_refs[i]

    return mapping


def map_role_chain(role, source_bones, target_bones):
    """
    역할별 체인 매핑.

    BuildRig는 leg/foot를 분리해서 해석하므로, Remap도 같은 의미를 유지해야 한다.
    특히 target이 1개인 역할(back_foot/front_foot 등)은 source가 여러 본이어도
    대표 본 1개만 사용해 중복 target 엔트리가 생기지 않도록 한다.
    foot 역할은 마지막 본을 대표로 써야 2본 체인에서는 toe 쪽, 1본 체인에서는
    foot 본 자체가 Remap 컨트롤에 연결된다.
    """
    if not source_bones or not target_bones:
        return {}

    if len(target_bones) == 1:
        if role.startswith("back_foot") or role.startswith("front_foot"):
            return {source_bones[-1]: target_bones[0]}
        return {source_bones[0]: target_bones[0]}

    return match_chain_lengths(source_bones, target_bones)


# ═══════════════════════════════════════════════════════════════
# ARP 매핑 생성
# ═══════════════════════════════════════════════════════════════


def generate_arp_mapping(analysis):
    """
    분석 결과를 ARP ref 본 매핑(deform_to_ref dict)으로 변환.

    Returns:
        dict: 기존 프로필과 호환되는 형식
            {
                'deform_to_ref': {src_bone: arp_ref_bone, ...},
                'ref_alignment': {'priority': {}, 'avg_lr': {}},
            }
    """
    chains = analysis.get("chains", {})
    deform_to_ref = {}
    skipped_roles = []

    for role, chain_info in chains.items():
        source_bones = chain_info["bones"]
        target_refs = _dynamic_ref_names(role, len(source_bones))

        if not target_refs:
            target_refs = ARP_REF_MAP.get(role, [])
        if not target_refs:
            skipped_roles.append(role)
            continue

        chain_mapping = map_role_chain(role, source_bones, target_refs)
        deform_to_ref.update(chain_mapping)

    return {
        "name": "auto_generated",
        "description": f"자동 생성 매핑 (신뢰도: {analysis.get('confidence', 0)})",
        "arp_preset": "dog",
        "deform_to_ref": deform_to_ref,
        "ref_alignment": {"priority": {}, "avg_lr": {}},
        "skipped_roles": skipped_roles,
    }


# ═══════════════════════════════════════════════════════════════
# ARP 실제 이름 탐색 (match_to_rig 후)
# ═══════════════════════════════════════════════════════════════

# 역할별 컨트롤러 이름 검색 패턴 (정규식)
_CTRL_SEARCH_PATTERNS = {
    "root": [r"^c_root_master\."],
    "spine": [r"^c_spine_\d+\."],
    "neck": [r"^c_neck"],
    "head": [r"^c_head\."],
    "back_leg_l": [r"^c_thigh_b\.l", r"^c_thigh_fk\.l", r"^c_leg_fk\.l"],
    "back_leg_r": [r"^c_thigh_b\.r", r"^c_thigh_fk\.r", r"^c_leg_fk\.r"],
    "back_foot_l": [r"^c_foot_fk\.l", r"^c_toes(_fk)?\.l"],
    "back_foot_r": [r"^c_foot_fk\.r", r"^c_toes(_fk)?\.r"],
    # dog 프리셋: 앞다리가 _dupli_001 복제 체인. humanoid 프리셋은 arm 계열.
    # 두 패턴을 모두 나열 — dog에서는 dupli만, humanoid에서는 arm만 매칭됨.
    "front_leg_l": [
        r"^c_thigh_b_dupli_\d+\.l",
        r"^c_thigh_fk_dupli_\d+\.l",
        r"^c_leg_fk_dupli_\d+\.l",
        r"^c_shoulder\.l",
        r"^c_arm_fk\.l",
        r"^c_forearm_fk\.l",
    ],
    "front_leg_r": [
        r"^c_thigh_b_dupli_\d+\.r",
        r"^c_thigh_fk_dupli_\d+\.r",
        r"^c_leg_fk_dupli_\d+\.r",
        r"^c_shoulder\.r",
        r"^c_arm_fk\.r",
        r"^c_forearm_fk\.r",
    ],
    "front_foot_l": [r"^c_foot_fk_dupli_\d+\.l", r"^c_hand_fk\.l"],
    "front_foot_r": [r"^c_foot_fk_dupli_\d+\.r", r"^c_hand_fk\.r"],
    "tail": [r"^c_tail_\d+\."],
    "ear_l": [r"^c_ear_\d+\.l"],
    "ear_r": [r"^c_ear_\d+\.r"],
}

# 와일드카드(다중 본) 패턴 — 이 역할은 하나의 패턴이 여러 본을 매칭해야 함
_MULTI_BONE_ROLES = {"spine", "tail", "ear_l", "ear_r"}


def discover_arp_ctrl_map(arp_obj):
    """
    match_to_rig 이후 ARP 아마추어에서 실제 컨트롤러 이름을 역할별로 탐색.

    Returns:
        dict: {role: [ctrl_name, ...], ...}  역할별 컨트롤러 이름 리스트 (패턴 순서 유지)
    """
    import re

    if arp_obj is None or arp_obj.type != "ARMATURE":
        return {}

    all_bones = set(b.name for b in arp_obj.data.bones)
    ctrl_map = {}

    for role, patterns in _CTRL_SEARCH_PATTERNS.items():
        matched = []
        multi = role in _MULTI_BONE_ROLES

        for pat in patterns:
            if multi:
                # 다중 본 역할: 패턴에 매칭되는 모든 본을 수집
                hits = sorted([bn for bn in all_bones if re.match(pat, bn)])
                matched.extend(hits)
            else:
                # 단일 본 역할: 패턴당 첫 매칭만
                for bone_name in all_bones:
                    if re.match(pat, bone_name):
                        matched.append(bone_name)
                        break
        if matched:
            ctrl_map[role] = matched

    return ctrl_map


# ═══════════════════════════════════════════════════════════════
# 동적 이름 생성 (체인 개수 매칭 — fallback용)
# ═══════════════════════════════════════════════════════════════

# 소스 개수에 맞춰 ref 이름을 동적 생성하는 패턴
_REF_PATTERNS = {
    "spine": ("spine_{:02d}_ref.x", 1),  # spine_01_ref.x, spine_02_ref.x, ...
    "tail": ("tail_{:02d}_ref.x", 0),  # tail_00_ref.x, tail_01_ref.x, ...
    "ear_l": ("ear_{:02d}_ref.l", 1),  # ear_01_ref.l, ear_02_ref.l, ...
    "ear_r": ("ear_{:02d}_ref.r", 1),
}


def _dynamic_ref_names(role, count):
    """
    역할과 소스 개수에 맞춰 ARP ref 본 이름을 반환.
    기본 개수 이하면 ARP_REF_MAP에서 잘라서 반환하고,
    초과하면 패턴으로 동적 생성한다.
    """
    base = ARP_REF_MAP.get(role, [])
    if count <= len(base):
        return base[:count]

    if role in _REF_PATTERNS:
        pattern, start_idx = _REF_PATTERNS[role]
        return [pattern.format(start_idx + i) for i in range(count)]

    # neck: 첫 번째는 neck_ref.x, 추가분은 neck_NN_ref.x
    if role == "neck":
        result = list(base)
        for i in range(len(base), count):
            result.append(f"neck_{i + 1:02d}_ref.x")
        return result

    return base


# 소스 개수에 맞춰 컨트롤러 이름을 동적 생성하는 패턴
_CTRL_PATTERNS = {
    "spine": ("c_spine_{:02d}.x", 1),  # c_spine_01.x, c_spine_02.x, ...
    "tail": ("c_tail_{:02d}.x", 0),  # c_tail_00.x, c_tail_01.x, ...
    "ear_l": ("c_ear_{:02d}.l", 1),  # c_ear_01.l, c_ear_02.l, ...
    "ear_r": ("c_ear_{:02d}.r", 1),
}


def _dynamic_ctrl_names(role, count):
    """
    역할과 소스 개수에 맞춰 ARP 컨트롤러 본 이름을 반환.
    기본 개수 이하면 ARP_CTRL_MAP에서 잘라서 반환하고,
    초과하면 패턴으로 동적 생성한다.
    """
    base = ARP_CTRL_MAP.get(role, [])
    if count <= len(base):
        return base[:count]

    # 패턴이 있으면 전체 동적 생성
    if role in _CTRL_PATTERNS:
        pattern, start_idx = _CTRL_PATTERNS[role]
        return [pattern.format(start_idx + i) for i in range(count)]

    # neck 등 패턴이 없는 역할: 기존 + 추가분
    if role == "neck":
        result = list(base)
        for i in range(len(base), count):
            result.append(f"c_neck_{i + 1:02d}.x")
        return result

    return base


def _apply_ik_to_foot_ctrl(ctrl_name, role):
    """foot 역할의 FK 컨트롤러를 IK로 변환. (ik_legs 모드용)

    leg 체인은 건드리지 않고, foot 역할 본만 IK 컨트롤러에 매핑한다.

    Returns:
        (ik_ctrl_name, pole_name, ik_flag)
    """
    import re

    # c_toes 계열 → c_foot_ik 계열 (IK=True, pole=c_leg_pole)
    # 매칭 대상: c_toes.l, c_toes_dupli_001.l, c_toes_fk_dupli_001.l
    m = re.match(r"^c_toes(?:_fk)?(_dupli_\d+)?(\.[lr])$", ctrl_name)
    if m:
        dupli = m.group(1) or ""
        side = m.group(2)
        return f"c_foot_ik{dupli}{side}", f"c_leg_pole{dupli}{side}", True
    # humanoid: c_hand_fk → c_hand_ik
    if role.startswith("front_foot") and ctrl_name.startswith("c_hand_fk"):
        suffix = ctrl_name[len("c_hand_fk") :]
        return f"c_hand_ik{suffix}", f"c_arm_pole{suffix}", True
    return ctrl_name, "", False


# ═══════════════════════════════════════════════════════════════
# 검증 리포트
# ═══════════════════════════════════════════════════════════════


def generate_verification_report(analysis):
    """분석 결과를 사람이 읽기 쉬운 형식으로 출력"""
    lines = []
    lines.append("=" * 55)
    lines.append("  구조 기반 본 매핑 분석 결과")
    lines.append("=" * 55)
    lines.append(f"  소스: {analysis.get('source_armature', '?')}")
    lines.append(f"  전체 신뢰도: {analysis.get('confidence', 0)}")
    lines.append("-" * 55)

    chains = analysis.get("chains", {})
    for role, info in chains.items():
        bones_str = " → ".join(info["bones"])
        conf = info["confidence"]
        lines.append(f"  {role:14s}: {bones_str:30s} ({conf:.2f})")

    unmapped = analysis.get("unmapped", [])
    if unmapped:
        lines.append(f"  {'미매핑':14s}: {', '.join(unmapped)}")

    lines.append("=" * 55)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# JSON 저장/로드
# ═══════════════════════════════════════════════════════════════


def save_auto_mapping(analysis, output_dir):
    """분석 결과를 auto_mapping.json으로 저장"""
    # bone_data는 너무 크므로 제외
    save_data = {k: v for k, v in analysis.items() if k != "bone_data"}

    # deform_to_ref도 함께 저장
    mapping = generate_arp_mapping(analysis)
    save_data["deform_to_ref"] = mapping["deform_to_ref"]

    path = os.path.join(output_dir, "auto_mapping.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)

    return path


def load_auto_mapping(input_dir):
    """
    auto_mapping.json 로드.
    chains에서 deform_to_ref를 재생성 (사용자가 chains를 수정했을 수 있음).
    """
    path = os.path.join(input_dir, "auto_mapping.json")
    if not os.path.exists(path):
        return None

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # chains가 있으면 deform_to_ref 재생성
    if "chains" in data:
        deform_to_ref = {}
        for role, chain_info in data["chains"].items():
            source_bones = chain_info.get("bones", [])
            target_refs = _dynamic_ref_names(role, len(source_bones))
            if not target_refs:
                target_refs = ARP_REF_MAP.get(role, [])
            if target_refs:
                chain_mapping = map_role_chain(role, source_bones, target_refs)
                deform_to_ref.update(chain_mapping)
        data["deform_to_ref"] = deform_to_ref

    return data


# ═══════════════════════════════════════════════════════════════
# Preview Armature 생성
# ═══════════════════════════════════════════════════════════════

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
    "unmapped": (0.5, 0.5, 0.5),  # 회색
}

# 역할 커스텀 프로퍼티 키
ROLE_PROP_KEY = "arp_role"
VIRTUAL_NECK_BONE = "__virtual_neck__"
VIRTUAL_NECK_RATIO = 0.35


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

    # 각 역할 내에서 하이어라키 순서(부모→자식)로 정렬
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
# ARP ref 본 동적 검색
# ═══════════════════════════════════════════════════════════════


def discover_arp_ref_chains(arp_obj):
    """
    ARP 리그에서 실제 존재하는 ref 본을 검색하여 역할별 체인으로 분류.
    하드코딩 이름(ARP_REF_MAP) 대신 실제 본 이름을 반환.

    Args:
        arp_obj: ARP Armature 오브젝트

    Returns:
        dict: ARP_REF_MAP과 동일한 형식 {role: [ref_bone_names]}
    """
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    arp_obj.select_set(True)
    bpy.context.view_layer.objects.active = arp_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = arp_obj.data.edit_bones

    # _ref 포함 본만 수집
    ref_bones = {}
    for eb in edit_bones:
        if "_ref" in eb.name:
            ref_bones[eb.name] = {
                "head": (arp_obj.matrix_world @ eb.head.copy()),
                "tail": (arp_obj.matrix_world @ eb.tail.copy()),
                "parent": eb.parent.name if eb.parent else None,
                "children": [child.name for child in eb.children],
                "depth": 0,
            }
            # 깊이 계산
            d = 0
            p = eb.parent
            while p:
                d += 1
                p = p.parent
            ref_bones[eb.name]["depth"] = d

    bpy.ops.object.mode_set(mode="OBJECT")

    result = {}
    all_names = set(ref_bones.keys())

    # --- Root ---
    root_candidates = [n for n in all_names if n.startswith("root_ref")]
    if root_candidates:
        result["root"] = sorted(root_candidates)

    # --- Spine ---
    spine_candidates = sorted([n for n in all_names if "spine_" in n and "_ref" in n])
    if spine_candidates:
        result["spine"] = spine_candidates

    # --- Neck ---
    neck_candidates = sorted([n for n in all_names if "neck" in n and "_ref" in n])
    if neck_candidates:
        result["neck"] = neck_candidates

    # --- Head ---
    head_candidates = [n for n in all_names if n.startswith("head_ref")]
    if head_candidates:
        result["head"] = head_candidates

    # --- Tail ---
    tail_candidates = sorted([n for n in all_names if "tail_" in n and "_ref" in n])
    if tail_candidates:
        result["tail"] = tail_candidates

    def collect_connected_ref_chain(root_name):
        """시작 ref 본에서 connected 자식 체인을 따라 limb 전체 ref 체인을 수집."""
        chain = []
        current_name = root_name
        visited = set()

        while current_name and current_name not in visited and current_name in ref_bones:
            visited.add(current_name)
            chain.append(current_name)

            child_candidates = [
                child_name
                for child_name in ref_bones[current_name].get("children", [])
                if child_name in ref_bones and "bank" not in child_name and "heel" not in child_name
            ]
            if not child_candidates:
                break

            child_candidates.sort(key=lambda x: ref_bones[x]["depth"])
            next_name = None
            for child_name in child_candidates:
                if ref_bones.get(child_name, {}).get("parent") == current_name:
                    next_name = child_name
                    break
            if next_name is None:
                break
            current_name = next_name

        return chain

    # --- Legs (leg/foot 분리) ---
    # leg: thigh_b/thigh/leg ref 본
    # foot: foot/toes ref 본
    # bank/heel: 발 보조 ref 본
    FOOT_AUX_PREFIXES = ["foot_bank", "foot_heel"]

    for side_suffix, side_key in [(".l", "l"), (".r", "r")]:
        for is_dupli, limb_prefix in [(False, "back"), (True, "front")]:
            thigh_roots = [
                n
                for n in all_names
                if n.startswith("thigh_b_ref")
                and n.endswith(side_suffix)
                and ("dupli" in n) == is_dupli
            ]
            if not thigh_roots:
                thigh_roots = [
                    n
                    for n in all_names
                    if n.startswith("thigh_ref")
                    and n.endswith(side_suffix)
                    and ("dupli" in n) == is_dupli
                ]

            if thigh_roots:
                thigh_roots.sort(key=lambda x: ref_bones[x]["depth"])
                limb_chain = collect_connected_ref_chain(thigh_roots[0])
                leg_bones = [n for n in limb_chain if n.startswith("thigh") or n.startswith("leg")]
                foot_bones = [n for n in limb_chain if n.startswith("foot") or n.startswith("toes")]

                if leg_bones:
                    result[f"{limb_prefix}_leg_{side_key}"] = leg_bones
                if foot_bones:
                    result[f"{limb_prefix}_foot_{side_key}"] = foot_bones

            for aux_prefix in FOOT_AUX_PREFIXES:
                aux_key = aux_prefix.replace("foot_", "")
                candidates = [
                    n
                    for n in all_names
                    if n.startswith(aux_prefix)
                    and "_ref" in n
                    and n.endswith(side_suffix)
                    and ("dupli" in n) == is_dupli
                ]
                if candidates:
                    candidates.sort(key=lambda x: ref_bones[x]["depth"])
                    result[f"{limb_prefix}_{aux_key}_{side_key}"] = candidates

    # --- Ear ---
    for side_suffix, side_key in [(".l", "l"), (".r", "r")]:
        ear_candidates = sorted(
            [n for n in all_names if "ear" in n and "_ref" in n and n.endswith(side_suffix)],
            key=lambda x: ref_bones[x]["depth"],
        )
        if ear_candidates:
            result[f"ear_{side_key}"] = ear_candidates

    # 디버그 로그
    print("=" * 55)
    print("  ARP ref 본 자동 검색 결과")
    print("=" * 55)
    for role, bones in result.items():
        print(f"  {role:20s}: {' → '.join(bones)}")
    print(f"  총 ref 본 수: {len(ref_bones)}")
    print("=" * 55)

    return result


def build_preview_to_ref_mapping(preview_obj, arp_obj):
    """
    Preview 역할 + ARP 실제 ref 본을 매칭하여 최종 매핑 생성.
    하드코딩 이름 대신 동적 검색 결과를 사용.
    bank/heel 가이드 본도 포함.

    Args:
        preview_obj: Preview Armature 오브젝트
        arp_obj: ARP Armature 오브젝트

    Returns:
        dict: {preview_bone_name: arp_ref_bone_name}
    """
    roles = read_preview_roles(preview_obj)
    arp_chains = discover_arp_ref_chains(arp_obj)

    mapping = {}

    print("=" * 55)
    print("  Preview → ARP ref 매핑")
    print("=" * 55)

    def map_chain(role_label, preview_bones, target_refs):
        if not preview_bones:
            return

        if not target_refs:
            if "heel" in role_label or "bank" in role_label:
                print(
                    f"  [WARN] 가이드 '{role_label}'에 대응하는 ARP ref 없음 (match_to_rig에서 처리)"
                )
            else:
                print(f"  [WARN] 역할 '{role_label}'에 대응하는 ARP ref 체인 없음")
            return

        chain_mapping = map_role_chain(role_label, preview_bones, target_refs)
        mapping.update(chain_mapping)
        for src, ref in chain_mapping.items():
            print(f"  {src:25s} → {ref}")

    for role, preview_bones in roles.items():
        if role == "unmapped":
            continue
        map_chain(role, preview_bones, arp_chains.get(role, []))

    print("=" * 55)
    return mapping

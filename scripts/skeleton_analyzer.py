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

import bpy
import json
import os
import math
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════
# 상수
# ═══════════════════════════════════════════════════════════════

# 방향 임계값 (Blender 좌표계: Z=위, Y=앞, X=좌우)
UPWARD_THRESHOLD = 0.3
DOWNWARD_THRESHOLD = -0.3
BACKWARD_THRESHOLD = -0.3
CENTER_X_THRESHOLD = 0.05
LATERAL_THRESHOLD = 0.1
MIN_LEG_CHAIN_LENGTH = 2
MAX_EAR_CHAIN_LENGTH = 3

# 얼굴 본 키워드 (cc_ 커스텀 본으로 분류)
FACE_BONE_KEYWORDS = ["eye", "ear", "jaw", "mouth", "tongue"]

# ARP dog 프리셋 ref 본 구조 (3-bone leg, 고정)
ARP_REF_MAP = {
    "root":        ["root_ref.x"],
    "spine":       ["spine_01_ref.x", "spine_02_ref.x", "spine_03_ref.x"],
    "neck":        ["neck_ref.x"],
    "head":        ["head_ref.x"],
    "back_leg_l":  ["thigh_b_ref.l", "leg_b_ref.l", "foot_b_ref.l", "toes_b_ref.l"],
    "back_leg_r":  ["thigh_b_ref.r", "leg_b_ref.r", "foot_b_ref.r", "toes_b_ref.r"],
    "front_leg_l": ["thigh_b_ref_dupli_001.l", "leg_b_ref_dupli_001.l",
                    "foot_b_ref_dupli_001.l", "toes_b_ref_dupli_001.l"],
    "front_leg_r": ["thigh_b_ref_dupli_001.r", "leg_b_ref_dupli_001.r",
                    "foot_b_ref_dupli_001.r", "toes_b_ref_dupli_001.r"],
    "tail":        ["tail_00_ref.x", "tail_01_ref.x", "tail_02_ref.x", "tail_03_ref.x"],
}

# ARP 컨트롤러 본 매핑 (.bmap용)
ARP_CTRL_MAP = {
    "root":        ["c_root_master.x"],
    "spine":       ["c_spine_01.x", "c_spine_02.x", "c_spine_03.x"],
    "neck":        ["c_neck.x"],
    "head":        ["c_head.x"],
    "back_leg_l":  ["c_thigh_fk.l", "c_leg_fk.l", "c_foot_fk.l", "c_toes.l"],
    "back_leg_r":  ["c_thigh_fk.r", "c_leg_fk.r", "c_foot_fk.r", "c_toes.r"],
    "front_leg_l": ["c_shoulder.l", "c_arm_fk.l", "c_forearm_fk.l", "c_hand_fk.l"],
    "front_leg_r": ["c_shoulder.r", "c_arm_fk.r", "c_forearm_fk.r", "c_hand_fk.r"],
    "tail":        ["c_tail_00.x", "c_tail_01.x", "c_tail_02.x", "c_tail_03.x"],
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
    return math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)

def vec_normalize(v):
    l = vec_length(v)
    if l < 1e-8:
        return (0, 0, 0)
    return (v[0]/l, v[1]/l, v[2]/l)

def vec_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def vec_avg(vectors):
    n = len(vectors)
    if n == 0:
        return (0, 0, 0)
    s = (0, 0, 0)
    for v in vectors:
        s = vec_add(s, v)
    return vec_scale(s, 1.0/n)


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
    # Object 모드로 전환 후 아마추어 선택 & 활성화
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    armature_obj.select_set(True)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')

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
            'name': ebone.name,
            'head': head_t,
            'tail': tail_t,
            'roll': ebone.roll,
            'parent': ebone.parent.name if ebone.parent else None,
            'children': [c.name for c in ebone.children],
            'is_deform': ebone.use_deform,
            'direction': direction,
            'length': length,
            'use_connect': ebone.use_connect,
        }

    bpy.ops.object.mode_set(mode='OBJECT')
    return bones


def filter_deform_bones(all_bones):
    """
    deform 본만 추출하고, deform 본 간의 하이어라키를 재구성.
    비-deform 중간 본을 건너뛰어 직접적인 부모-자식 관계를 유지.
    """
    deform_names = {name for name, b in all_bones.items() if b['is_deform']}
    deform_bones = {}

    for name in deform_names:
        b = dict(all_bones[name])

        # 부모 찾기: deform 본인 가장 가까운 조상
        parent_name = b['parent']
        while parent_name and parent_name not in deform_names:
            parent_name = all_bones[parent_name]['parent']
        b['parent'] = parent_name

        # 자식 찾기: deform 본인 직접 후손
        deform_children = []
        queue = list(b['children'])
        while queue:
            child_name = queue.pop(0)
            if child_name in deform_names:
                deform_children.append(child_name)
            elif child_name in all_bones:
                queue.extend(all_bones[child_name]['children'])
        b['children'] = deform_children

        deform_bones[name] = b

    return deform_bones


# ═══════════════════════════════════════════════════════════════
# 구조 식별
# ═══════════════════════════════════════════════════════════════

def count_descendants(bone_name, bones):
    """하위 본 수 재귀 카운트"""
    count = 0
    for child in bones[bone_name]['children']:
        count += 1 + count_descendants(child, bones)
    return count


def find_root_bone(deform_bones):
    """
    루트 본 식별.
    가중 스코어: 후손 수(0.5) + 중심 근접(0.3) + 최상위(0.2)
    """
    candidates = []

    # 모든 본의 중심점 계산
    all_heads = [b['head'] for b in deform_bones.values()]
    center_of_mass = vec_avg(all_heads)

    max_descendants = max(count_descendants(name, deform_bones) for name in deform_bones)
    if max_descendants == 0:
        max_descendants = 1

    # 전체 아마추어 크기 (거리 정규화용)
    max_dist = 0
    for b in deform_bones.values():
        d = vec_length(vec_sub(b['head'], center_of_mass))
        if d > max_dist:
            max_dist = d
    if max_dist < 1e-8:
        max_dist = 1.0

    for name, bone in deform_bones.items():
        # 후손 수 점수
        desc_count = count_descendants(name, deform_bones)
        score_descendants = desc_count / max_descendants

        # 중심 근접 점수 (가까울수록 높음)
        dist_to_center = vec_length(vec_sub(bone['head'], center_of_mass))
        score_center = 1.0 - min(dist_to_center / max_dist, 1.0)

        # 최상위 점수 (부모 없으면 1.0, 있으면 깊이에 따라 감소)
        depth = 0
        p = bone['parent']
        while p:
            depth += 1
            p = deform_bones[p]['parent'] if p in deform_bones else None
        score_top = 1.0 / (1.0 + depth)

        total = score_descendants * 0.5 + score_center * 0.3 + score_top * 0.2
        candidates.append((name, total, {
            'descendants': score_descendants,
            'center': score_center,
            'top': score_top,
        }))

    candidates.sort(key=lambda x: x[1], reverse=True)
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

        children = bone['children']
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
            break

        # +Z 방향에 가장 가까운 자식 선택
        best_child = None
        best_z_score = -float('inf')

        for child_name in spine_candidates:
            child = deform_bones[child_name]
            # 본의 방향 Z 성분 + 위치의 상대적 Z 변화
            dir_z = child['direction'][2]
            pos_z_delta = child['head'][2] - bone['head'][2]
            z_score = dir_z * 0.6 + (1.0 if pos_z_delta > 0 else -0.5) * 0.4

            if z_score > best_z_score:
                best_z_score = z_score
                best_child = child_name

        # Z 점수가 음수면 스파인이 아닌 다른 방향 (다리/꼬리)
        if best_z_score < DOWNWARD_THRESHOLD and len(chain) > 2:
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

    for spine_bone_name in spine_chain:
        bone = deform_bones[spine_bone_name]
        for child_name in bone['children']:
            if child_name in spine_set:
                continue

            child = deform_bones[child_name]
            # 아래로 향하는 체인인지 확인
            if child['direction'][2] < DOWNWARD_THRESHOLD or child['head'][2] > bone['head'][2]:
                # 체인 따라가기
                chain = trace_chain(child_name, deform_bones, spine_set)
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
        children = [c for c in bone['children'] if c not in exclude_set]

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

    # 스파인 인덱스 매핑 (0=하단, len-1=상단)
    spine_index = {name: i for i, name in enumerate(spine_chain)}
    spine_mid = len(spine_chain) / 2.0

    result = {
        'back_leg_l': None, 'back_leg_r': None,
        'front_leg_l': None, 'front_leg_r': None,
    }

    # 분기점의 스파인 위치로 앞/뒤 분류
    back_candidates = []
    front_candidates = []

    for branch_point, chain in branches:
        idx = spine_index.get(branch_point, 0)
        # 체인의 평균 X 좌표로 좌우 판별
        avg_x = sum(deform_bones[name]['head'][0] for name in chain) / len(chain)

        info = {
            'chain': chain,
            'branch_point': branch_point,
            'spine_idx': idx,
            'avg_x': avg_x,
            'side': 'l' if avg_x > CENTER_X_THRESHOLD else ('r' if avg_x < -CENTER_X_THRESHOLD else 'c'),
        }

        if idx < spine_mid:
            back_candidates.append(info)
        else:
            front_candidates.append(info)

    # L/R 쌍 매칭
    def assign_pair(candidates, prefix):
        left = [c for c in candidates if c['side'] == 'l']
        right = [c for c in candidates if c['side'] == 'r']

        if left:
            result[f'{prefix}_l'] = left[0]['chain']
        if right:
            result[f'{prefix}_r'] = right[0]['chain']

    assign_pair(back_candidates, 'back_leg')
    assign_pair(front_candidates, 'front_leg')

    return result


def find_tail_chain(root_name, spine_chain, deform_bones):
    """
    루트에서 뒤(-Y)로 가는 꼬리 체인 찾기.
    """
    spine_set = set(spine_chain)
    bone = deform_bones[root_name]

    best_chain = None
    best_score = -float('inf')

    for child_name in bone['children']:
        if child_name in spine_set:
            continue

        child = deform_bones[child_name]
        # 뒤(-Y) 또는 아래(-Z) 방향 + 중앙 (|X| 작음)
        dir_y = child['direction'][1]
        dir_z = child['direction'][2]
        avg_x = abs(child['head'][0])

        # 꼬리는 -Y 방향이 주, 중앙에 위치
        score = -dir_y * 0.5 + (-dir_z) * 0.3 + (1.0 - min(avg_x / 0.1, 1.0)) * 0.2

        if score > best_score:
            chain = trace_chain(child_name, deform_bones, spine_set)
            # 꼬리는 보통 2본 이상
            if len(chain) >= 2:
                best_score = score
                best_chain = chain

    return best_chain


def find_head_features(head_name, deform_bones):
    """
    head 본의 자식에서 얼굴 특징(귀, 눈, 턱) 식별.
    키워드 기반 + 방향/위치 보조.
    """
    features = {
        'face_bones': [],  # cc_ 커스텀 본으로 등록할 얼굴 본
    }

    if head_name not in deform_bones:
        return features

    head = deform_bones[head_name]

    def collect_face_subtree(bone_name):
        """얼굴 본과 그 하위 본 모두 수집"""
        result = [bone_name]
        if bone_name in deform_bones:
            for child in deform_bones[bone_name]['children']:
                result.extend(collect_face_subtree(child))
        return result

    for child_name in head['children']:
        child = deform_bones[child_name]
        name_lower = child_name.lower()

        # 얼굴 키워드 체크
        is_face = any(kw in name_lower for kw in FACE_BONE_KEYWORDS)

        if is_face:
            # 얼굴 본 전체 서브트리 수집
            subtree = collect_face_subtree(child_name)
            features['face_bones'].extend(subtree)
        else:
            # 키워드 없지만 짧은 체인이면 얼굴 가능성
            chain = trace_chain(child_name, deform_bones, set())
            if len(chain) <= MAX_EAR_CHAIN_LENGTH:
                # 위로 향하면 귀, 옆이면 눈, 아래면 턱 가능성
                features['face_bones'].extend(chain)

    return features


# ═══════════════════════════════════════════════════════════════
# 메인 분석 함수
# ═══════════════════════════════════════════════════════════════

def analyze_skeleton(armature_obj):
    """
    소스 아마추어의 deform 본을 분석하여 구조적 역할을 식별.

    Returns:
        dict: 분석 결과 (chains, face_bones, unmapped, confidence 등)
    """
    # 1. 본 데이터 추출
    all_bones = extract_bone_data(armature_obj)
    deform_bones = filter_deform_bones(all_bones)

    if not deform_bones:
        return {'error': 'deform 본이 없습니다.', 'chains': {}, 'face_bones': [],
                'unmapped': [], 'confidence': 0}

    # 2. 루트 찾기
    root_result = find_root_bone(deform_bones)
    if not root_result:
        return {'error': '루트 본을 찾을 수 없습니다.', 'chains': {}, 'face_bones': [],
                'unmapped': list(deform_bones.keys()), 'confidence': 0}

    root_name = root_result[0]
    root_confidence = root_result[1]

    # 3. 스파인 체인 트레이싱
    spine_chain = trace_spine_chain(root_name, deform_bones)

    # 루트를 스파인에서 분리 (root는 별도 역할)
    if len(spine_chain) > 1:
        spine_body = spine_chain[1:]  # root 제외
    else:
        spine_body = []

    # 스파인에서 head/neck 분리 (마지막 1-2본)
    head_name = None
    neck_bones = []
    spine_only = list(spine_body)

    if len(spine_body) >= 2:
        head_name = spine_body[-1]
        # neck: head 바로 앞 본이 짧은 체인이면 neck
        # 간단히: 마지막 본 = head, 나머지 앞부분에서 상위 1-2본 = neck
        # 스파인 3본 + neck 1본 + head 1본 구조 가정
        if len(spine_body) >= 3:
            head_name = spine_body[-1]
            neck_bones = [spine_body[-2]]
            spine_only = spine_body[:-2]
        else:
            head_name = spine_body[-1]
            spine_only = spine_body[:-1]

    # 4. 다리 찾기
    branches = find_downward_branches(spine_chain, deform_bones)
    legs = classify_legs(branches, spine_chain, deform_bones)

    # 5. 꼬리 찾기
    tail_chain = find_tail_chain(root_name, spine_chain, deform_bones)

    # 6. 얼굴 특징 찾기
    face_features = find_head_features(head_name, deform_bones) if head_name else {'face_bones': []}

    # 7. 매핑된/미매핑 본 분류
    mapped_bones = set()
    mapped_bones.add(root_name)
    mapped_bones.update(spine_only)
    mapped_bones.update(neck_bones)
    if head_name:
        mapped_bones.add(head_name)
    for key in ['back_leg_l', 'back_leg_r', 'front_leg_l', 'front_leg_r']:
        if legs.get(key):
            mapped_bones.update(legs[key])
    if tail_chain:
        mapped_bones.update(tail_chain)
    mapped_bones.update(face_features.get('face_bones', []))

    unmapped = [name for name in deform_bones if name not in mapped_bones]

    # 8. 결과 구성
    chains = {}
    chains['root'] = {'bones': [root_name], 'confidence': root_confidence}

    if spine_only:
        chains['spine'] = {'bones': spine_only, 'confidence': 0.9}
    if neck_bones:
        chains['neck'] = {'bones': neck_bones, 'confidence': 0.85}
    if head_name:
        chains['head'] = {'bones': [head_name], 'confidence': 0.95}

    for key in ['back_leg_l', 'back_leg_r', 'front_leg_l', 'front_leg_r']:
        if legs.get(key):
            chains[key] = {'bones': legs[key], 'confidence': 0.9}

    if tail_chain:
        chains['tail'] = {'bones': tail_chain, 'confidence': 0.85}

    # 전체 신뢰도
    if chains:
        avg_confidence = sum(c['confidence'] for c in chains.values()) / len(chains)
    else:
        avg_confidence = 0

    return {
        'source_armature': armature_obj.name,
        'chains': chains,
        'face_bones': face_features.get('face_bones', []),
        'unmapped': unmapped,
        'confidence': round(avg_confidence, 2),
        'bone_data': deform_bones,  # 위치 정보 포함
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
        # 소스가 더 많음: 양 끝점 고정, 중간 보간
        mapping[source_bones[0]] = target_refs[0]
        mapping[source_bones[-1]] = target_refs[-1]

        for t_idx in range(1, t_len - 1):
            # 보간된 소스 인덱스
            s_idx = round(t_idx * (s_len - 1) / (t_len - 1))
            mapping[source_bones[s_idx]] = target_refs[t_idx]

    else:
        # 소스가 더 적음: 루트부터 순서대로
        for i in range(s_len):
            mapping[source_bones[i]] = target_refs[i]

    return mapping


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
                'face_bones': [src_bone, ...],
                'ref_alignment': {'priority': {}, 'avg_lr': {}},
            }
    """
    chains = analysis.get('chains', {})
    deform_to_ref = {}

    for role, chain_info in chains.items():
        source_bones = chain_info['bones']
        target_refs = ARP_REF_MAP.get(role, [])

        if not target_refs:
            continue

        chain_mapping = match_chain_lengths(source_bones, target_refs)
        deform_to_ref.update(chain_mapping)

    return {
        'name': 'auto_generated',
        'description': f"자동 생성 매핑 (신뢰도: {analysis.get('confidence', 0)})",
        'arp_preset': 'dog',
        'deform_to_ref': deform_to_ref,
        'face_bones': analysis.get('face_bones', []),
        'ref_alignment': {'priority': {}, 'avg_lr': {}},
    }


# ═══════════════════════════════════════════════════════════════
# 동적 .bmap 생성
# ═══════════════════════════════════════════════════════════════

def generate_bmap_content(analysis):
    """
    분석 결과에서 .bmap 파일 내용을 생성.

    Returns:
        str: .bmap 파일 내용
    """
    chains = analysis.get('chains', {})
    lines = []

    for role, chain_info in chains.items():
        source_bones = chain_info['bones']
        ctrl_bones = ARP_CTRL_MAP.get(role, [])

        if not ctrl_bones:
            continue

        mapping = match_chain_lengths(source_bones, ctrl_bones)

        for src_bone, ctrl_bone in mapping.items():
            is_root = (role == 'root')
            # .bmap 포맷: 4줄 반복
            flags = f"{'True' if is_root else 'False'}%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%"
            lines.append(f"{ctrl_bone}%{flags}")
            lines.append(src_bone)
            lines.append("True" if is_root else "False")
            lines.append("False")
            lines.append("")

    # 얼굴 cc_ 본 매핑 추가
    for face_bone in analysis.get('face_bones', []):
        cc_name = f"cc_{face_bone.lower()}"
        lines.append(f"{cc_name}%False%ABSOLUTE%0.0,0.0,0.0%0.0,0.0,0.0%1.0%False%False%")
        lines.append(face_bone)
        lines.append("False")
        lines.append("False")
        lines.append("")

    return "\n".join(lines)


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

    chains = analysis.get('chains', {})
    for role, info in chains.items():
        bones_str = " → ".join(info['bones'])
        conf = info['confidence']
        lines.append(f"  {role:14s}: {bones_str:30s} ({conf:.2f})")

    face_bones = analysis.get('face_bones', [])
    if face_bones:
        lines.append(f"  {'face (cc_)':14s}: {', '.join(face_bones)}")

    unmapped = analysis.get('unmapped', [])
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
    save_data = {k: v for k, v in analysis.items() if k != 'bone_data'}

    # deform_to_ref도 함께 저장
    mapping = generate_arp_mapping(analysis)
    save_data['deform_to_ref'] = mapping['deform_to_ref']

    path = os.path.join(output_dir, "auto_mapping.json")
    with open(path, 'w', encoding='utf-8') as f:
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

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # chains가 있으면 deform_to_ref 재생성
    if 'chains' in data:
        deform_to_ref = {}
        for role, chain_info in data['chains'].items():
            source_bones = chain_info.get('bones', [])
            target_refs = ARP_REF_MAP.get(role, [])
            if target_refs:
                chain_mapping = match_chain_lengths(source_bones, target_refs)
                deform_to_ref.update(chain_mapping)
        data['deform_to_ref'] = deform_to_ref

    return data


# ═══════════════════════════════════════════════════════════════
# Preview Armature 생성
# ═══════════════════════════════════════════════════════════════

# 역할별 본 그룹 색상 (Blender 테마 색상 인덱스)
ROLE_COLORS = {
    'root':        (1.0, 0.9, 0.0),    # 노랑
    'spine':       (0.2, 0.4, 1.0),    # 파랑
    'neck':        (0.2, 0.4, 1.0),    # 파랑
    'head':        (0.2, 0.4, 1.0),    # 파랑
    'back_leg_l':  (1.0, 0.2, 0.2),    # 빨강
    'back_leg_r':  (1.0, 0.2, 0.2),    # 빨강
    'front_leg_l': (0.2, 0.8, 0.2),    # 초록
    'front_leg_r': (0.2, 0.8, 0.2),    # 초록
    'tail':        (1.0, 0.5, 0.0),    # 주황
    'face':        (0.7, 0.3, 0.9),    # 보라
    'unmapped':    (0.5, 0.5, 0.5),    # 회색
}

# 역할 커스텀 프로퍼티 키
ROLE_PROP_KEY = "arp_role"


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
    bone_data = analysis.get('bone_data', {})
    chains = analysis.get('chains', {})
    face_bones_list = analysis.get('face_bones', [])
    unmapped_list = analysis.get('unmapped', [])

    if not bone_data:
        return None

    # 본 이름 → 역할 매핑 구성
    bone_to_role = {}
    for role, chain_info in chains.items():
        for bone_name in chain_info['bones']:
            bone_to_role[bone_name] = role
    for bone_name in face_bones_list:
        bone_to_role[bone_name] = 'face'
    for bone_name in unmapped_list:
        bone_to_role[bone_name] = 'unmapped'

    # Object 모드 확보
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # 새 Armature 데이터 생성
    arm_data = bpy.data.armatures.new(f"{source_obj.name}_preview")
    arm_data.display_type = 'OCTAHEDRAL'
    preview_obj = bpy.data.objects.new(f"{source_obj.name}_preview", arm_data)

    # 씬에 추가
    bpy.context.collection.objects.link(preview_obj)

    # 소스와 같은 위치/회전/스케일
    preview_obj.matrix_world = source_obj.matrix_world.copy()

    # Edit Mode 진입하여 본 생성
    bpy.ops.object.select_all(action='DESELECT')
    preview_obj.select_set(True)
    bpy.context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode='EDIT')

    edit_bones = preview_obj.data.edit_bones
    src_matrix = source_obj.matrix_world
    preview_matrix_inv = preview_obj.matrix_world.inverted()

    # 소스에서 Edit Mode 본 데이터 읽기 (bone_data에 이미 월드 좌표 있음)
    # deform 본만 생성
    created_bones = {}
    for bone_name, binfo in bone_data.items():
        ebone = edit_bones.new(bone_name)

        # 월드 좌표 → Preview 로컬 좌표
        from mathutils import Vector
        world_head = Vector(binfo['head'])
        world_tail = Vector(binfo['tail'])
        ebone.head = preview_matrix_inv @ world_head
        ebone.tail = preview_matrix_inv @ world_tail
        ebone.roll = binfo['roll']
        ebone.use_deform = True

        created_bones[bone_name] = ebone

    # 부모-자식 관계 설정
    for bone_name, binfo in bone_data.items():
        if binfo['parent'] and binfo['parent'] in created_bones:
            ebone = created_bones[bone_name]
            parent_ebone = created_bones[binfo['parent']]
            ebone.parent = parent_ebone

            # 연결 여부: head가 부모 tail에 충분히 가까우면 connected
            if (ebone.head - parent_ebone.tail).length < 0.001:
                ebone.use_connect = True

    bpy.ops.object.mode_set(mode='OBJECT')

    # 본 그룹 + 색상 설정 (Pose Mode에서)
    bpy.ops.object.mode_set(mode='POSE')

    # 역할별 본 그룹 생성
    bone_groups = {}
    for role, color in ROLE_COLORS.items():
        # Blender 4.x: bone_color 사용 (bone_groups 대신)
        pass  # 아래에서 개별 본에 색상 직접 설정

    # 각 본에 역할 커스텀 프로퍼티 + 색상 설정
    for bone_name in bone_data:
        pbone = preview_obj.pose.bones.get(bone_name)
        if pbone is None:
            continue

        role = bone_to_role.get(bone_name, 'unmapped')
        color = ROLE_COLORS.get(role, ROLE_COLORS['unmapped'])

        # 역할 커스텀 프로퍼티 저장
        pbone[ROLE_PROP_KEY] = role

        # Blender 4.x 본 색상 설정
        pbone.color.palette = 'CUSTOM'
        pbone.color.custom.normal = color
        pbone.color.custom.select = tuple(min(c + 0.3, 1.0) for c in color)
        pbone.color.custom.active = tuple(min(c + 0.5, 1.0) for c in color)

    bpy.ops.object.mode_set(mode='OBJECT')

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
        role = pbone.get(ROLE_PROP_KEY, 'unmapped')
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
    face_bones = []
    unmapped = []

    for role, bone_names in roles.items():
        if role == 'face':
            face_bones = bone_names
        elif role == 'unmapped':
            unmapped = bone_names
        else:
            chains[role] = {
                'bones': bone_names,
                'confidence': 1.0,  # 사용자 확인 완료
            }

    # bone_data 추출 (위치 정보)
    bone_data = extract_bone_data(preview_obj)
    deform_bones = {name: bone_data[name] for name in bone_data if bone_data[name]['is_deform']}

    return {
        'source_armature': preview_obj.name,
        'chains': chains,
        'face_bones': face_bones,
        'unmapped': unmapped,
        'confidence': 1.0,
        'bone_data': deform_bones,
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
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    arp_obj.select_set(True)
    bpy.context.view_layer.objects.active = arp_obj
    bpy.ops.object.mode_set(mode='EDIT')

    edit_bones = arp_obj.data.edit_bones

    # _ref 포함 본만 수집
    ref_bones = {}
    for eb in edit_bones:
        if '_ref' in eb.name:
            ref_bones[eb.name] = {
                'head': (arp_obj.matrix_world @ eb.head.copy()),
                'tail': (arp_obj.matrix_world @ eb.tail.copy()),
                'parent': eb.parent.name if eb.parent else None,
                'depth': 0,
            }
            # 깊이 계산
            d = 0
            p = eb.parent
            while p:
                d += 1
                p = p.parent
            ref_bones[eb.name]['depth'] = d

    bpy.ops.object.mode_set(mode='OBJECT')

    result = {}
    all_names = set(ref_bones.keys())

    # --- Root ---
    root_candidates = [n for n in all_names if n.startswith('root_ref')]
    if root_candidates:
        result['root'] = sorted(root_candidates)

    # --- Spine ---
    spine_candidates = sorted([n for n in all_names
                               if 'spine_' in n and '_ref' in n])
    if spine_candidates:
        result['spine'] = spine_candidates

    # --- Neck ---
    neck_candidates = sorted([n for n in all_names
                              if 'neck' in n and '_ref' in n])
    if neck_candidates:
        result['neck'] = neck_candidates

    # --- Head ---
    head_candidates = [n for n in all_names if n.startswith('head_ref')]
    if head_candidates:
        result['head'] = head_candidates

    # --- Tail ---
    tail_candidates = sorted([n for n in all_names
                              if 'tail_' in n and '_ref' in n])
    if tail_candidates:
        result['tail'] = tail_candidates

    # --- Legs ---
    # 뒷다리: thigh/leg/foot/toes + _ref + .l/.r (dupli 제외)
    # 앞다리: thigh/leg/foot/toes + _ref + dupli + .l/.r
    LEG_PREFIXES = ['thigh', 'leg', 'foot', 'toes']

    for side_suffix, side_key in [('.l', 'l'), ('.r', 'r')]:
        # 뒷다리 (dupli 아닌 것)
        back_leg = []
        for prefix in LEG_PREFIXES:
            candidates = [n for n in all_names
                          if n.startswith(prefix)
                          and '_ref' in n
                          and n.endswith(side_suffix)
                          and 'dupli' not in n]
            if candidates:
                # 여러 후보 중 depth가 가장 작은 것 (체인 순서대로)
                candidates.sort(key=lambda x: ref_bones[x]['depth'])
                back_leg.append(candidates[0])
        if back_leg:
            # depth 순 정렬
            back_leg.sort(key=lambda x: ref_bones[x]['depth'])
            result[f'back_leg_{side_key}'] = back_leg

        # 앞다리 (dupli 포함)
        front_leg = []
        for prefix in LEG_PREFIXES:
            candidates = [n for n in all_names
                          if n.startswith(prefix)
                          and '_ref' in n
                          and n.endswith(side_suffix)
                          and 'dupli' in n]
            if candidates:
                candidates.sort(key=lambda x: ref_bones[x]['depth'])
                front_leg.append(candidates[0])
        if front_leg:
            front_leg.sort(key=lambda x: ref_bones[x]['depth'])
            result[f'front_leg_{side_key}'] = front_leg

    # 디버그 로그
    print("=" * 55)
    print("  ARP ref 본 자동 검색 결과")
    print("=" * 55)
    for role, bones in result.items():
        print(f"  {role:16s}: {' → '.join(bones)}")
    print(f"  총 ref 본 수: {len(ref_bones)}")
    print("=" * 55)

    return result


def build_preview_to_ref_mapping(preview_obj, arp_obj):
    """
    Preview 역할 + ARP 실제 ref 본을 매칭하여 최종 매핑 생성.
    하드코딩 이름 대신 동적 검색 결과를 사용.

    Args:
        preview_obj: Preview Armature 오브젝트
        arp_obj: ARP Armature 오브젝트

    Returns:
        dict: {preview_bone_name: arp_ref_bone_name}
    """
    roles = read_preview_roles(preview_obj)
    arp_chains = discover_arp_ref_chains(arp_obj)

    mapping = {}

    for role, preview_bones in roles.items():
        if role in ('face', 'unmapped'):
            continue

        target_refs = arp_chains.get(role, [])
        if not target_refs:
            print(f"  [WARN] 역할 '{role}'에 대응하는 ARP ref 체인 없음")
            continue

        # 체인 길이 매칭
        chain_mapping = match_chain_lengths(preview_bones, target_refs)
        mapping.update(chain_mapping)

        # 매칭 로그
        for src, ref in chain_mapping.items():
            print(f"  {src:20s} → {ref}")

    return mapping

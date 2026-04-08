"""
ARP 매핑 모듈
=============
Auto-Rig Pro 특화 매핑, ref/ctrl 본 검색, 직렬화 로직을 담당한다.
skeleton_detection.py의 순수 구조 분석 결과를 ARP 리그에 연결하는 브릿지 역할.

skeleton_analyzer.py에서 분리됨.
"""

import json
import os
import re

import bpy

from skeleton_detection import scan_shape_key_drivers

# __all__ 정의: from arp_mapping import * 에서 _접두사 심볼도 포함
__all__ = [
    "ARP_CTRL_MAP",
    # 상수
    "ARP_REF_MAP",
    "_CTRL_PATTERNS",
    "_CTRL_SEARCH_PATTERNS",
    "_MULTI_BONE_ROLES",
    "_REF_PATTERNS",
    # IK
    "_apply_ik_to_foot_ctrl",
    "_dynamic_ctrl_names",
    # 동적 이름 생성
    "_dynamic_ref_names",
    # Preview→Ref
    "build_preview_to_ref_mapping",
    # 컨트롤러 탐색
    "discover_arp_ctrl_map",
    # ARP ref 검색
    "discover_arp_ref_chains",
    # 매핑 생성
    "generate_arp_mapping",
    # 리포트
    "generate_verification_report",
    "load_auto_mapping",
    "map_role_chain",
    # 체인 매칭
    "match_chain_lengths",
    # 드라이버 리맵
    "remap_shape_key_drivers",
    # JSON
    "save_auto_mapping",
]

# ═══════════════════════════════════════════════════════════════
# ARP 상수
# ═══════════════════════════════════════════════════════════════

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

# 와일드카드(다중 본) 패턴 — 이 역할은 하나의 패턴이 여러 본을 매칭해야 함
_MULTI_BONE_ROLES = {"spine", "neck", "tail", "ear_l", "ear_r"}

# 역할별 컨트롤러 이름 검색 패턴 (정규식)
_CTRL_SEARCH_PATTERNS = {
    "root": [r"^c_root_master\."],
    "spine": [r"^c_spine_\d+\."],
    "neck": [r"^c_subneck_\d+\.", r"^c_neck\."],
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

# 소스 개수에 맞춰 ref 이름을 동적 생성하는 패턴
_REF_PATTERNS = {
    "spine": ("spine_{:02d}_ref.x", 1),  # spine_01_ref.x, spine_02_ref.x, ...
    "tail": ("tail_{:02d}_ref.x", 0),  # tail_00_ref.x, tail_01_ref.x, ...
    "ear_l": ("ear_{:02d}_ref.l", 1),  # ear_01_ref.l, ear_02_ref.l, ...
    "ear_r": ("ear_{:02d}_ref.r", 1),
}

# 소스 개수에 맞춰 컨트롤러 이름을 동적 생성하는 패턴
_CTRL_PATTERNS = {
    "spine": ("c_spine_{:02d}.x", 1),  # c_spine_01.x, c_spine_02.x, ...
    "tail": ("c_tail_{:02d}.x", 0),  # c_tail_00.x, c_tail_01.x, ...
    "ear_l": ("c_ear_{:02d}.l", 1),  # c_ear_01.l, c_ear_02.l, ...
    "ear_r": ("c_ear_{:02d}.r", 1),
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


def discover_arp_ctrl_map(arp_obj):
    """
    match_to_rig 이후 ARP 아마추어에서 실제 컨트롤러 이름을 역할별로 탐색.

    Returns:
        dict: {role: [ctrl_name, ...], ...}  역할별 컨트롤러 이름 리스트 (패턴 순서 유지)
    """
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
    # c_toes 계열 → c_foot_ik 계열 (IK=True, pole=c_leg_pole)
    # 매칭 대상: c_toes.l, c_toes_dupli_001.l, c_toes_fk_dupli_001.l
    m = re.match(r"^c_toes(?:_fk)?(_dupli_\d+)?(\.[lr])$", ctrl_name)
    if m:
        dupli = m.group(1) or ""
        side = m.group(2)
        return f"c_foot_ik{dupli}{side}", f"c_leg_pole{dupli}{side}", True
    # c_foot_fk 계열 → c_foot_ik 계열 (2026-04-05 F12 back_foot 패턴 수정 이후
    # discover_arp_ctrl_map이 c_foot_fk를 첫 매칭으로 반환하므로 이 분기가 필요).
    # 매칭 대상: c_foot_fk.l, c_foot_fk_dupli_001.r
    m2 = re.match(r"^c_foot_fk(_dupli_\d+)?(\.[lr])$", ctrl_name)
    if m2:
        dupli = m2.group(1) or ""
        side = m2.group(2)
        return f"c_foot_ik{dupli}{side}", f"c_leg_pole{dupli}{side}", True
    # humanoid: c_hand_fk → c_hand_ik
    if role.startswith("front_foot") and ctrl_name.startswith("c_hand_fk"):
        suffix = ctrl_name[len("c_hand_fk") :]
        return f"c_hand_ik{suffix}", f"c_arm_pole{suffix}", True
    return ctrl_name, "", False


# ═══════════════════════════════════════════════════════════════
# Shape Key 드라이버 리맵
# ═══════════════════════════════════════════════════════════════


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
    # Late import: read_preview_roles는 skeleton_analyzer.py에 남아 있음
    from skeleton_analyzer import read_preview_roles

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

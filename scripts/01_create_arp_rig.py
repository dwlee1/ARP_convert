"""
01. ARP 리그 생성
=================
소스 deform 본 기준으로 ARP 리그를 생성하고 본 위치를 정렬.
Blender Scripting 탭에서 실행.

사용법:
  1. 변환할 리그가 있는 .blend 파일 열기
  2. 아래 CONFIG의 MAPPING_PROFILE 확인
  3. ▶ Run Script
"""

import os

# scripts/ 폴더를 import 경로에 추가
import sys
import traceback

import bpy
from mathutils import Vector


def _find_scripts_dir():
    """scripts/arp_utils.py가 있는 폴더를 찾는다."""
    # 1) __file__ 기반 (커맨드라인 실행)
    try:
        d = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(os.path.join(d, "arp_utils.py")):
            return d
    except NameError:
        pass
    # 2) blend 파일 경로에서 상위로 올라가며 scripts/ 탐색
    if bpy.data.filepath:
        d = os.path.dirname(bpy.data.filepath)
        for _ in range(10):
            candidate = os.path.join(d, "scripts")
            if os.path.exists(os.path.join(candidate, "arp_utils.py")):
                return candidate
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return ""


_SCRIPT_DIR = _find_scripts_dir()
if _SCRIPT_DIR and _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from arp_utils import (
    ensure_object_mode,
    find_arp_armature,
    find_mesh_objects,
    load_mapping_profile,
    log,
    run_arp_operator,
    select_only,
)

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

MAPPING_PROFILE = "custom_quadruped"
VERBOSE = True


# ═══════════════════════════════════════════════════════════════
# 소스 아마추어 식별
# ═══════════════════════════════════════════════════════════════


def find_source_armature(profile):
    """프로필 매핑 키와 일치하는 본이 가장 많은 비-ARP 아마추어를 선택."""
    mapping_keys = set(profile["deform_to_ref"].keys())
    best_obj = None
    best_match = 0

    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        if len([b for b in obj.data.bones if b.name.startswith("c_")]) > 5:
            continue
        matched = len([b for b in obj.data.bones if b.name in mapping_keys])
        if matched > best_match:
            best_match = matched
            best_obj = obj

    if best_obj:
        log(
            f"소스 아마추어: '{best_obj.name}' (프로필 매칭 {best_match}개 / 전체 {len(best_obj.data.bones)}개)"
        )

        # 매핑된 본 목록
        mapped = [b.name for b in best_obj.data.bones if b.name in mapping_keys]
        log(f"  매핑된 본 ({len(mapped)}개): {mapped}")

        # 프로필에 없는 deform 본
        unmapped_deform = [
            b.name for b in best_obj.data.bones if b.name not in mapping_keys and b.use_deform
        ]
        if unmapped_deform:
            log(f"  프로필에 없는 deform 본 ({len(unmapped_deform)}개): {unmapped_deform}", "WARN")

        # 프로필에 있지만 소스에 없는 본 (오타/이름 불일치 진단)
        source_bone_names = {b.name for b in best_obj.data.bones}
        missing_in_source = [k for k in mapping_keys if k not in source_bone_names]
        if missing_in_source:
            log(
                f"  프로필에 있지만 소스에 없는 본 ({len(missing_in_source)}개): {missing_in_source}",
                "WARN",
            )
    return best_obj


# ═══════════════════════════════════════════════════════════════
# ARP ref 본 위치 정렬
# ═══════════════════════════════════════════════════════════════


def align_ref_bones_to_source(source_obj, arp_obj, profile, copy_roll=True):
    """
    ARP 레퍼런스 본을 소스 아마추어 본 위치에 맞게 이동.
    프로필의 deform_to_ref + ref_alignment 기반.
    """
    ensure_object_mode()

    deform_to_ref = profile["deform_to_ref"]
    ref_alignment = profile.get("ref_alignment", {})
    priority_map = ref_alignment.get("priority", {})
    avg_lr_map = ref_alignment.get("avg_lr", {})

    # 소스 본 위치 추출 (월드 좌표)
    log("  소스 본 위치 추출")
    source_positions = {}

    bpy.context.view_layer.objects.active = source_obj
    bpy.ops.object.mode_set(mode="EDIT")

    src_matrix = source_obj.matrix_world
    for ebone in source_obj.data.edit_bones:
        world_head = src_matrix @ ebone.head.copy()
        world_tail = src_matrix @ ebone.tail.copy()
        source_positions[ebone.name] = (world_head, world_tail, ebone.roll)

    bpy.ops.object.mode_set(mode="OBJECT")

    # ARP ref 본 목표 위치 결정
    log("  목표 위치 결정")
    resolved = {}
    processed = set()

    # priority 매핑
    for ref_name, candidates in priority_map.items():
        for src in candidates:
            if src in source_positions:
                resolved[ref_name] = source_positions[src]
                processed.add(ref_name)
                break

    # avg_lr 매핑
    for ref_name, lr_pair in avg_lr_map.items():
        src_l, src_r = lr_pair[0], lr_pair[1]
        has_l = src_l in source_positions
        has_r = src_r in source_positions
        if has_l and has_r:
            l_h, l_t, l_r = source_positions[src_l]
            r_h, r_t, r_r = source_positions[src_r]
            avg_h = (l_h + r_h) / 2.0
            avg_t = (l_t + r_t) / 2.0
            avg_h.x = 0.0
            avg_t.x = 0.0
            resolved[ref_name] = (avg_h, avg_t, (l_r + r_r) / 2.0)
        elif has_l:
            h, t, r = source_positions[src_l]
            h = h.copy()
            t = t.copy()
            h.x = 0.0
            t.x = 0.0
            resolved[ref_name] = (h, t, r)
        elif has_r:
            h, t, r = source_positions[src_r]
            h = h.copy()
            t = t.copy()
            h.x = 0.0
            t.x = 0.0
            resolved[ref_name] = (h, t, r)
        processed.add(ref_name)

    # 일반 1:1 매핑
    mapped_ok = []
    mapped_fail = []
    for src_name, ref_name in deform_to_ref.items():
        if ref_name in processed:
            continue
        if src_name in source_positions:
            resolved[ref_name] = source_positions[src_name]
            mapped_ok.append(f"{src_name} → {ref_name}")
        else:
            mapped_fail.append(f"{src_name} → {ref_name} (소스 본 미발견)")

    if VERBOSE:
        for m in mapped_ok:
            log(f"    OK: {m}")
    if mapped_fail:
        for m in mapped_fail:
            log(f"    FAIL: {m}", "WARN")

    # ARP ref 본에 위치 적용 (하이어라키 순서: 부모 → 자식)
    log(f"  위치 적용: {len(resolved)}개 ref 본")

    bpy.context.view_layer.objects.active = arp_obj
    bpy.ops.object.mode_set(mode="EDIT")

    arp_matrix_inv = arp_obj.matrix_world.inverted()
    edit_bones = arp_obj.data.edit_bones
    aligned = 0

    # 하이어라키 깊이 계산 → 부모(얕은)부터 자식(깊은) 순서로 처리
    def get_depth(bone_name):
        eb = edit_bones.get(bone_name)
        depth = 0
        while eb and eb.parent:
            depth += 1
            eb = eb.parent
        return depth

    sorted_refs = sorted(resolved.keys(), key=get_depth)

    for ref_name in sorted_refs:
        world_head, world_tail, roll = resolved[ref_name]
        ebone = edit_bones.get(ref_name)
        if ebone is None:
            if VERBOSE:
                log(f"    '{ref_name}' 미발견 (프리셋에 없음)", "WARN")
            continue

        local_head = arp_matrix_inv @ world_head
        local_tail = arp_matrix_inv @ world_tail

        if (local_tail - local_head).length < 0.0001:
            local_tail = local_head + Vector((0, 0.01, 0))

        # Connected 본: head가 부모.tail에 고정 → tail만 설정
        if ebone.use_connect and ebone.parent:
            ebone.tail = local_tail
            if VERBOSE:
                log(f"    {ref_name}: tail만 설정 (connected)")
        else:
            ebone.head = local_head
            ebone.tail = local_tail

        if copy_roll:
            ebone.roll = roll
        aligned += 1

    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"  정렬 완료: {aligned}개")
    return aligned


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════


def main():
    log("=" * 50)
    log("01. ARP 리그 생성")
    log("=" * 50)

    ensure_object_mode()

    # Step 1: 프로필 로드 + 소스 식별
    log("Step 1: 프로필 로드 + 소스 아마추어 식별")
    profile = load_mapping_profile(MAPPING_PROFILE)

    source_obj = find_source_armature(profile)
    if source_obj is None:
        log("소스 아마추어를 찾을 수 없습니다.", "ERROR")
        return

    # Step 2: ARP 리그 추가
    log("Step 2: ARP 리그 추가")
    ensure_object_mode()
    select_only(source_obj)

    try:
        run_arp_operator(bpy.ops.arp.append_arp, rig_preset=profile["arp_preset"])
        log(f"  프리셋: {profile['arp_preset']}")
    except Exception as e:
        log(f"ARP 리그 추가 실패: {e}", "ERROR")
        return

    arp_obj = find_arp_armature()
    if arp_obj is None:
        log("ARP 아마추어를 찾을 수 없습니다.", "ERROR")
        return

    # ARP ref 본 목록 출력 (진단용)
    ref_bones = sorted([b.name for b in arp_obj.data.bones if "ref" in b.name.lower()])
    log(f"  ARP ref 본 ({len(ref_bones)}개):")
    for rb in ref_bones:
        log(f"    {rb}")

    # Step 3: ref 본 위치 정렬
    log("Step 3: ARP ref 본 위치 정렬")
    try:
        aligned = align_ref_bones_to_source(source_obj, arp_obj, profile)
    except Exception as e:
        log(f"ref 본 정렬 실패: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return

    # Step 4: match_to_rig
    log("Step 4: ARP 리그 생성 (match_to_rig)")
    try:
        ensure_object_mode()
        select_only(arp_obj)
        run_arp_operator(bpy.ops.arp.match_to_rig)
        log("  완료")
    except Exception as e:
        log(f"match_to_rig 실패: {e}", "ERROR")
        return

    log("=" * 50)
    log("ARP 리그 생성 완료!")
    log("다음 단계: 02_retarget_animation.py 실행")
    log("=" * 50)


if __name__ == "__main__":
    main()

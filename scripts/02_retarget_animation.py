"""
02. 애니메이션 리타게팅
======================
ARP Remap 기능으로 소스 액션을 ARP 리그에 리타게팅.
01_create_arp_rig.py 실행 후 같은 씬에서 실행.

사용법:
  1. 01_create_arp_rig.py 실행 완료된 .blend 파일에서
  2. 아래 CONFIG의 BMAP_PRESET 확인
  3. ▶ Run Script
"""

import bpy
import traceback

# scripts/ 폴더를 import 경로에 추가
import os, sys

def _find_scripts_dir():
    """scripts/arp_utils.py가 있는 폴더를 찾는다."""
    try:
        d = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(os.path.join(d, "arp_utils.py")):
            return d
    except NameError:
        pass
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
    log, ensure_object_mode, select_only,
    run_arp_operator, find_arp_armature, find_source_armature,
    ensure_retarget_context, install_bmap_preset,
)


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

# .bmap 프리셋 이름 (ARP remap_presets 폴더 내, 확장자 제외)
BMAP_PRESET = "custom_quadruped"


# ═══════════════════════════════════════════════════════════════
# 유틸리티
# ═══════════════════════════════════════════════════════════════

def get_all_actions():
    """모든 액션과 프레임 범위를 수집"""
    actions = []
    for action in bpy.data.actions:
        actions.append({
            'name': action.name,
            'frame_start': int(action.frame_range[0]),
            'frame_end': int(action.frame_range[1]),
        })
    log(f"액션 {len(actions)}개: {[a['name'] for a in actions]}")
    return actions


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════

def main():
    log("=" * 50)
    log("02. 애니메이션 리타게팅")
    log("=" * 50)

    ensure_object_mode()

    # Step 1: 소스/ARP 아마추어 식별
    log("Step 1: 아마추어 식별")
    source_obj = find_source_armature()
    arp_obj = find_arp_armature()

    if source_obj is None:
        log("소스 아마추어를 찾을 수 없습니다.", "ERROR")
        return
    if arp_obj is None:
        log("ARP 아마추어를 찾을 수 없습니다. 01_create_arp_rig.py를 먼저 실행하세요.", "ERROR")
        return

    actions = get_all_actions()
    if not actions:
        log("액션이 없습니다.", "WARN")
        return

    # Step 2: ARP Remap 설정
    log("Step 2: ARP Remap 설정")
    try:
        ensure_retarget_context(source_obj, arp_obj)
        run_arp_operator(bpy.ops.arp.auto_scale)
        log("  auto_scale 완료")

        ensure_object_mode()
        run_arp_operator(bpy.ops.arp.build_bones_list)
        log("  build_bones_list 완료")

        if BMAP_PRESET:
            install_bmap_preset(BMAP_PRESET)
            try:
                run_arp_operator(bpy.ops.arp.import_config_preset, preset_name=BMAP_PRESET)
                log(f"  .bmap 로드 성공: {BMAP_PRESET}")
            except Exception as e:
                log(f"  .bmap 로드 실패: {e}", "WARN")

        run_arp_operator(bpy.ops.arp.redefine_rest_pose, preserve=True)
        run_arp_operator(bpy.ops.arp.save_pose_rest)
        ensure_object_mode()
        log("  레스트 포즈 조정 완료")

    except Exception as e:
        log(f"Remap 설정 실패: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")
        return

    # Step 3: 액션별 리타게팅
    log("Step 3: 액션별 리타게팅")
    success = 0
    fail = 0

    for i, act in enumerate(actions):
        name = act['name']
        f_start = act['frame_start']
        f_end = act['frame_end']

        log(f"  [{i+1}/{len(actions)}] '{name}' ({f_start}~{f_end})")

        try:
            action = bpy.data.actions.get(name)
            if action is None:
                fail += 1
                continue

            if source_obj.animation_data is None:
                source_obj.animation_data_create()
            source_obj.animation_data.action = action

            ensure_object_mode()
            select_only(arp_obj)  # retarget은 타겟 아마추어가 active여야 함
            run_arp_operator(
                bpy.ops.arp.retarget,
                frame_start=f_start,
                frame_end=f_end,
                fake_user_action=True,
                interpolation_type='LINEAR',
            )
            success += 1
            log(f"    OK")

        except Exception as e:
            fail += 1
            log(f"    실패: {e}", "WARN")

    log("=" * 50)
    log(f"리타게팅 완료: {success}/{len(actions)} 성공, {fail} 실패")
    log("=" * 50)


if __name__ == "__main__":
    main()

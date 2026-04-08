"""
파이프라인 러너 — 비대화형 CLI 변환 경로
==========================================
사용법:
  blender --background <file.blend> --python pipeline_runner.py -- --auto
  blender --background <file.blend> --python pipeline_runner.py -- --auto --retarget

플래그:
  --auto       자동 역할 추론 모드 (addon operator 호출)
  --retarget   리타겟까지 실행 (setup + ARP retarget + scale copy + cleanup)
  --no-save    .blend 저장 안 함
  --profile X  (deprecated) 레거시 프로필 기반 변환

Addon operator 호출 기반으로 동작하며, addon UI와 동일한 실행 경로를 사용한다.
"""

import json
import os
import sys
import time
import traceback

import bpy

# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

MAPPING_PROFILE = "custom_quadruped"
SAVE_BLEND = True


# ═══════════════════════════════════════════════════════════════
# 커맨드라인 인자 파싱
# ═══════════════════════════════════════════════════════════════


def parse_args():
    """'--' 이후의 커맨드라인 인자를 파싱"""
    argv = sys.argv
    if "--" not in argv:
        return {}

    args = {}
    custom_args = argv[argv.index("--") + 1 :]
    i = 0
    while i < len(custom_args):
        if custom_args[i] == "--profile" and i + 1 < len(custom_args):
            args["profile"] = custom_args[i + 1]
            i += 2
        elif custom_args[i] == "--no-save":
            args["save"] = False
            i += 1
        elif custom_args[i] == "--auto":
            args["auto"] = True
            i += 1
        elif custom_args[i] == "--retarget":
            args["retarget"] = True
            i += 1
        elif custom_args[i] == "--bake":
            # deprecated: --retarget으로 대체
            args["retarget"] = True
            i += 1
        elif custom_args[i] == "--bmap" and i + 1 < len(custom_args):
            args["bmap"] = custom_args[i + 1]
            i += 2
        else:
            i += 1
    return args


# ═══════════════════════════════════════════════════════════════
# 스크립트 경로 설정
# ═══════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════
# 결과 기록
# ═══════════════════════════════════════════════════════════════


class ConversionResult:
    """변환 결과 수집 및 JSON 저장"""

    def __init__(self):
        self.success = False
        self.steps_completed = []
        self.errors = []
        self.warnings = []
        self.pre_state = {}
        self.post_state = {}
        self.elapsed_sec = 0

    def add_step(self, step_name):
        self.steps_completed.append(step_name)

    def add_error(self, msg):
        self.errors.append(msg)

    def add_warning(self, msg):
        self.warnings.append(msg)

    def save(self, output_dir):
        """conversion_result.json 저장"""
        path = os.path.join(output_dir, "conversion_result.json")
        data = {
            "success": self.success,
            "steps_completed": self.steps_completed,
            "errors": self.errors,
            "warnings": self.warnings,
            "pre_state": self.pre_state,
            "post_state": self.post_state,
            "elapsed_sec": round(self.elapsed_sec, 1),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return path


# ═══════════════════════════════════════════════════════════════
# 상태 스냅샷
# ═══════════════════════════════════════════════════════════════


def snapshot_state():
    """현재 씬의 아마추어/액션 상태를 딕셔너리로 반환"""
    armatures = []
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE":
            c_bones = len([b for b in obj.data.bones if b.name.startswith("c_")])
            armatures.append(
                {
                    "name": obj.name,
                    "bone_count": len(obj.data.bones),
                    "is_arp": c_bones > 5,
                }
            )

    actions = []
    for action in bpy.data.actions:
        actions.append(
            {
                "name": action.name,
                "frame_start": int(action.frame_range[0]),
                "frame_end": int(action.frame_range[1]),
            }
        )

    return {
        "armatures": armatures,
        "action_count": len(actions),
        "actions": actions,
    }


# ═══════════════════════════════════════════════════════════════
# 메인: --auto 모드 (operator 기반)
# ═══════════════════════════════════════════════════════════════


def _run_auto(cli_args, result):
    """addon operator를 순서대로 호출하여 변환 + 리타겟을 실행한다."""
    from arp_utils import ensure_object_mode, find_source_armature, log, select_only

    ensure_object_mode()

    # 소스 아마추어 선택
    source_obj = find_source_armature()
    if source_obj is None:
        result.add_error("소스 아마추어를 찾을 수 없습니다.")
        raise RuntimeError("소스 아마추어 미발견")
    log(f"소스 아마추어: '{source_obj.name}'")
    select_only(source_obj)
    result.add_step("source_detected")

    # Step 1-2: Create Preview (분석 + DEF 본 + Preview)
    log("=" * 50)
    log("Step 1-2: Create Preview")
    log("=" * 50)
    ret = bpy.ops.arp_convert.create_preview()
    if ret != {"FINISHED"}:
        result.add_error(f"Create Preview 실패: {ret}")
        raise RuntimeError("Create Preview 실패")
    result.add_step("preview_created")

    # Step 3: Build Rig (ARP append + align + match + cc_ + weights + bone_pairs)
    log("=" * 50)
    log("Step 3: Build Rig")
    log("=" * 50)
    ret = bpy.ops.arp_convert.build_rig()
    if ret != {"FINISHED"}:
        result.add_error(f"Build Rig 실패: {ret}")
        raise RuntimeError("Build Rig 실패")
    result.add_step("rig_built")

    # --retarget: 리타겟 실행
    if cli_args.get("retarget"):
        log("=" * 50)
        log("Step 4: Setup Retarget + ARP Retarget")
        log("=" * 50)

        ret = bpy.ops.arp_convert.setup_retarget()
        if ret != {"FINISHED"}:
            result.add_error(f"Setup Retarget 실패: {ret}")
            raise RuntimeError("Setup Retarget 실패")
        result.add_step("retarget_setup")

        # ARP 네이티브 리타겟 실행
        ret = bpy.ops.arp.retarget()
        if ret != {"FINISHED"}:
            result.add_error(f"ARP Retarget 실패: {ret}")
            raise RuntimeError("ARP Retarget 실패")
        result.add_step("retarget_executed")

        # 커스텀 본 스케일 복사
        bpy.ops.arp_convert.copy_custom_scale()
        result.add_step("custom_scale_copied")

        # Cleanup (소스/프리뷰 삭제 + 액션 rename)
        log("=" * 50)
        log("Step 5: Cleanup")
        log("=" * 50)
        ret = bpy.ops.arp_convert.cleanup()
        if ret != {"FINISHED"}:
            result.add_warning(f"Cleanup 경고: {ret}")
        result.add_step("cleanup_done")


# ═══════════════════════════════════════════════════════════════
# 메인: --profile 레거시 모드
# ═══════════════════════════════════════════════════════════════


def _run_legacy_profile(cli_args, result):
    """레거시 프로필 기반 변환. --profile 플래그 사용.

    deprecated: --auto 모드를 사용하세요.
    """
    from arp_utils import (
        ensure_object_mode,
        find_arp_armature,
        find_source_armature,
        load_mapping_profile,
        log,
        run_arp_operator,
        select_only,
    )

    print("[WARN] --profile 모드는 deprecated입니다. --auto 모드를 사용하세요.")
    result.add_warning("--profile 모드 deprecated")

    profile_name = cli_args.get("profile", MAPPING_PROFILE)
    ensure_object_mode()

    source_obj = find_source_armature()
    if source_obj is None:
        result.add_error("소스 아마추어를 찾을 수 없습니다.")
        raise RuntimeError("소스 아마추어 미발견")
    log(f"소스 아마추어: '{source_obj.name}'")
    result.add_step("source_detected")

    from skeleton_analyzer import analyze_skeleton

    analysis = analyze_skeleton(source_obj)
    if "error" in analysis:
        result.add_error(f"구조 분석 실패: {analysis['error']}")
        raise RuntimeError(analysis["error"])
    result.add_step("source_analyzed")

    profile = load_mapping_profile(profile_name)
    deform_to_ref = profile["deform_to_ref"]
    arp_preset = profile.get("arp_preset", "dog")
    result.add_step("profile_loaded")

    # ARP 리그 추가
    ensure_object_mode()
    select_only(source_obj)
    run_arp_operator(bpy.ops.arp.append_arp, rig_preset=arp_preset)
    result.add_step("arp_appended")

    arp_obj = find_arp_armature()
    if arp_obj is None:
        result.add_error("ARP 아마추어 생성 실패")
        raise RuntimeError("ARP 아마추어 미발견")

    # ref 본 위치 정렬
    from mathutils import Vector

    ensure_object_mode()
    bpy.context.view_layer.objects.active = source_obj
    bpy.ops.object.mode_set(mode="EDIT")
    src_matrix = source_obj.matrix_world
    source_positions = {}
    for ebone in source_obj.data.edit_bones:
        world_head = src_matrix @ ebone.head.copy()
        world_tail = src_matrix @ ebone.tail.copy()
        source_positions[ebone.name] = (world_head, world_tail, ebone.roll)
    bpy.ops.object.mode_set(mode="OBJECT")

    resolved = {}
    for src_name, ref_name in deform_to_ref.items():
        if src_name in source_positions:
            resolved[ref_name] = source_positions[src_name]

    bpy.context.view_layer.objects.active = arp_obj
    bpy.ops.object.mode_set(mode="EDIT")
    arp_matrix_inv = arp_obj.matrix_world.inverted()
    edit_bones = arp_obj.data.edit_bones
    aligned = 0

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
            continue
        local_head = arp_matrix_inv @ world_head
        local_tail = arp_matrix_inv @ world_tail
        if (local_tail - local_head).length < 0.0001:
            local_tail = local_head + Vector((0, 0.01, 0))
        if ebone.use_connect and ebone.parent:
            ebone.tail = local_tail
        else:
            ebone.head = local_head
            ebone.tail = local_tail
        ebone.roll = roll
        aligned += 1

    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"ref 본 정렬 완료: {aligned}개")
    result.add_step("ref_bones_aligned")

    ensure_object_mode()
    select_only(arp_obj)
    run_arp_operator(bpy.ops.arp.match_to_rig)
    result.add_step("rig_generated")
    log("ARP 리그 생성 완료 (레거시 프로필 모드)")


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════


def main():
    start_time = time.time()
    result = ConversionResult()

    cli_args = parse_args()
    save_blend = cli_args.get("save", SAVE_BLEND)
    auto_mode = cli_args.get("auto", False)

    blend_path = bpy.data.filepath
    if not blend_path:
        print("[ERROR] .blend 파일이 저장되지 않은 상태입니다.")
        return
    output_dir = os.path.dirname(blend_path)

    mode_str = "자동 분석 (operator)" if auto_mode else "레거시 프로필"
    print("=" * 60)
    print("파이프라인 러너 시작")
    print(f"  파일: {blend_path}")
    print(f"  모드: {mode_str}")
    if cli_args.get("retarget"):
        print("  리타겟: 활성화")
    print("=" * 60)

    result.pre_state = snapshot_state()
    result.add_step("state_recorded")

    try:
        if auto_mode:
            _run_auto(cli_args, result)
        else:
            _run_legacy_profile(cli_args, result)
    except Exception as e:
        result.add_error(f"실패: {e}")
        from arp_utils import log

        log(traceback.format_exc(), "ERROR")
        result.elapsed_sec = time.time() - start_time
        result.save(output_dir)
        return

    if save_blend:
        bpy.ops.wm.save_mainfile()
        result.add_step("blend_saved")

    result.post_state = snapshot_state()
    result.success = len(result.errors) == 0
    result.elapsed_sec = time.time() - start_time

    result_path = result.save(output_dir)

    print("=" * 60)
    print(f"파이프라인 완료: {'성공' if result.success else '실패'}")
    print(f"  소요시간: {result.elapsed_sec:.1f}초")
    print(f"  결과 파일: {result_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()

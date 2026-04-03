"""
파이프라인 러너
===============
단일 .blend 파일에 대해 01_create_arp_rig을 실행하고 결과를 저장.
결과를 conversion_result.json으로 저장.

사용법 (Blender 커맨드라인):
  blender --background <file.blend> --python scripts/pipeline_runner.py -- --profile custom_quadruped

사용법 (Blender 스크립팅 탭):
  아래 CONFIG 수정 후 ▶ Run Script
"""

import json
import os
import sys
import time
import traceback

import bpy

# ═══════════════════════════════════════════════════════════════
# CONFIG (커맨드라인 인자로 오버라이드 가능)
# ═══════════════════════════════════════════════════════════════

MAPPING_PROFILE = "custom_quadruped"
SAVE_BLEND = True  # 변환 완료 후 .blend 저장 여부


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
        elif custom_args[i] == "--bake":
            args["bake"] = True
            i += 1
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


def _remove_temp_armature(obj):
    if obj is None:
        return
    arm_data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if arm_data.users == 0:
        bpy.data.armatures.remove(arm_data, do_unlink=True)


# ═══════════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════════


def main():
    start_time = time.time()
    result = ConversionResult()

    # 인자 파싱
    cli_args = parse_args()
    profile_name = cli_args.get("profile", MAPPING_PROFILE)
    save_blend = cli_args.get("save", SAVE_BLEND)
    auto_mode = cli_args.get("auto", False)

    # 출력 디렉토리 결정
    blend_path = bpy.data.filepath
    if not blend_path:
        print("[ERROR] .blend 파일이 저장되지 않은 상태입니다.")
        return
    output_dir = os.path.dirname(blend_path)

    mode_str = "자동 분석" if auto_mode else f"프로필: {profile_name}"
    print("=" * 60)
    print("파이프라인 러너 시작")
    print(f"  파일: {blend_path}")
    print(f"  모드: {mode_str}")
    print("=" * 60)

    # 사전 상태 기록
    result.pre_state = snapshot_state()
    result.add_step("state_recorded")

    analysis = None

    # Step 1: ARP 리그 생성
    print("\n--- Step 1: ARP 리그 생성 ---")
    try:
        from arp_utils import (
            ensure_object_mode,
            find_arp_armature,
            find_mesh_objects,
            find_source_armature,
            load_mapping_profile,
            log,
            run_arp_operator,
            select_only,
        )

        ensure_object_mode()

        # 소스 아마추어 식별
        source_obj = find_source_armature()
        if source_obj is None:
            result.add_error("소스 아마추어를 찾을 수 없습니다.")
            raise RuntimeError("소스 아마추어 미발견")
        log(f"소스 아마추어: '{source_obj.name}'")
        result.add_step("source_detected")

        if analysis is None:
            from skeleton_analyzer import analyze_skeleton

            analysis = analyze_skeleton(source_obj)
            if "error" in analysis:
                result.add_error(f"구조 분석 실패: {analysis['error']}")
                raise RuntimeError(analysis["error"])
            result.add_step("source_analyzed")

        # 매핑 생성 (자동 분석 또는 프로필)
        if auto_mode:
            from skeleton_analyzer import (
                generate_arp_mapping,
                generate_verification_report,
                save_auto_mapping,
            )

            print(generate_verification_report(analysis))
            save_auto_mapping(analysis, output_dir)

            mapping = generate_arp_mapping(analysis)
            deform_to_ref = mapping["deform_to_ref"]
            arp_preset = mapping.get("arp_preset", "dog")
            result.add_step("auto_analyzed")
        else:
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

        # 소스 본 위치 추출
        bpy.context.view_layer.objects.active = source_obj
        bpy.ops.object.mode_set(mode="EDIT")
        src_matrix = source_obj.matrix_world
        source_positions = {}
        for ebone in source_obj.data.edit_bones:
            world_head = src_matrix @ ebone.head.copy()
            world_tail = src_matrix @ ebone.tail.copy()
            source_positions[ebone.name] = (world_head, world_tail, ebone.roll)
        bpy.ops.object.mode_set(mode="OBJECT")

        # 목표 위치 결정
        resolved = {}
        for src_name, ref_name in deform_to_ref.items():
            if src_name in source_positions:
                resolved[ref_name] = source_positions[src_name]

        # ARP ref 본에 위치 적용 (하이어라키 순서: 부모 → 자식)
        bpy.context.view_layer.objects.active = arp_obj
        bpy.ops.object.mode_set(mode="EDIT")
        arp_matrix_inv = arp_obj.matrix_world.inverted()
        edit_bones = arp_obj.data.edit_bones
        aligned = 0

        # 하이어라키 깊이순 정렬 (부모 먼저 처리)
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

        # match_to_rig
        ensure_object_mode()
        select_only(arp_obj)
        run_arp_operator(bpy.ops.arp.match_to_rig)
        result.add_step("rig_generated")
        log("ARP 리그 생성 완료")

        # F12: 애니메이션 베이크 (--bake 플래그 시)
        if cli_args.get("bake"):
            from arp_utils import (
                BAKE_PAIRS_KEY,
                bake_all_actions,
                deserialize_bone_pairs,
                preflight_check_transforms,
            )

            log("=" * 50)
            log("F12: 애니메이션 베이크")
            log("=" * 50)

            error = preflight_check_transforms(source_obj, arp_obj)
            if error:
                log(f"Preflight 실패: {error}", "ERROR")
                result.add_error(f"베이크 Preflight 실패: {error}")
            else:
                raw_pairs = arp_obj.get(BAKE_PAIRS_KEY)
                if raw_pairs:
                    bone_pairs = deserialize_bone_pairs(raw_pairs)
                    created = bake_all_actions(source_obj, arp_obj, bone_pairs)
                    result.add_step("animation_baked")
                    log(f"베이크 완료: {len(created)}개 액션")
                else:
                    log("bone_pairs 없음 — 베이크 건너뜀", "WARN")

    except Exception as e:
        result.add_error(f"리그 생성 실패: {e}")
        log(traceback.format_exc(), "ERROR")
        result.elapsed_sec = time.time() - start_time
        result.save(output_dir)
        return

    # 저장
    if save_blend:
        bpy.ops.wm.save_mainfile()
        result.add_step("blend_saved")

    # 사후 상태 기록
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

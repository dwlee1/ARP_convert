"""
Rigify → AutoRig Pro 변환 스크립트 (PoC)
==========================================
Blender 4.5 LTS + AutoRig Pro 에서 실행

사용법:
  1. 변환할 Rigify 리그가 있는 .blend 파일을 Blender에서 열기
  2. Scripting 탭에서 이 스크립트 열기
  3. 아래 CONFIG 섹션의 경로 설정 확인
  4. ▶ Run Script 실행

또는 커맨드라인:
  blender myfile.blend --python rigify_to_arp.py
"""

import bpy
import os
import sys
import json
import traceback
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 본 매핑 데이터 (내장)
# 출처: https://github.com/israelandrewbrown/AutoRigPro-to-Rigify
# ═══════════════════════════════════════════════════════════════

# ─── 커스텀 리그 → ARP 변형 본 매핑 ───
# fox_AllAni_240311.blend 분석 결과 기반
# 변형(deform) 본만 매핑, IK컨트롤/폴벡터는 제외
DEFORM_BONE_MAPPING = {
    # 스파인 / 몸통
    "root":       "root_ref.x",
    "center":     "root_ref.x",       # center가 실질적 루트일 수 있음
    "pelvis":     "spine_01_ref.x",
    "spine01":    "spine_02_ref.x",
    "spine02":    "spine_03_ref.x",
    "chest":      "spine_03_ref.x",    # chest ↔ spine 상위 (중복 시 조정)
    "neck":       "neck_ref.x",
    "head":       "head_ref.x",
    "jaw":        "head_ref.x",        # jaw는 head에 매핑 (별도 jaw 본 없을 때)
    # 앞다리 (사족보행 = arm 계열)
    "shoulder_L": "shoulder_ref.l",
    "upperarm_L": "arm_ref.l",
    "arm_L":      "forearm_ref.l",
    "hand_L":     "hand_ref.l",
    "shoulder_R": "shoulder_ref.r",
    "upperarm_R": "arm_ref.r",
    "arm_R":      "forearm_ref.r",
    "hand_R":     "hand_ref.r",
    # 뒷다리
    "thigh_L":    "thigh_ref.l",
    "leg_L":      "leg_ref.l",
    "foot_L":     "foot_ref.l",
    "toe_L":      "toes_ref.l",
    "thigh_R":    "thigh_ref.r",
    "leg_R":      "leg_ref.r",
    "foot_R":     "foot_ref.r",
    "toe_R":      "toes_ref.r",
    # 꼬리
    "tail_01":    "tail_00_ref.x",
    "tail02":     "tail_01_ref.x",
    "tail03":     "tail_02_ref.x",
    "tail04":     "tail_03_ref.x",
}

# IK/컨트롤 본 — 변환 시 무시 (ARP가 자체 IK 생성)
IK_CONTROL_BONES = [
    "L_backfoot_ctrl", "R_backfoot_ctrl",
    "L_foot_IK", "R_foot_IK",
    "L_leg_IK", "R_leg_IK",
    "L_thigh_PV", "R_thigh_PV",
    "L_leg_PV", "R_leg_PV",
    "toe_heel_L", "toe_heel_R",
    "toe_up_L", "toe_up_R",
    "Larm_IK", "Rarm_IK",
]


def source_to_arp_name(bone_name):
    """소스 본 이름 → ARP 레퍼런스 본 이름 변환. 매핑 없으면 None."""
    if bone_name in DEFORM_BONE_MAPPING:
        return DEFORM_BONE_MAPPING[bone_name]
    if bone_name in IK_CONTROL_BONES:
        return None  # IK/컨트롤은 무시
    return None  # 매핑 없음


# ═══════════════════════════════════════════════════════════════
# CONFIG — 필요에 따라 수정
# ═══════════════════════════════════════════════════════════════

# 프로젝트 루트 (자동 감지)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""

# ARP 아마추어 프리셋 (armature_presets 폴더 내 .blend 파일명, 확장자 제외)
# 사용 가능: dog, horse, bird, human, free, cs, master, horse_ik_spine
ARP_RIG_PRESET = "dog"

# .bmap 프리셋 이름 (확장자 제외)
# custom_quadruped = Fox 등 커스텀 리그용, rigify_quadruped = DEF- 기반
BMAP_PRESET_NAME = "custom_quadruped"

# 변환 결과 저장 경로 (None이면 원본 옆에 _arp 접미사로 저장)
OUTPUT_PATH = None

# FBX 익스포트 테스트 여부 (ARP 익스포트 기능을 수동으로 사용할 경우 False)
TEST_FBX_EXPORT = False

# 로그 레벨
VERBOSE = True


# ═══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════

def log(msg, level="INFO"):
    """로그 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def find_source_armature():
    """
    씬에서 변환 대상 아마추어를 찾는다.
    ARP 아마추어(c_ 본)가 아닌 아마추어 중에서
    매핑 가능한 본이 가장 많은 것을 선택.
    """
    best_obj = None
    best_match = 0

    for obj in bpy.data.objects:
        if obj.type != 'ARMATURE':
            continue
        arm = obj.data

        # ARP 아마추어는 제외
        c_bones = [b for b in arm.bones if b.name.startswith('c_')]
        if len(c_bones) > 5:
            continue

        # 매핑 가능한 본 수 계산
        mapped = [b for b in arm.bones if source_to_arp_name(b.name) is not None]
        if len(mapped) > best_match:
            best_match = len(mapped)
            best_obj = obj

    if best_obj:
        arm = best_obj.data
        total = len(arm.bones)
        log(f"소스 아마추어 발견: '{best_obj.name}' (본 {total}개, 매핑 가능 {best_match}개)")
        unmapped = [b.name for b in arm.bones if source_to_arp_name(b.name) is None and b.name not in IK_CONTROL_BONES]
        if unmapped:
            log(f"  매핑 안 되는 본: {unmapped}", "WARN")
    return best_obj


def find_arp_armature():
    """
    씬에서 ARP 아마추어를 찾는다.
    'rig' 이름이거나 c_ 접두사 본이 있는 아마추어.
    """
    for obj in bpy.data.objects:
        if obj.type != 'ARMATURE':
            continue
        arm = obj.data
        arp_bones = [b for b in arm.bones if b.name.startswith('c_')]
        if len(arp_bones) > 5:
            log(f"ARP 아마추어 발견: '{obj.name}' (c_ 본 {len(arp_bones)}개)")
            return obj
    return None


def find_mesh_objects(armature_obj):
    """
    특정 아마추어에 바인딩된 메시 오브젝트들을 찾는다.
    Armature 모디파이어가 있는 메시를 검색.
    """
    meshes = []
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature_obj:
                meshes.append(obj)
                break
    log(f"'{armature_obj.name}'에 바인딩된 메시: {len(meshes)}개 — {[m.name for m in meshes]}")
    return meshes


def get_all_actions():
    """모든 액션과 프레임 범위를 수집"""
    actions_info = []
    for action in bpy.data.actions:
        frame_start = int(action.frame_range[0])
        frame_end = int(action.frame_range[1])
        keyframe_count = sum(len(fc.keyframe_points) for fc in action.fcurves)
        actions_info.append({
            'name': action.name,
            'frame_start': frame_start,
            'frame_end': frame_end,
            'keyframe_count': keyframe_count,
        })
    log(f"액션 {len(actions_info)}개 발견: {[a['name'] for a in actions_info]}")
    return actions_info


def extract_bone_data(armature_obj):
    """
    소스 아마추어의 본 위치 데이터를 추출하여
    ARP import_rig_data 형식 (.py dict)으로 변환.
    """
    arm = armature_obj.data
    arp_data = {}

    # Edit 모드에서 본 데이터 접근 (head, tail, roll)
    bpy.context.view_layer.objects.active = armature_obj
    bpy.ops.object.mode_set(mode='EDIT')

    for ebone in arm.edit_bones:
        arp_name = source_to_arp_name(ebone.name)
        if arp_name is None:
            if VERBOSE:
                log(f"  매핑 없음 (패스스루 대상): {ebone.name}", "WARN")
            continue

        # ARP 리그 데이터 형식: (head_xyz, tail_xyz, roll)
        head = list(ebone.head)
        tail = list(ebone.tail)
        roll = ebone.roll
        arp_data[arp_name] = (head, tail, roll)

        if VERBOSE:
            log(f"  매핑: {ebone.name} → {arp_name}")

    bpy.ops.object.mode_set(mode='OBJECT')

    log(f"본 매핑 완료: {len(arp_data)}개 매핑됨")
    return arp_data


def save_arp_rig_data(arp_data, filepath):
    """ARP 리그 데이터를 .py 파일로 저장 (import_rig_data 형식)"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(repr(arp_data))
    log(f"ARP 리그 데이터 저장: {filepath}")


def get_3d_viewport_context():
    """
    3D Viewport의 컨텍스트를 가져온다.
    ARP 오퍼레이터는 3D Viewport 컨텍스트에서 실행해야 함.
    (Scripting 탭에서 실행 시 SpaceTextEditor라서 overlay 에러 발생)
    """
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return {
                            'window': window,
                            'screen': window.screen,
                            'area': area,
                            'region': region,
                            'scene': bpy.context.scene,
                            'view_layer': bpy.context.view_layer,
                        }
    log("3D Viewport를 찾을 수 없습니다! 3D Viewport가 열려있어야 합니다.", "ERROR")
    return None


def run_arp_operator(op_func, **kwargs):
    """
    ARP 오퍼레이터를 3D Viewport 컨텍스트에서 실행.
    Blender 4.x의 temp_override 사용.
    """
    ctx = get_3d_viewport_context()
    if ctx is None:
        raise RuntimeError("3D Viewport 컨텍스트를 찾을 수 없습니다.")
    with bpy.context.temp_override(**ctx):
        return op_func(**kwargs)


def select_only(obj):
    """오브젝트 하나만 선택 & 활성화"""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def ensure_object_mode():
    """Object 모드로 전환"""
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


# ═══════════════════════════════════════════════════════════════
# 메인 변환 파이프라인
# ═══════════════════════════════════════════════════════════════

def convert_to_arp():
    """
    소스 리그 → ARP 변환 메인 함수.

    수정된 파이프라인 (v2):
    1. 소스 아마추어 식별
    2. 변환 전 상태 기록
    3. ARP 리그 추가 (dog 프리셋, 기본 위치)
    4. ARP 리그 생성 (match_to_rig)
    5. Remap으로 애니메이션 리타게팅 (auto_scale이 크기 차이 처리)
    6. FBX 익스포트 테스트

    핵심 변경: import_rig_data 제거 — ARP를 기본 위치로 생성하고
    Remap이 크기/위치 차이를 자동 처리하게 함.
    메시 리바인딩은 별도 단계로 분리 (Phase 2에서 처리).
    """

    result = {
        'success': False,
        'steps_completed': [],
        'errors': [],
        'warnings': [],
    }

    try:
        ensure_object_mode()

        # ─── Step 1: 소스 아마추어 식별 ───
        log("=" * 50)
        log("Step 1: 소스 아마추어 식별")
        log("=" * 50)

        source_obj = find_source_armature()
        if source_obj is None:
            result['errors'].append("소스 아마추어를 찾을 수 없습니다.")
            return result

        mesh_objects = find_mesh_objects(source_obj)
        pre_actions = get_all_actions()
        result['pre_actions'] = pre_actions
        result['steps_completed'].append('source_detected')

        # ─── Step 2: 변환 전 상태 기록 ───
        log("=" * 50)
        log("Step 2: 변환 전 상태 기록")
        log("=" * 50)

        pre_state = {
            'source_name': source_obj.name,
            'mapped_bone_count': len([b for b in source_obj.data.bones if source_to_arp_name(b.name) is not None]),
            'total_bone_count': len(source_obj.data.bones),
            'mesh_count': len(mesh_objects),
            'action_count': len(pre_actions),
        }
        result['pre_state'] = pre_state
        log(f"  매핑 가능 본: {pre_state['mapped_bone_count']}개")
        log(f"  메시: {pre_state['mesh_count']}개")
        log(f"  액션: {pre_state['action_count']}개")
        result['steps_completed'].append('state_recorded')

        # ─── Step 3: ARP 리그 추가 (기본 위치) ───
        log("=" * 50)
        log("Step 3: ARP 리그 추가 (기본 위치)")
        log("=" * 50)

        ensure_object_mode()
        select_only(source_obj)

        try:
            run_arp_operator(bpy.ops.arp.append_arp, rig_preset=ARP_RIG_PRESET)
            log(f"ARP 리그 추가 완료 (프리셋: {ARP_RIG_PRESET})")
            result['steps_completed'].append('arp_appended')
        except Exception as e:
            result['errors'].append(f"ARP 리그 추가 실패: {e}")
            log(f"ARP 리그 추가 실패: {e}", "ERROR")
            return result

        arp_obj = find_arp_armature()
        if arp_obj is None:
            result['errors'].append("ARP 아마추어를 찾을 수 없습니다.")
            return result

        # ─── Step 4: ARP 리그 생성 ───
        log("=" * 50)
        log("Step 4: ARP 리그 생성 (Match to Rig)")
        log("=" * 50)

        try:
            ensure_object_mode()
            select_only(arp_obj)
            run_arp_operator(bpy.ops.arp.match_to_rig)
            log("ARP 리그 생성 완료")
            result['steps_completed'].append('rig_generated')
        except Exception as e:
            result['errors'].append(f"ARP 리그 생성 실패: {e}")
            log(f"ARP 리그 생성 실패: {e}", "ERROR")
            return result

        # ─── Step 4.5: ARP 팔(앞다리) IK→FK 전환 ───
        log("=" * 50)
        log("Step 4.5: ARP 앞다리 IK→FK 전환")
        log("=" * 50)

        try:
            ensure_object_mode()
            select_only(arp_obj)
            bpy.ops.object.mode_set(mode='POSE')

            # ARP의 모든 커스텀 프로퍼티를 탐색하여 IK/FK 관련 프로퍼티 찾기
            ik_fk_switched = 0
            ik_fk_props_found = []

            for pbone in arp_obj.pose.bones:
                for prop_name in pbone.keys():
                    # rna_type 등 내부 프로퍼티 무시
                    if prop_name.startswith('_') or prop_name == 'rna_type':
                        continue
                    prop_lower = prop_name.lower()
                    # IK/FK 관련 프로퍼티 찾기
                    if 'ik' in prop_lower and 'fk' in prop_lower:
                        old_val = pbone[prop_name]
                        ik_fk_props_found.append(f"{pbone.name}['{prop_name}'] = {old_val}")
                        # FK로 전환 (ARP에서 보통 1.0 = FK, 0.0 = IK)
                        try:
                            pbone[prop_name] = 1.0
                            ik_fk_switched += 1
                            log(f"  {pbone.name}['{prop_name}']: {old_val} → 1.0 (FK)")
                        except:
                            log(f"  {pbone.name}['{prop_name}']: 변경 실패 (읽기 전용?)", "WARN")

            bpy.ops.object.mode_set(mode='OBJECT')

            if ik_fk_switched > 0:
                log(f"  IK→FK 전환 완료: {ik_fk_switched}개 스위치")
            elif ik_fk_props_found:
                log(f"  프로퍼티 발견했으나 전환 실패: {ik_fk_props_found}", "WARN")
            else:
                # IK/FK 프로퍼티 못 찾으면 전체 커스텀 프로퍼티 덤프
                log("  IK/FK 프로퍼티 못 찾음. 커스텀 프로퍼티 탐색:", "WARN")
                for pbone in arp_obj.pose.bones:
                    custom_props = [k for k in pbone.keys() if not k.startswith('_')]
                    if custom_props and ('hand' in pbone.name.lower() or 'foot' in pbone.name.lower() or 'arm' in pbone.name.lower() or 'leg' in pbone.name.lower()):
                        log(f"    {pbone.name}: {custom_props}")
                result['warnings'].append("IK/FK 스위치를 자동 전환하지 못함")

        except Exception as e:
            log(f"  IK→FK 전환 실패 (계속 진행): {e}", "WARN")
            ensure_object_mode()

        # ─── Step 5: Remap 애니메이션 리타게팅 ───
        log("=" * 50)
        log("Step 5: Remap 애니메이션 리타게팅")
        log("=" * 50)

        if len(pre_actions) > 0:
            try:
                ensure_object_mode()

                # 소스/타겟 설정
                bpy.context.scene.source_rig = source_obj.name
                bpy.context.scene.target_rig = arp_obj.name
                log(f"  소스: {source_obj.name}")
                log(f"  타겟: {arp_obj.name}")

                # auto_scale — 소스↔타겟 크기 자동 맞춤
                run_arp_operator(bpy.ops.arp.auto_scale)
                log("  auto_scale 완료")

                # 본 매핑 구축
                run_arp_operator(bpy.ops.arp.build_bones_list)
                log("  build_bones_list 완료")

                # .bmap 프리셋 로드 시도
                bmap_loaded = False
                try:
                    run_arp_operator(bpy.ops.arp.import_config_preset, preset_name=BMAP_PRESET_NAME)
                    log(f"  .bmap 프리셋 로드 성공: {BMAP_PRESET_NAME}")
                    bmap_loaded = True
                except Exception as e:
                    log(f"  .bmap 프리셋 로드 실패 — ARP 자동 매핑 사용: {e}", "WARN")
                    result['warnings'].append(f".bmap 프리셋 미사용, ARP 자동 매핑")

                # 레스트 포즈 조정 (소스 포즈를 타겟에 맞춤)
                run_arp_operator(bpy.ops.arp.redefine_rest_pose, preserve=True)
                run_arp_operator(bpy.ops.arp.save_pose_rest)
                ensure_object_mode()
                log("  레스트 포즈 조정 완료")

                # ── 액션별 리타게팅 ──
                # 소스 아마추어에 각 액션을 활성화하고 리타게팅
                retarget_success = 0
                retarget_fail = 0

                for i, action_info in enumerate(pre_actions):
                    action_name = action_info['name']
                    frame_start = action_info['frame_start']
                    frame_end = action_info['frame_end']

                    log(f"  [{i+1}/{len(pre_actions)}] 리타게팅: '{action_name}' ({frame_start}~{frame_end})")

                    try:
                        # 소스 아마추어에 액션 설정
                        action = bpy.data.actions.get(action_name)
                        if action is None:
                            log(f"    액션 '{action_name}' 찾을 수 없음", "WARN")
                            retarget_fail += 1
                            continue

                        if source_obj.animation_data is None:
                            source_obj.animation_data_create()
                        source_obj.animation_data.action = action

                        ensure_object_mode()

                        run_arp_operator(
                            bpy.ops.arp.retarget,
                            frame_start=frame_start,
                            frame_end=frame_end,
                            fake_user_action=True,
                            interpolation_type='LINEAR',
                        )
                        retarget_success += 1
                        log(f"    ✓ 성공")

                    except Exception as e:
                        retarget_fail += 1
                        log(f"    ✗ 실패: {e}", "WARN")

                log(f"  리타게팅 완료: {retarget_success}/{len(pre_actions)} 성공, {retarget_fail} 실패")
                result['retarget_success'] = retarget_success
                result['retarget_fail'] = retarget_fail
                result['steps_completed'].append('retargeted')

            except Exception as e:
                result['errors'].append(f"리타게팅 실패: {e}")
                log(f"리타게팅 실패: {e}", "ERROR")
                log(traceback.format_exc(), "ERROR")
        else:
            log("  액션 없음 — 리타게팅 스킵")
            result['steps_completed'].append('retarget_skipped')

        # ─── Step 6: FBX 익스포트 테스트 ───
        if TEST_FBX_EXPORT:
            log("=" * 50)
            log("Step 6: FBX 익스포트 테스트")
            log("=" * 50)

            try:
                ensure_object_mode()
                blend_path = bpy.data.filepath
                fbx_path = os.path.splitext(blend_path)[0] + "_arp_test.fbx" if blend_path else os.path.join(os.path.expanduser("~"), "_arp_test.fbx")

                select_only(arp_obj)
                for mesh_obj in mesh_objects:
                    mesh_obj.select_set(True)

                # Blender 기본 FBX 익스포터 사용 (ARP 익스포터는 shape_keys 버그)
                bpy.ops.export_scene.fbx(
                    filepath=fbx_path,
                    use_selection=True,
                    add_leaf_bones=False,
                    bake_anim=True,
                    bake_anim_use_all_actions=True,
                    bake_anim_force_startend_keying=True,
                    axis_forward='-Z',
                    axis_up='Y',
                    use_armature_deform_only=True,
                )
                log(f"FBX 익스포트 성공: {fbx_path}")
                result['fbx_path'] = fbx_path
                result['steps_completed'].append('fbx_exported')
            except Exception as e:
                result['errors'].append(f"FBX 익스포트 실패: {e}")
                log(f"FBX 익스포트 실패: {e}", "ERROR")

        # ─── 결과 요약 ───
        log("=" * 50)
        log("변환 결과 요약")
        log("=" * 50)

        result['success'] = len(result['errors']) == 0
        log(f"  완료 단계: {result['steps_completed']}")
        if result['errors']:
            log(f"  오류: {result['errors']}", "ERROR")
        if result['warnings']:
            log(f"  경고: {result['warnings']}", "WARN")

        # 결과 JSON 저장
        result_path = os.path.join(
            os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~"),
            "conversion_result.json"
        )
        serializable_result = json.loads(json.dumps(result, default=str))
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(serializable_result, f, ensure_ascii=False, indent=2)
        log(f"  결과 저장: {result_path}")

    except Exception as e:
        result['errors'].append(f"예상치 못한 오류: {e}")
        log(f"예상치 못한 오류: {e}", "ERROR")
        log(traceback.format_exc(), "ERROR")

    return result


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    log("=" * 60)
    log("Source Rig → AutoRig Pro 변환 시작")
    log(f"Blender: {bpy.app.version_string}")
    log(f"파일: {bpy.data.filepath or '(저장되지 않음)'}")
    log("=" * 60)

    result = convert_to_arp()

    if result['success']:
        log("✅ 변환 성공!", "SUCCESS")
    else:
        log("❌ 변환 실패 — 오류 확인 필요", "ERROR")
        for err in result['errors']:
            log(f"  → {err}", "ERROR")

    log("=" * 60)
    log("변환 완료")
    log("=" * 60)

"""
Source Rig → AutoRig Pro 변환 스크립트 (v5 — 프로필 기반)
=========================================================
Blender 4.5 LTS + AutoRig Pro 에서 실행

사용법:
  1. 변환할 리그가 있는 .blend 파일을 Blender에서 열기
  2. Scripting 탭에서 이 스크립트 열기
  3. 아래 CONFIG 섹션의 MAPPING_PROFILE 설정 확인
  4. ▶ Run Script 실행

또는 커맨드라인:
  blender myfile.blend --python rigify_to_arp.py
"""

import os
import json
import traceback
from datetime import datetime

try:
    import bpy
    from mathutils import Vector
    _IN_BLENDER = True
except ImportError:
    _IN_BLENDER = False


# ═══════════════════════════════════════════════════════════════
# CONFIG — 필요에 따라 수정
# ═══════════════════════════════════════════════════════════════

# 프로젝트 루트 (자동 감지)
if _IN_BLENDER:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else os.path.dirname(bpy.data.filepath) if bpy.data.filepath else ""
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 매핑 프로필 이름 (mapping_profiles/ 폴더 내 JSON 파일명, 확장자 제외)
# 리그 타입별로 프로필 교체: custom_quadruped, rigify_quadruped 등
MAPPING_PROFILE = "custom_quadruped"

# 변환 결과 저장 경로 (None이면 원본 옆에 _arp 접미사로 저장)
OUTPUT_PATH = None

# FBX 익스포트 테스트 여부 (ARP 익스포트 기능을 수동으로 사용할 경우 False)
TEST_FBX_EXPORT = False

# 로그 레벨
VERBOSE = True


# ═══════════════════════════════════════════════════════════════
# 프로필 로더
# ═══════════════════════════════════════════════════════════════

def load_mapping_profile(profile_name):
    """
    mapping_profiles/{profile_name}.json 로드.
    L사이드 매핑에서 R사이드 자동 생성 (미러링).

    Returns:
        dict: {
            'name', 'description',
            'arp_preset': ARP 아마추어 프리셋 이름,
            'bmap_preset': .bmap 리타게팅 프리셋 이름,
            'deform_to_ref': {소스본: ARP ref본} (L+R 포함),
            'ref_to_source': {ARP ref본: 소스본} (역매핑),
            'ref_alignment': {'priority': {...}, 'avg_lr': {...}},
        }
    """
    profile_dir = os.path.join(PROJECT_ROOT, "mapping_profiles")
    profile_path = os.path.join(profile_dir, f"{profile_name}.json")

    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"매핑 프로필 미발견: {profile_path}")

    with open(profile_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # L→R 미러링
    mirror = raw.get("mirror_suffix", {})
    src_suffixes = mirror.get("source", ["_L", "_R"])
    arp_suffixes = mirror.get("arp", [".l", ".r"])

    deform_to_ref = dict(raw["deform_to_ref"])

    # L사이드 매핑에서 R사이드 자동 생성
    for src_name, ref_name in list(raw["deform_to_ref"].items()):
        if isinstance(src_suffixes, list) and len(src_suffixes) == 2:
            l_suffix, r_suffix = src_suffixes
        else:
            continue
        if isinstance(arp_suffixes, list) and len(arp_suffixes) == 2:
            l_arp, r_arp = arp_suffixes
        else:
            continue

        if src_name.endswith(l_suffix) and ref_name.endswith(l_arp):
            r_src = src_name[:-len(l_suffix)] + r_suffix
            r_ref = ref_name[:-len(l_arp)] + r_arp
            if r_src not in deform_to_ref:
                deform_to_ref[r_src] = r_ref

    # 역매핑
    ref_to_source = {}
    for src, ref in deform_to_ref.items():
        # 중복 ref (priority 처리는 ref_alignment에서)
        if ref not in ref_to_source:
            ref_to_source[ref] = src

    log(f"프로필 로드: '{raw['name']}' — {raw.get('description', '')}")
    log(f"  매핑: {len(deform_to_ref)}개 (미러링 포함)")

    return {
        'name': raw['name'],
        'description': raw.get('description', ''),
        'arp_preset': raw.get('arp_preset', 'dog'),
        'bmap_preset': raw.get('bmap_preset', ''),
        'deform_to_ref': deform_to_ref,
        'ref_to_source': ref_to_source,
        'ref_alignment': raw.get('ref_alignment', {}),
    }


# ═══════════════════════════════════════════════════════════════
# 유틸리티 함수
# ═══════════════════════════════════════════════════════════════

def log(msg, level="INFO"):
    """로그 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def find_source_armature(profile):
    """
    씬에서 변환 대상 아마추어를 찾는다.
    ARP 아마추어(c_ 본)가 아닌 아마추어 중에서
    프로필 매핑 키와 일치하는 본이 가장 많은 것을 선택.
    """
    mapping_keys = set(profile['deform_to_ref'].keys())
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

        # 프로필 매핑 키와 일치하는 본 수
        matched = len([b for b in arm.bones if b.name in mapping_keys])
        if matched > best_match:
            best_match = matched
            best_obj = obj

    if best_obj:
        arm = best_obj.data
        total = len(arm.bones)
        log(f"소스 아마추어 발견: '{best_obj.name}' (본 {total}개, 프로필 매칭 {best_match}개)")
        unmapped = [b.name for b in arm.bones if b.name not in mapping_keys and b.use_deform]
        if unmapped:
            log(f"  프로필에 없는 deform 본: {unmapped}", "WARN")
    return best_obj


def find_arp_armature():
    """씬에서 ARP 아마추어를 찾는다."""
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
    """특정 아마추어에 바인딩된 메시 오브젝트들을 찾는다."""
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


def get_3d_viewport_context():
    """3D Viewport의 컨텍스트를 가져온다."""
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
    log("3D Viewport를 찾을 수 없습니다!", "ERROR")
    return None


def run_arp_operator(op_func, **kwargs):
    """ARP 오퍼레이터를 3D Viewport 컨텍스트에서 실행."""
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
# Step 3.5: ARP 레퍼런스 본 위치 정렬
# ═══════════════════════════════════════════════════════════════

def align_ref_bones_to_source(source_obj, arp_obj, profile, copy_roll=True):
    """
    ARP 레퍼런스 본을 소스 아마추어 본 위치에 맞게 이동.
    프로필의 매핑 + ref_alignment 기반.

    Args:
        source_obj: 소스 아마추어 오브젝트
        arp_obj: ARP 아마추어 오브젝트
        profile: load_mapping_profile() 결과
        copy_roll: True면 소스 본의 roll도 복사

    Returns:
        dict: {'aligned_count', 'skipped_count', 'averaged_bones', 'errors'}
    """
    ensure_object_mode()

    result = {
        'aligned_count': 0,
        'skipped_count': 0,
        'averaged_bones': [],
        'errors': [],
    }

    deform_to_ref = profile['deform_to_ref']
    ref_alignment = profile.get('ref_alignment', {})
    priority_map = ref_alignment.get('priority', {})
    avg_lr_map = ref_alignment.get('avg_lr', {})

    # ── Phase A: 소스 본 위치 추출 (월드 좌표) ──
    log("  Phase A: 소스 본 위치 추출 (월드 좌표)")
    source_positions = {}

    bpy.context.view_layer.objects.active = source_obj
    bpy.ops.object.mode_set(mode='EDIT')

    src_matrix = source_obj.matrix_world
    for ebone in source_obj.data.edit_bones:
        world_head = src_matrix @ ebone.head.copy()
        world_tail = src_matrix @ ebone.tail.copy()
        source_positions[ebone.name] = (world_head, world_tail, ebone.roll)

    bpy.ops.object.mode_set(mode='OBJECT')
    log(f"    추출된 소스 본: {len(source_positions)}개")

    # ── Phase B: ARP ref 본 목표 위치 결정 ──
    log("  Phase B: ARP ref 본 목표 위치 결정 (프로필 기반)")
    resolved = {}  # arp_ref_name → (world_head, world_tail, roll)

    # 처리 완료된 ref 본 추적 (중복 방지)
    processed_refs = set()

    # B-1: priority 매핑 (여러 소스 중 첫 발견 사용)
    for ref_name, src_candidates in priority_map.items():
        for src_name in src_candidates:
            if src_name in source_positions:
                resolved[ref_name] = source_positions[src_name]
                processed_refs.add(ref_name)
                break
        if ref_name not in processed_refs:
            msg = f"우선순위 소스 본 {src_candidates} 모두 미발견 → {ref_name} 스킵"
            log(f"    {msg}", "WARN")
            result['errors'].append(msg)

    # B-2: avg_lr 매핑 (L/R 평균 → 중앙 본)
    for ref_name, lr_pair in avg_lr_map.items():
        src_l, src_r = lr_pair[0], lr_pair[1]
        has_l = src_l in source_positions
        has_r = src_r in source_positions

        if has_l and has_r:
            l_head, l_tail, l_roll = source_positions[src_l]
            r_head, r_tail, r_roll = source_positions[src_r]
            avg_head = (l_head + r_head) / 2.0
            avg_tail = (l_tail + r_tail) / 2.0
            avg_head.x = 0.0
            avg_tail.x = 0.0
            avg_roll = (l_roll + r_roll) / 2.0
            resolved[ref_name] = (avg_head, avg_tail, avg_roll)
            result['averaged_bones'].append(ref_name)
        elif has_l:
            h, t, r = source_positions[src_l]
            h = h.copy(); t = t.copy()
            h.x = 0.0; t.x = 0.0
            resolved[ref_name] = (h, t, r)
            log(f"    '{src_r}' 미발견, '{src_l}'만 사용 → {ref_name}", "WARN")
        elif has_r:
            h, t, r = source_positions[src_r]
            h = h.copy(); t = t.copy()
            h.x = 0.0; t.x = 0.0
            resolved[ref_name] = (h, t, r)
            log(f"    '{src_l}' 미발견, '{src_r}'만 사용 → {ref_name}", "WARN")
        else:
            msg = f"'{src_l}' + '{src_r}' 모두 미발견 → {ref_name} 스킵"
            log(f"    {msg}", "WARN")
            result['errors'].append(msg)
        processed_refs.add(ref_name)

    # B-3: 일반 1:1 매핑
    for src_name, ref_name in deform_to_ref.items():
        if ref_name in processed_refs:
            continue  # priority/avg_lr에서 이미 처리됨
        if src_name in source_positions:
            resolved[ref_name] = source_positions[src_name]
        else:
            if VERBOSE:
                log(f"    소스 본 '{src_name}' 미발견 → {ref_name} 스킵")

    log(f"    결정된 ref 본: {len(resolved)}개")

    # ── Phase C: ARP ref 본에 위치 적용 ──
    log("  Phase C: ARP ref 본에 위치 적용")

    bpy.context.view_layer.objects.active = arp_obj
    bpy.ops.object.mode_set(mode='EDIT')

    arp_matrix_inv = arp_obj.matrix_world.inverted()
    aligned = 0

    for ref_name, (world_head, world_tail, roll) in resolved.items():
        ebone = arp_obj.data.edit_bones.get(ref_name)
        if ebone is None:
            msg = f"ARP ref 본 '{ref_name}' 미발견 (프리셋에 없음)"
            log(f"    {msg}", "WARN")
            result['errors'].append(msg)
            continue

        local_head = arp_matrix_inv @ world_head
        local_tail = arp_matrix_inv @ world_tail

        # 본 길이 0 방지
        if (local_tail - local_head).length < 0.0001:
            local_tail = local_head + Vector((0, 0.01, 0))
            log(f"    '{ref_name}': 본 길이 0 방지 보정", "WARN")

        ebone.head = local_head
        ebone.tail = local_tail
        if copy_roll:
            ebone.roll = roll

        aligned += 1
        if VERBOSE:
            log(f"    정렬: {ref_name}")

    bpy.ops.object.mode_set(mode='OBJECT')

    result['aligned_count'] = aligned
    result['skipped_count'] = len(deform_to_ref) - aligned
    return result


# ═══════════════════════════════════════════════════════════════
# 메인 변환 파이프라인
# ═══════════════════════════════════════════════════════════════

def convert_to_arp():
    """
    소스 리그 → ARP 변환 메인 함수.

    파이프라인 (v5 — 프로필 기반):
    1. 프로필 로드 + 소스 아마추어 식별
    2. 변환 전 상태 기록
    3. ARP 리그 추가 (프로필의 arp_preset)
    3.5. ARP 레퍼런스 본 위치 정렬 (프로필 매핑 기반)
    4. ARP 리그 생성 (match_to_rig)
    4.5. IK→FK 전환 시도
    5. Remap 애니메이션 리타게팅 (프로필의 bmap_preset)
    6. FBX 익스포트 테스트
    """

    result = {
        'success': False,
        'steps_completed': [],
        'errors': [],
        'warnings': [],
    }

    try:
        ensure_object_mode()

        # ─── Step 1: 프로필 로드 + 소스 아마추어 식별 ───
        log("=" * 50)
        log(f"Step 1: 프로필 '{MAPPING_PROFILE}' 로드 + 소스 아마추어 식별")
        log("=" * 50)

        try:
            profile = load_mapping_profile(MAPPING_PROFILE)
        except FileNotFoundError as e:
            result['errors'].append(str(e))
            log(str(e), "ERROR")
            return result

        source_obj = find_source_armature(profile)
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

        mapping_keys = set(profile['deform_to_ref'].keys())
        matched_count = len([b for b in source_obj.data.bones if b.name in mapping_keys])
        pre_state = {
            'source_name': source_obj.name,
            'profile': profile['name'],
            'matched_bone_count': matched_count,
            'total_bone_count': len(source_obj.data.bones),
            'mesh_count': len(mesh_objects),
            'action_count': len(pre_actions),
        }
        result['pre_state'] = pre_state
        log(f"  프로필 매칭 본: {matched_count}개")
        log(f"  전체 본: {pre_state['total_bone_count']}개")
        log(f"  메시: {pre_state['mesh_count']}개")
        log(f"  액션: {pre_state['action_count']}개")
        result['steps_completed'].append('state_recorded')

        # ─── Step 3: ARP 리그 추가 (기본 위치) ───
        log("=" * 50)
        log("Step 3: ARP 리그 추가 (기본 위치)")
        log("=" * 50)

        arp_preset = profile['arp_preset']
        ensure_object_mode()
        select_only(source_obj)

        try:
            run_arp_operator(bpy.ops.arp.append_arp, rig_preset=arp_preset)
            log(f"ARP 리그 추가 완료 (프리셋: {arp_preset})")
            result['steps_completed'].append('arp_appended')
        except Exception as e:
            result['errors'].append(f"ARP 리그 추가 실패: {e}")
            log(f"ARP 리그 추가 실패: {e}", "ERROR")
            return result

        arp_obj = find_arp_armature()
        if arp_obj is None:
            result['errors'].append("ARP 아마추어를 찾을 수 없습니다.")
            return result

        # ─── Step 3.5: ARP 레퍼런스 본 위치 정렬 ───
        log("=" * 50)
        log("Step 3.5: ARP 레퍼런스 본을 소스 메시에 맞게 정렬")
        log("=" * 50)

        try:
            align_result = align_ref_bones_to_source(source_obj, arp_obj, profile)
            log(f"  정렬 완료: {align_result['aligned_count']}개 본 정렬")
            if align_result['skipped_count'] > 0:
                log(f"  스킵: {align_result['skipped_count']}개")
            if align_result['averaged_bones']:
                log(f"  L/R 평균 처리: {align_result['averaged_bones']}")
            if align_result['errors']:
                for err in align_result['errors']:
                    log(f"  {err}", "WARN")
                result['warnings'].extend(align_result['errors'])
            result['steps_completed'].append('ref_bones_aligned')
        except Exception as e:
            result['errors'].append(f"레퍼런스 본 정렬 실패: {e}")
            log(f"레퍼런스 본 정렬 실패: {e}", "ERROR")
            log(traceback.format_exc(), "ERROR")
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

        # ─── Step 4.5: ARP 앞다리 IK→FK 전환 ───
        log("=" * 50)
        log("Step 4.5: ARP 앞다리 IK→FK 전환")
        log("=" * 50)

        try:
            ensure_object_mode()
            select_only(arp_obj)
            bpy.ops.object.mode_set(mode='POSE')

            ik_fk_switched = 0
            for pbone in arp_obj.pose.bones:
                for prop_name in pbone.keys():
                    if prop_name.startswith('_') or prop_name == 'rna_type':
                        continue
                    prop_lower = prop_name.lower()
                    if 'ik' in prop_lower and 'fk' in prop_lower:
                        old_val = pbone[prop_name]
                        try:
                            pbone[prop_name] = 1.0
                            ik_fk_switched += 1
                            log(f"  {pbone.name}['{prop_name}']: {old_val} → 1.0 (FK)")
                        except:
                            log(f"  {pbone.name}['{prop_name}']: 변경 실패", "WARN")

            bpy.ops.object.mode_set(mode='OBJECT')

            if ik_fk_switched > 0:
                log(f"  IK→FK 전환 완료: {ik_fk_switched}개 스위치")
            else:
                log("  IK/FK 프로퍼티 못 찾음", "WARN")
                result['warnings'].append("IK/FK 스위치를 자동 전환하지 못함")

        except Exception as e:
            log(f"  IK→FK 전환 실패 (계속 진행): {e}", "WARN")
            ensure_object_mode()

        # ─── Step 5: Remap 애니메이션 리타게팅 ───
        log("=" * 50)
        log("Step 5: Remap 애니메이션 리타게팅")
        log("=" * 50)

        bmap_preset = profile.get('bmap_preset', '')

        if len(pre_actions) > 0:
            try:
                ensure_object_mode()

                bpy.context.scene.source_rig = source_obj.name
                bpy.context.scene.target_rig = arp_obj.name
                log(f"  소스: {source_obj.name}")
                log(f"  타겟: {arp_obj.name}")

                run_arp_operator(bpy.ops.arp.auto_scale)
                log("  auto_scale 완료")

                run_arp_operator(bpy.ops.arp.build_bones_list)
                log("  build_bones_list 완료")

                # .bmap 프리셋 로드
                if bmap_preset:
                    try:
                        run_arp_operator(bpy.ops.arp.import_config_preset, preset_name=bmap_preset)
                        log(f"  .bmap 프리셋 로드 성공: {bmap_preset}")
                    except Exception as e:
                        log(f"  .bmap 프리셋 로드 실패: {e}", "WARN")
                        result['warnings'].append(f".bmap 프리셋 미사용")

                run_arp_operator(bpy.ops.arp.redefine_rest_pose, preserve=True)
                run_arp_operator(bpy.ops.arp.save_pose_rest)
                ensure_object_mode()
                log("  레스트 포즈 조정 완료")

                # 액션별 리타게팅
                retarget_success = 0
                retarget_fail = 0

                for i, action_info in enumerate(pre_actions):
                    action_name = action_info['name']
                    frame_start = action_info['frame_start']
                    frame_end = action_info['frame_end']

                    log(f"  [{i+1}/{len(pre_actions)}] 리타게팅: '{action_name}' ({frame_start}~{frame_end})")

                    try:
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
                        log(f"    OK")

                    except Exception as e:
                        retarget_fail += 1
                        log(f"    실패: {e}", "WARN")

                log(f"  리타게팅 완료: {retarget_success}/{len(pre_actions)} 성공")
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
# 검증: 프로필 로드 테스트 (Blender 없이 실행 가능)
# ═══════════════════════════════════════════════════════════════

def _test_profile_load():
    """프로필 로드 및 미러링 검증"""
    profile = load_mapping_profile("custom_quadruped")

    d2r = profile['deform_to_ref']

    # L 매핑 확인
    assert d2r.get("shoulder_L") == "shoulder_ref.l", f"shoulder_L 매핑 실패: {d2r.get('shoulder_L')}"
    assert d2r.get("thigh_L") == "thigh_ref.l", f"thigh_L 매핑 실패: {d2r.get('thigh_L')}"
    assert d2r.get("arm_L") == "forearm_ref.l", f"arm_L 매핑 실패: {d2r.get('arm_L')}"

    # R 미러 자동 생성 확인
    assert d2r.get("shoulder_R") == "shoulder_ref.r", f"shoulder_R 미러 실패: {d2r.get('shoulder_R')}"
    assert d2r.get("thigh_R") == "thigh_ref.r", f"thigh_R 미러 실패: {d2r.get('thigh_R')}"
    assert d2r.get("arm_R") == "forearm_ref.r", f"arm_R 미러 실패: {d2r.get('arm_R')}"
    assert d2r.get("upperarm_R") == "arm_ref.r", f"upperarm_R 미러 실패: {d2r.get('upperarm_R')}"
    assert d2r.get("ear01_R") == "ear_01_ref.r", f"ear01_R 미러 실패: {d2r.get('ear01_R')}"
    assert d2r.get("eye_R") == "eye_ref.r", f"eye_R 미러 실패: {d2r.get('eye_R')}"

    # 중앙 본 (미러 대상 아님)
    assert d2r.get("pelvis") == "spine_01_ref.x", f"pelvis 매핑 실패: {d2r.get('pelvis')}"
    assert d2r.get("jaw") == "jawbone_ref.x", f"jaw 매핑 실패: {d2r.get('jaw')}"

    # ref_alignment 확인
    ra = profile['ref_alignment']
    assert "root_ref.x" in ra.get("priority", {}), "priority 매핑 누락"
    assert "ear_01_ref.x" in ra.get("avg_lr", {}), "avg_lr 매핑 누락"

    # 총 매핑 수 (L 23 + R 미러 ~12 = ~35)
    print(f"프로필 매핑 수: {len(d2r)}개 (L+R 미러 포함)")
    print(f"프로필 로드 테스트: 전체 통과")
    return True


# ═══════════════════════════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if not _IN_BLENDER:
        print("Blender 외부 실행 — 프로필 로드 테스트")
        _test_profile_load()
    else:
        log("=" * 60)
        log(f"Source Rig → AutoRig Pro 변환 시작 (v5 — 프로필: {MAPPING_PROFILE})")
        log(f"Blender: {bpy.app.version_string}")
        log(f"파일: {bpy.data.filepath or '(저장되지 않음)'}")
        log("=" * 60)

        result = convert_to_arp()

        if result['success']:
            log("변환 성공!", "SUCCESS")
        else:
            log("변환 실패 — 오류 확인 필요", "ERROR")
            for err in result['errors']:
                log(f"  → {err}", "ERROR")

        log("=" * 60)
        log("변환 완료")
        log("=" * 60)

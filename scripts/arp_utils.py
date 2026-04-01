"""
ARP 변환 공유 유틸리티
=====================
01_create_arp_rig.py, 02_retarget_animation.py 에서 공통 사용
"""

import json
import os
import shutil
from datetime import datetime

import bpy


def log(msg, level="INFO"):
    """로그 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def ensure_object_mode():
    """Object 모드로 전환"""
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def select_only(obj):
    """오브젝트 하나만 선택 & 활성화"""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def get_3d_viewport_context():
    """3D Viewport 컨텍스트 반환. ARP 오퍼레이터 실행에 필요."""
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                for region in area.regions:
                    if region.type == "WINDOW":
                        return {
                            "window": window,
                            "screen": window.screen,
                            "area": area,
                            "region": region,
                            "scene": bpy.context.scene,
                            "view_layer": bpy.context.view_layer,
                        }
    log("3D Viewport를 찾을 수 없습니다!", "ERROR")
    return None


def run_arp_operator(op_func, **kwargs):
    """ARP 오퍼레이터를 3D Viewport 컨텍스트에서 실행."""
    ctx = get_3d_viewport_context()
    if ctx is None:
        raise RuntimeError("3D Viewport 컨텍스트를 찾을 수 없습니다.")
    try:
        with bpy.context.temp_override(**ctx):
            return op_func(**kwargs)
    except RuntimeError:
        active = bpy.context.view_layer.objects.active
        mode = bpy.context.mode
        op_name = getattr(op_func, "idname_py", lambda: str(op_func))()
        log(
            f"오퍼레이터 실패: {op_name} (active={active.name if active else None}, mode={mode})",
            "ERROR",
        )
        raise


def ensure_retarget_context(source_obj, arp_obj):
    """리타게팅 전 컨텍스트 설정 (auto_scale 호출 전에 사용)"""
    ensure_object_mode()
    bpy.context.scene.source_rig = source_obj.name
    bpy.context.scene.target_rig = arp_obj.name
    # auto_scale poll은 소스+타겟 양쪽 선택 + 소스 활성 필요
    bpy.ops.object.select_all(action="DESELECT")
    source_obj.select_set(True)
    arp_obj.select_set(True)
    bpy.context.view_layer.objects.active = source_obj
    log(f"리타게팅 컨텍스트: 소스={source_obj.name}, 타겟={arp_obj.name}")


def install_bmap_preset(preset_name, project_root=None):
    """
    프로젝트의 .bmap 파일을 ARP remap_presets 경로로 복사.
    이미 존재하면 스킵.

    Returns:
        bool: 설치 성공 여부
    """
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    src_path = os.path.join(project_root, "remap_presets", f"{preset_name}.bmap")
    if not os.path.exists(src_path):
        log(f".bmap 파일 미발견: {src_path}", "WARN")
        return False

    # ARP remap_presets 경로 탐색
    arp_presets_dir = None
    blender_ver = f"{bpy.app.version[0]}.{bpy.app.version[1]}"

    # extensions 경로 (Blender 4.x)
    candidates = [
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Blender Foundation",
            "Blender",
            blender_ver,
            "extensions",
            "user_default",
            "auto_rig_pro",
            "remap_presets",
        ),
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Blender Foundation",
            "Blender",
            blender_ver,
            "config",
            "addons",
            "auto_rig_pro-master",
            "remap_presets",
        ),
    ]

    for c in candidates:
        if os.path.isdir(c):
            arp_presets_dir = c
            break

    if arp_presets_dir is None:
        log("ARP remap_presets 경로를 찾을 수 없습니다.", "WARN")
        return False

    dst_path = os.path.join(arp_presets_dir, f"{preset_name}.bmap")
    if os.path.exists(dst_path):
        log(f".bmap 이미 설치됨: {dst_path}")
        return True

    shutil.copy2(src_path, dst_path)
    log(f".bmap 설치 완료: {dst_path}")
    return True


def find_arp_armature():
    """씬에서 ARP 아마추어를 찾는다. (c_ 접두사 본 5개 이상)"""
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        arp_bones = [b for b in obj.data.bones if b.name.startswith("c_")]
        if len(arp_bones) > 5:
            log(f"ARP 아마추어 발견: '{obj.name}' (c_ 본 {len(arp_bones)}개)")
            return obj
    return None


def find_source_armature():
    """
    씬에서 소스(비-ARP) 아마추어를 찾는다.
    c_ 본이 5개 이하인 아마추어 중 본 수가 가장 많은 것.
    """
    best_obj = None
    best_count = 0

    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        c_bones = len([b for b in obj.data.bones if b.name.startswith("c_")])
        if c_bones > 5:
            continue
        total = len(obj.data.bones)
        if total > best_count:
            best_count = total
            best_obj = obj

    if best_obj:
        log(f"소스 아마추어 발견: '{best_obj.name}' (본 {best_count}개)")
    return best_obj


def find_mesh_objects(armature_obj):
    """특정 아마추어에 바인딩된 메시 오브젝트들을 찾는다."""
    meshes = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and mod.object == armature_obj:
                meshes.append(obj)
                break
    log(f"'{armature_obj.name}'에 바인딩된 메시: {len(meshes)}개")
    return meshes


def export_clean_fbx(source_obj, fbx_path=None):
    """
    소스 아마추어를 FBX(Deform Only + Anim)로 익스포트.

    Args:
        source_obj: 소스 아마추어 오브젝트
        fbx_path: 저장 경로. None이면 임시 파일 생성.

    Returns:
        str: FBX 파일 경로
    """
    import tempfile

    if fbx_path is None:
        fd, fbx_path = tempfile.mkstemp(suffix=".fbx", prefix="arp_clean_")
        os.close(fd)

    ensure_object_mode()
    select_only(source_obj)

    # NOTE: constraint/driver 뮤트 금지 — bake_anim이 뮤트 상태로 베이크하면
    # 애니메이션 자체가 틀어짐. rest pose 교정은 임포트 후 normalize에서 처리.
    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_force_startend_keying=True,
        axis_forward="-Z",
        axis_up="Y",
        use_armature_deform_only=True,
    )

    log(f"FBX 익스포트 완료: {fbx_path}")
    return fbx_path


def import_clean_fbx(fbx_path):
    """
    FBX를 임포트하여 clean armature를 반환.

    Args:
        fbx_path: FBX 파일 경로

    Returns:
        bpy.types.Object: 임포트된 아마추어 오브젝트 (없으면 None)
    """
    existing_armatures = {obj.name for obj in bpy.data.objects if obj.type == "ARMATURE"}

    ensure_object_mode()
    bpy.ops.import_scene.fbx(filepath=fbx_path)

    # 새로 생긴 아마추어 찾기
    new_armature = None
    for obj in bpy.data.objects:
        if obj.type == "ARMATURE" and obj.name not in existing_armatures:
            new_armature = obj
            break

    if new_armature:
        log(f"FBX 임포트 완료: clean armature '{new_armature.name}'")
    else:
        log("FBX 임포트 후 새 아마추어를 찾을 수 없습니다.", "WARN")

    return new_armature


def normalize_clean_hierarchy(clean_obj, bone_data):
    """
    Clean armature를 플랫 하이어라키로 변환 + rest pose를 원본 기준으로 교정.

    FBX 임포트 시 rest pose가 frame 1 포즈로 오염될 수 있다.
    bone_data의 원본 head/tail/roll을 사용하여 rest pose를 교정하고,
    모든 부모를 제거(플랫)한 뒤, 전체 본의 애니메이션을 리베이크한다.

    Args:
        clean_obj: FBX 임포트된 clean armature
        bone_data: analyze_skeleton() 결과의 bone_data (head/tail/roll 포함)

    Returns:
        int: 변경된 본 수. 0이면 변경 없음.
    """
    from mathutils import Vector

    if not bone_data or not clean_obj or clean_obj.type != "ARMATURE":
        return 0

    clean_bones = clean_obj.data.bones

    # Step A: 유지/삭제 본 식별
    keep_bones = []  # bone_data에 있는 본
    delete_bones = []

    for bone in clean_bones:
        if bone.name in bone_data:
            keep_bones.append(bone.name)
        else:
            delete_bones.append(bone.name)

    if not keep_bones:
        return 0

    log(f"하이어라키 정규화: 유지 {len(keep_bones)}개, 삭제 {len(delete_bones)}개")

    # Step B: 모든 유지 본의 씬 월드 행렬 기록
    # pb.matrix는 armature-space이므로, matrix_world를 곱해 씬 월드로 변환.
    # rest pose 교정(Step C) 전후 armature-space 정의가 달라지므로
    # 씬 월드 좌표를 기준점으로 사용해야 교정된 rest와 정합성 보장.
    scene = bpy.context.scene
    ensure_object_mode()
    select_only(clean_obj)

    actions = _collect_actions(clean_obj)
    obj_world = clean_obj.matrix_world

    world_matrices = {}  # {action.name: {bone_name: {frame: Matrix}}}

    if not clean_obj.animation_data:
        clean_obj.animation_data_create()

    # NLA 트랙 뮤트: action 단독 평가를 위해 (try/finally로 복원 보장)
    anim_data = clean_obj.animation_data
    nla_mute_states = []
    for track in anim_data.nla_tracks:
        nla_mute_states.append((track, track.mute))
        track.mute = True

    try:
        for action in actions:
            _assign_action_with_slot(anim_data, action, clean_obj)
            f_start = int(action.frame_range[0])
            f_end = int(action.frame_range[1])

            action_mats = {}
            for frame in range(f_start, f_end + 1):
                scene.frame_set(frame)
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = clean_obj.evaluated_get(depsgraph)
                for bone_name in keep_bones:
                    pb = eval_obj.pose.bones.get(bone_name)
                    if pb:
                        # 씬 월드 행렬 = object_world * bone_armature_space
                        action_mats.setdefault(bone_name, {})[frame] = (
                            obj_world @ pb.matrix
                        ).copy()
            world_matrices[action.name] = action_mats
    finally:
        # NLA 뮤트 복원 (예외 발생해도 반드시 실행)
        for track, was_muted in nla_mute_states:
            track.mute = was_muted

    # Step C: Edit Mode — 플랫 + rest pose 교정 + 삭제
    ensure_object_mode()
    select_only(clean_obj)
    bpy.context.view_layer.objects.active = clean_obj
    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = clean_obj.data.edit_bones
    clean_world_inv = clean_obj.matrix_world.inverted()

    # 플랫: 모든 부모 제거
    for eb in edit_bones:
        if eb.parent is not None:
            eb.parent = None
            eb.use_connect = False

    # rest pose 교정: bone_data의 head/tail/roll로 덮어쓰기
    # bone_data의 좌표는 원본 armature의 world space → clean의 local space로 변환
    rest_corrected = 0
    for bone_name in keep_bones:
        eb = edit_bones.get(bone_name)
        bd = bone_data.get(bone_name)
        if not eb or not bd:
            continue
        orig_head = clean_world_inv @ Vector(bd["head"])
        orig_tail = clean_world_inv @ Vector(bd["tail"])
        eb.head = orig_head
        eb.tail = orig_tail
        eb.roll = bd["roll"]
        rest_corrected += 1

    # 삭제
    for del_name in delete_bones:
        eb = edit_bones.get(del_name)
        if eb:
            edit_bones.remove(eb)

    bpy.ops.object.mode_set(mode="OBJECT")
    log(f"Rest pose 교정: {rest_corrected}개 본")

    # Step D: 전체 본 애니메이션 리베이크
    # world_matrices는 씬 월드 좌표 → armature-space로 변환 후 교정된 rest 기준 분해
    # 변환 체인: 씬 월드 → armature-space → bone-local
    obj_world_inv = clean_obj.matrix_world.inverted()

    if keep_bones and actions:
        for action in actions:
            mats = world_matrices.get(action.name, {})
            if not mats:
                continue
            _assign_action_with_slot(clean_obj.animation_data, action, clean_obj)

            # 모든 유지 본의 기존 FCurve 삭제
            remove_fcs = []
            bone_set = set(keep_bones)
            for fc in action.fcurves:
                for bone_name in bone_set:
                    if f'pose.bones["{bone_name}"]' in fc.data_path:
                        remove_fcs.append(fc)
                        break
            for fc in remove_fcs:
                action.fcurves.remove(fc)

            # 새 키프레임 삽입 — 플랫 + 교정된 rest 기준
            new_fcs = set()
            for bone_name, frame_mats in mats.items():
                pb = clean_obj.pose.bones.get(bone_name)
                if not pb:
                    continue

                # 교정된 rest bone의 역행렬 (armature-space → bone-local)
                rest_inv = pb.bone.matrix_local.inverted()

                dp_loc = f'pose.bones["{bone_name}"].location'
                dp_rot = f'pose.bones["{bone_name}"].rotation_quaternion'
                dp_scl = f'pose.bones["{bone_name}"].scale'

                for frame, scene_world_mat in sorted(frame_mats.items()):
                    # 씬 월드 → armature-space → bone-local
                    armature_mat = obj_world_inv @ scene_world_mat
                    local_mat = rest_inv @ armature_mat
                    loc = local_mat.to_translation()
                    rot = local_mat.to_quaternion()
                    scl = local_mat.to_scale()

                    for i in range(3):
                        new_fcs.add(_norm_fc_insert(action, dp_loc, i, frame, loc[i], bone_name))
                        new_fcs.add(_norm_fc_insert(action, dp_scl, i, frame, scl[i], bone_name))
                    for i in range(4):
                        new_fcs.add(_norm_fc_insert(action, dp_rot, i, frame, rot[i], bone_name))

            for fc in new_fcs:
                fc.update()

    # 삭제 본의 FCurve 정리
    if delete_bones:
        for action in actions:
            remove_fcs = []
            for fc in action.fcurves:
                for del_name in delete_bones:
                    if f'pose.bones["{del_name}"]' in fc.data_path:
                        remove_fcs.append(fc)
                        break
            for fc in remove_fcs:
                action.fcurves.remove(fc)

    ensure_object_mode()
    total_changes = len(keep_bones) + len(delete_bones)
    log(f"하이어라키 정규화 완료: {total_changes}개 본 처리 (플랫 + rest pose 교정)")
    return total_changes


def _collect_actions(armature_obj):
    """아마추어의 모든 관련 액션을 수집."""
    actions = []
    if armature_obj.animation_data:
        if armature_obj.animation_data.action:
            actions.append(armature_obj.animation_data.action)
        for track in armature_obj.animation_data.nla_tracks:
            for strip in track.strips:
                if strip.action and strip.action not in actions:
                    actions.append(strip.action)
    if not actions:
        for action in bpy.data.actions:
            if any(fc.data_path.startswith('pose.bones["') for fc in action.fcurves):
                actions.append(action)
    return actions


def _assign_action_with_slot(anim_data, action, armature_obj):
    """
    액션을 animation_data에 할당하고, Blender 4.5+ 슬롯도 설정.

    FBX 임포트 시 첫 번째 액션만 슬롯이 연결되고 나머지는 비어있을 수 있다.
    슬롯이 없으면 액션이 평가되지 않으므로 자동으로 할당/생성한다.
    """
    anim_data.action = action

    # Blender 4.5+ action slot 시스템 대응
    if not hasattr(anim_data, "action_slot"):
        return  # 슬롯 시스템 미지원 버전

    if anim_data.action_slot is not None:
        return  # 이미 슬롯 할당됨

    # 기존 슬롯에서 매칭 시도
    if hasattr(action, "slots"):
        for slot in action.slots:
            try:
                anim_data.action_slot = slot
                if anim_data.action_slot is not None:
                    return
            except Exception:
                continue

        # 슬롯 생성
        try:
            slot = action.slots.new(for_id=armature_obj)
            anim_data.action_slot = slot
            log(f"액션 '{action.name}' 슬롯 생성")
        except Exception as e:
            log(f"액션 '{action.name}' 슬롯 생성 실패: {e}", "WARN")


def _norm_fc_insert(action, data_path, index, frame, value, group=""):
    """정규화용 FCurve 키프레임 삽입."""
    fc = action.fcurves.find(data_path, index=index)
    if fc is None:
        fc = action.fcurves.new(data_path, index=index, action_group=group)
    fc.keyframe_points.insert(frame, value)
    return fc


def create_clean_source(source_obj):
    """
    소스 아마추어를 FBX로 익스포트 → 재임포트하여 clean armature를 생성.

    Args:
        source_obj: 소스 아마추어 오브젝트

    Returns:
        tuple: (clean_obj, fbx_path) — clean armature 오브젝트와 임시 FBX 경로
    """
    fbx_path = export_clean_fbx(source_obj)
    clean_obj = import_clean_fbx(fbx_path)
    if clean_obj is None:
        raise RuntimeError("Clean armature 생성 실패: FBX 임포트 결과 없음")
    return clean_obj, fbx_path


def cleanup_clean_source(clean_obj, fbx_path):
    """
    clean armature 오브젝트와 임시 FBX 파일을 정리.

    Args:
        clean_obj: 정리할 아마추어 오브젝트 (None이면 스킵)
        fbx_path: 삭제할 임시 FBX 파일 경로 (None이면 스킵)
    """
    if clean_obj:
        name = clean_obj.name
        # 임포트 시 딸려온 메시도 함께 제거
        children = [c for c in bpy.data.objects if c.parent == clean_obj]
        for child in children:
            bpy.data.objects.remove(child, do_unlink=True)
        bpy.data.objects.remove(clean_obj, do_unlink=True)
        log(f"Clean armature 정리 완료: '{name}'")

    if fbx_path and os.path.exists(fbx_path):
        os.remove(fbx_path)
        log(f"임시 FBX 삭제: {fbx_path}")


def load_mapping_profile(profile_name, project_root=None):
    """
    mapping_profiles/{profile_name}.json 로드.
    L사이드 매핑에서 R사이드 자동 미러링.

    Returns:
        dict: 프로필 데이터 (deform_to_ref, ref_alignment 등)
    """
    if project_root is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    profile_path = os.path.join(project_root, "mapping_profiles", f"{profile_name}.json")

    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"매핑 프로필 미발견: {profile_path}")

    with open(profile_path, encoding="utf-8") as f:
        raw = json.load(f)

    # L→R 미러링
    mirror = raw.get("mirror_suffix", {})
    src_suffixes = mirror.get("source", ["_L", "_R"])
    arp_suffixes = mirror.get("arp", [".l", ".r"])

    deform_to_ref = dict(raw["deform_to_ref"])

    if (
        isinstance(src_suffixes, list)
        and len(src_suffixes) == 2
        and isinstance(arp_suffixes, list)
        and len(arp_suffixes) == 2
    ):
        l_suffix, r_suffix = src_suffixes
        l_arp, r_arp = arp_suffixes
        for src_name, ref_name in list(raw["deform_to_ref"].items()):
            if src_name.endswith(l_suffix) and ref_name.endswith(l_arp):
                r_src = src_name[: -len(l_suffix)] + r_suffix
                r_ref = ref_name[: -len(l_arp)] + r_arp
                if r_src not in deform_to_ref:
                    deform_to_ref[r_src] = r_ref

    log(f"프로필 로드: '{raw['name']}' — 매핑 {len(deform_to_ref)}개 (미러 포함)")

    return {
        "name": raw["name"],
        "description": raw.get("description", ""),
        "arp_preset": raw.get("arp_preset", "dog"),
        "bmap_preset": raw.get("bmap_preset", ""),
        "deform_to_ref": deform_to_ref,
        "ref_alignment": raw.get("ref_alignment", {}),
    }

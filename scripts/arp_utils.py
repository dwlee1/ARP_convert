"""
ARP 변환 공유 유틸리티
=====================
ARP 리그 생성 공통 유틸리티.
"""

import json
import os
from datetime import datetime

import bpy

_PROJECT_RESOURCE_DIRS = (
    "mapping_profiles",
    "regression_fixtures",
)


def log(msg, level="INFO"):
    """로그 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def resolve_project_root(start_dir=None):
    """repo/scripts 레이아웃과 설치된 애드온 패키지 레이아웃을 모두 지원한다."""
    current = os.path.abspath(start_dir or os.path.dirname(os.path.abspath(__file__)))

    for _ in range(6):
        if any(os.path.isdir(os.path.join(current, name)) for name in _PROJECT_RESOURCE_DIRS):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    fallback = os.path.abspath(start_dir or os.path.dirname(os.path.abspath(__file__)))
    if os.path.basename(fallback) == "scripts":
        return os.path.dirname(fallback)
    return fallback


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


def load_mapping_profile(profile_name, project_root=None):
    """
    mapping_profiles/{profile_name}.json 로드.
    L사이드 매핑에서 R사이드 자동 미러링.

    Returns:
        dict: 프로필 데이터 (deform_to_ref, ref_alignment 등)
    """
    if project_root is None:
        project_root = resolve_project_root()

    profile_path = os.path.join(project_root, "mapping_profiles", f"{profile_name}.json")

    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"매핑 프로필 미발견: {profile_path}")

    with open(profile_path, encoding="utf-8") as f:
        raw = json.load(f)

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


# ═══════════════════════════════════════════════════════════════
# F12: 애니메이션 베이크 유틸리티
# ═══════════════════════════════════════════════════════════════

BAKE_PAIRS_KEY = "arpconv_bone_pairs"
BAKE_CONSTRAINT_NAME = "ARPCONV_CopyTF"


def serialize_bone_pairs(pairs):
    """bone_pairs 리스트를 JSON 문자열로 직렬화.

    Args:
        pairs: [(source_bone, arp_controller, is_custom), ...]

    Returns:
        str: JSON 문자열
    """
    return json.dumps([list(t) for t in pairs], ensure_ascii=False)


def deserialize_bone_pairs(json_str):
    """JSON 문자열에서 bone_pairs 리스트 복원.

    Returns:
        list[tuple]: [(source_bone, arp_controller, is_custom), ...]
    """
    raw = json.loads(json_str)
    return [(r[0], r[1], r[2]) for r in raw]


def preflight_check_transforms(source_obj, arp_obj):
    """베이크 전 오브젝트 transform 검증. 실패 시 에러 메시지 반환.

    Returns:
        str or None: 에러 메시지 (None이면 통과)
    """
    from mathutils import Vector

    tolerance = 1e-4
    for obj, label in [(source_obj, "소스"), (arp_obj, "ARP")]:
        loc = obj.location
        rot = obj.rotation_euler
        scale = obj.scale
        if (loc - Vector((0, 0, 0))).length > tolerance:
            return f"{label} 아마추어 위치가 원점이 아닙니다: {tuple(round(v, 4) for v in loc)}"
        if (Vector(rot) - Vector((0, 0, 0))).length > tolerance:
            return f"{label} 아마추어 회전이 0이 아닙니다: {tuple(round(v, 4) for v in rot)}"
        if (scale - Vector((1, 1, 1))).length > tolerance:
            return f"{label} 아마추어 스케일이 1이 아닙니다: {tuple(round(v, 4) for v in scale)}"
    return None


def _ensure_ik_mode(arp_obj):
    """ARP 리그의 모든 IK/FK 스위치를 IK 모드(0.0)로 전환.

    IK 모드에서 foot 위치를 직접 제어하고 IK solver가 다리 체인을 자동 계산.
    FK 모드의 Z축 잠금 문제를 회피한다.

    Returns:
        list[tuple]: [(pose_bone, prop_name, old_value), ...] 복원용
    """
    original_values = []
    for pbone in arp_obj.pose.bones:
        # Blender 4.5: PoseBone 직접 순회 불가, keys() 사용
        for prop_name in list(pbone.keys()):
            if prop_name.startswith("_"):
                continue
            prop_lower = prop_name.lower()
            if "ik" in prop_lower and "fk" in prop_lower:
                old_val = pbone[prop_name]
                try:
                    pbone[prop_name] = 0.0
                    original_values.append((pbone, prop_name, old_val))
                    log(f"  IK 모드: {pbone.name}['{prop_name}']: {old_val} → 0.0")
                except Exception:
                    log(f"  IK 모드: {pbone.name}['{prop_name}']: 변경 실패", "WARN")
    return original_values


def _restore_ik_fk(original_values):
    """IK/FK 스위치를 원래 값으로 복원."""
    for pbone, prop_name, old_val in original_values:
        try:
            pbone[prop_name] = old_val
        except Exception:
            pass


def bake_with_copy_transforms(source_obj, arp_obj, bone_pairs, frame_start, frame_end):
    """bone_pairs 기반으로 COPY_TRANSFORMS → Bake → Constraint 제거."""
    ensure_object_mode()
    select_only(arp_obj)
    bpy.ops.object.mode_set(mode="POSE")

    # ARP 리그가 REST 상태로 남아 있으면 제약/애니메이션이 전혀 평가되지 않아
    # bake 결과가 rest에 고정된다(회전 180° 꼬임, root 위치 이상 등 증상).
    # Build Rig의 match_to_rig가 REST로 남길 수 있으므로 방어적으로 복원.
    if arp_obj.data.pose_position != "POSE":
        log(f"  pose_position 복원: {arp_obj.data.pose_position} → POSE")
        arp_obj.data.pose_position = "POSE"
    if source_obj.data.pose_position != "POSE":
        log(
            f"  source pose_position 복원: {source_obj.data.pose_position} → POSE"
        )
        source_obj.data.pose_position = "POSE"

    # ── [1/5] IK 모드 확인 ──
    # IK 모드에서 foot 위치를 직접 제어, IK solver가 다리 체인 자동 계산
    ik_fk_originals = _ensure_ik_mode(arp_obj)
    if ik_fk_originals:
        log(f"  [1/5] IK 모드 전환 완료: {len(ik_fk_originals)}개 스위치")
    else:
        log("  [1/5] IK/FK 스위치 프로퍼티 없음 (이미 IK이거나 미지원)")

    # ── [2/5] COPY_TRANSFORMS constraint 추가 ──
    # WARN이 나오면 해당 본의 애니메이션이 누락됨
    added_bones = []
    skipped = 0
    for src_name, ctrl_name, _is_custom in bone_pairs:
        pose_bone = arp_obj.pose.bones.get(ctrl_name)
        if pose_bone is None:
            log(f"  [WARN] ARP 컨트롤러 '{ctrl_name}' 없음 — 스킵", "WARN")
            skipped += 1
            continue
        src_bone = source_obj.pose.bones.get(src_name)
        if src_bone is None:
            log(f"  [WARN] 소스 본 '{src_name}' 없음 — 스킵", "WARN")
            skipped += 1
            continue

        # c_root_master는 rest pose가 소스와 180도 반전 → COPY_LOCATION만 사용
        if ctrl_name == "c_root_master.x":
            con = pose_bone.constraints.new("COPY_LOCATION")
            con.name = BAKE_CONSTRAINT_NAME
            con.target = source_obj
            con.subtarget = src_name
            con.target_space = "WORLD"
            con.owner_space = "WORLD"
            log("  root: COPY_LOCATION (rest pose 반전 보정)")
        else:
            con = pose_bone.constraints.new("COPY_TRANSFORMS")
            con.name = BAKE_CONSTRAINT_NAME
            con.target = source_obj
            con.subtarget = src_name
            con.target_space = "WORLD"
            con.owner_space = "WORLD"
        added_bones.append(ctrl_name)

    if not added_bones:
        log("  [ERROR] 추가된 constraint 없음 — 베이크 중단", "ERROR")
        return

    log(f"  [2/5] COPY_TRANSFORMS 추가: {len(added_bones)}개 (스킵: {skipped}개)")

    # ── [3/5] nla.bake ──
    for bone in arp_obj.data.bones:
        bone.select = False
    added_set = set(added_bones)
    for bone in arp_obj.data.bones:
        if bone.name in added_set:
            bone.select = True

    bpy.ops.nla.bake(
        frame_start=frame_start,
        frame_end=frame_end,
        only_selected=True,
        visual_keying=True,
        clear_constraints=False,
        use_current_action=True,
        bake_types={"POSE"},
    )
    log(f"  [3/5] nla.bake 완료: {frame_start}~{frame_end} ({frame_end - frame_start + 1}프레임)")

    # ── [4/5] constraint 제거 ──
    removed = 0
    for ctrl_name in added_bones:
        pose_bone = arp_obj.pose.bones.get(ctrl_name)
        if pose_bone is None:
            continue
        for con in list(pose_bone.constraints):
            if con.name == BAKE_CONSTRAINT_NAME:
                pose_bone.constraints.remove(con)
                removed += 1
    log(f"  [4/5] constraint 제거: {removed}개")

    # ── [5/5] 역할 본 Scale FCurve 삭제 ──
    action = arp_obj.animation_data.action if arp_obj.animation_data else None
    if action:
        non_custom_ctrls = {ctrl for _, ctrl, is_custom in bone_pairs if not is_custom}
        fcurves_to_remove = []
        for fc in action.fcurves:
            if fc.data_path.startswith("pose.bones["):
                try:
                    bone_name = fc.data_path.split('"')[1]
                except IndexError:
                    continue
                if bone_name in non_custom_ctrls and ".scale" in fc.data_path:
                    fcurves_to_remove.append(fc)
        for fc in fcurves_to_remove:
            action.fcurves.remove(fc)
        if fcurves_to_remove:
            log(f"  [5/5] Scale FCurve 삭제: {len(fcurves_to_remove)}개 (역할 본)")
        else:
            log("  [5/5] Scale FCurve 삭제: 없음")

    ensure_object_mode()


def _collect_actions_for_armature(armature_obj):
    """아마추어에 관련된 모든 액션을 수집. _arp 접미사 액션은 제외."""
    actions = []
    armature_bone_names = {b.name for b in armature_obj.data.bones}
    for action in bpy.data.actions:
        if action.name.endswith("_arp"):
            continue
        for fc in action.fcurves:
            if fc.data_path.startswith("pose.bones["):
                try:
                    bone_name = fc.data_path.split('"')[1]
                except IndexError:
                    continue
                if bone_name in armature_bone_names:
                    actions.append(action)
                    break
    return actions


def bake_all_actions(source_obj, arp_obj, bone_pairs):
    """소스 아마추어의 모든 액션을 순회하며 ARP 컨트롤러에 베이크.

    Returns:
        list[str]: 생성된 ARP 액션 이름 리스트
    """
    actions = _collect_actions_for_armature(source_obj)
    if not actions:
        log("  [ERROR] 베이크할 액션이 없습니다.", "WARN")
        return []

    # ── 아래 숫자가 소스 액션 수와 같아야 정상 ──
    log(f"소스 액션 {len(actions)}개 발견: {', '.join(a.name for a in actions)}")

    anim_data = source_obj.animation_data
    if anim_data is None:
        source_obj.animation_data_create()
        anim_data = source_obj.animation_data

    if arp_obj.animation_data is None:
        arp_obj.animation_data_create()

    original_mute_states = [(t, t.mute) for t in anim_data.nla_tracks]
    created_actions = []

    for action_idx, action in enumerate(actions):
        action_name = action.name
        frame_start = int(action.frame_range[0])
        frame_end = int(action.frame_range[1])
        arp_action_name = f"{action_name}_arp"

        log(
            f"  ── [{action_idx + 1}/{len(actions)}] '{action_name}' ({frame_start}~{frame_end}) ──"
        )

        existing_arp = bpy.data.actions.get(arp_action_name)
        if existing_arp:
            bpy.data.actions.remove(existing_arp)
            log(f"    기존 '{arp_action_name}' 삭제")

        arp_action = bpy.data.actions.new(name=arp_action_name)
        arp_action.use_fake_user = True
        # 이전 액션이 NLA에 auto-push되지 않도록 먼저 해제
        arp_obj.animation_data.action = None
        arp_obj.animation_data.action = arp_action

        for track, _ in original_mute_states:
            track.mute = True

        tmp_track = anim_data.nla_tracks.new()
        tmp_track.name = "_arpconv_tmp"
        tmp_strip = tmp_track.strips.new(action_name, int(action.frame_range[0]), action)
        tmp_strip.action_frame_start = frame_start
        tmp_strip.action_frame_end = frame_end

        try:
            bake_with_copy_transforms(source_obj, arp_obj, bone_pairs, frame_start, frame_end)
            created_actions.append(arp_action_name)
            log(f"    → '{arp_action_name}' 생성 완료")
        except Exception as e:
            log(f"    베이크 실패: {e}", "ERROR")
            if arp_obj.animation_data and arp_obj.animation_data.action == arp_action:
                arp_obj.animation_data.action = None
            bpy.data.actions.remove(arp_action)
        finally:
            anim_data.nla_tracks.remove(tmp_track)
            for track, was_muted in original_mute_states:
                track.mute = was_muted
            ensure_object_mode()
            for _, ctrl_name, _ in bone_pairs:
                pose_bone = arp_obj.pose.bones.get(ctrl_name)
                if pose_bone is None:
                    continue
                for con in list(pose_bone.constraints):
                    if con.name == BAKE_CONSTRAINT_NAME:
                        pose_bone.constraints.remove(con)

    # ARP에 자동 생성된 NLA 트랙 정리 (액션은 fake_user로 보존)
    arp_anim = arp_obj.animation_data
    if arp_anim:
        nla_count = len(arp_anim.nla_tracks)
        for track in list(arp_anim.nla_tracks):
            arp_anim.nla_tracks.remove(track)
        if nla_count:
            log(f"  ARP NLA 트랙 정리: {nla_count}개 제거")

    # ── 최종 결과 (이 줄을 전달해주세요) ──
    log("=" * 50)
    if len(created_actions) == len(actions):
        log(f"[결과] 베이크 성공: {len(created_actions)}/{len(actions)} 액션 완료")
    else:
        failed = len(actions) - len(created_actions)
        log(f"[결과] 베이크 부분 실패: {len(created_actions)} 성공, {failed} 실패")
    log(f"[결과] 생성된 액션: {', '.join(created_actions)}")
    log("=" * 50)
    return created_actions

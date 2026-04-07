"""
ARP 변환 공유 유틸리티
=====================
Entrypoints:
  log(msg, level)               — 레벨 필터링 로깅
  find_arp_armature()           → ARP 아마추어 or None
  find_source_armature()        → 소스 아마추어 or None
  find_mesh_objects(armature)   → [mesh objects]
  run_arp_operator(op, **kw)    — ARP 오퍼레이터 안전 실행
  load_mapping_profile(name)    → deform→ref 매핑 dict
  serialize_bone_pairs(pairs)   → JSON str
  setup_arp_retarget(src, arp, pairs) → dict  (리타겟 재설계 예정)

Consumes: bpy scene state
Produces: armature/mesh discovery, operator execution, retarget setup
"""

import contextlib
import json
import os
import re
from datetime import datetime

import bpy

_PROJECT_RESOURCE_DIRS = (
    "mapping_profiles",
    "regression_fixtures",
)

# ── 로그 레벨 (MCP quiet 모드 지원) ──
# 기본 INFO. MCP 함수 내부에서 quiet_logs() 컨텍스트가 WARN으로 올려
# 호출 중 발생하는 INFO 로그를 억제한다. GUI 경로는 set_log_level을 호출하지
# 않으므로 Blender 시스템 콘솔 출력은 변함없음.
_LOG_LEVELS = {"DEBUG": 0, "INFO": 1, "WARN": 2, "WARNING": 2, "ERROR": 3}
_LOG_LEVEL = 1  # INFO


def set_log_level(level):
    """모듈 레벨 로그 임계값 변경. level: DEBUG/INFO/WARN/ERROR."""
    global _LOG_LEVEL
    _LOG_LEVEL = _LOG_LEVELS.get(level.upper(), 1)


def get_log_level():
    """현재 로그 레벨(정수) 반환."""
    return _LOG_LEVEL


@contextlib.contextmanager
def quiet_logs(level="WARN"):
    """컨텍스트 동안 로그 임계값을 올려 INFO/DEBUG 출력을 억제한다."""
    global _LOG_LEVEL
    prev = _LOG_LEVEL
    set_log_level(level)
    try:
        yield
    finally:
        _LOG_LEVEL = prev


def log(msg, level="INFO"):
    """로그 출력. 임계값보다 낮은 레벨은 건너뜀."""
    if _LOG_LEVELS.get(level.upper(), 1) < _LOG_LEVEL:
        return
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
# F12: ARP 리타겟 위임 유틸리티
# ═══════════════════════════════════════════════════════════════

BAKE_PAIRS_KEY = "arpconv_bone_pairs"

# IK foot 컨트롤러 패턴 (location=False, ik=True)
_IK_CTRL_PATTERN = re.compile(r"^c_foot_ik|^c_hand_ik")
# Pole vector 패턴 (pole_parent=1로 처리, 매핑 제외)
_POLE_CTRL_PATTERN = re.compile(r"^c_(leg|arm)_pole")


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


def _classify_ctrl(ctrl_name, is_custom):
    """컨트롤러 이름에서 ARP 리타겟 플래그를 결정한다.

    Returns:
        dict: {"location": bool, "ik": bool, "set_as_root": bool, "ctrl": str}
    """
    # root: c_root_master.x → c_root.x로 교체
    if ctrl_name == "c_root_master.x":
        return {"ctrl": "c_root.x", "location": True, "ik": False, "set_as_root": True}

    # IK foot/hand 컨트롤러
    if _IK_CTRL_PATTERN.match(ctrl_name):
        return {"ctrl": ctrl_name, "location": False, "ik": True, "set_as_root": False}

    # 커스텀 본 또는 일반 FK
    return {"ctrl": ctrl_name, "location": True, "ik": False, "set_as_root": False}


def _override_bones_map(bone_pairs):
    """bone_pairs 기반으로 ARP bones_map_v2 엔트리를 오버라이드.

    bone_pairs에 매핑이 있는 본은 우리 매핑으로 덮어쓰고,
    bone_pairs에 없는 본은 빈 매핑("")으로 비운다.
    사용자가 필요하면 ARP Remap UI에서 수동 추가 가능.
    """
    scn = bpy.context.scene

    # bone_pairs → 룩업 테이블 (src_name → 매핑 정보)
    # pole vector 본은 제외 (pole_parent=1로 ARP가 자동 처리)
    lookup = {}
    for src_name, ctrl_name, is_custom in bone_pairs:
        if _POLE_CTRL_PATTERN.match(ctrl_name):
            continue
        classified = _classify_ctrl(ctrl_name, is_custom)
        lookup[src_name] = classified

    overridden = 0
    cleared = 0
    for entry in scn.bones_map_v2:
        if entry.source_bone in lookup:
            info = lookup[entry.source_bone]
            entry.name = info["ctrl"]
            entry.location = info["location"]
            entry.ik = info["ik"]
            entry.set_as_root = info["set_as_root"]
            overridden += 1
        elif entry.name:
            # bone_pairs에 없는 본: ARP 자동 추측 제거
            entry.name = ""
            entry.location = False
            entry.ik = False
            entry.set_as_root = False
            cleared += 1

    log(f"  bones_map_v2 오버라이드: {overridden}/{len(lookup)}개, 추측 제거: {cleared}개")
    if overridden < len(lookup):
        missing = set(lookup.keys()) - {e.source_bone for e in scn.bones_map_v2}
        if missing:
            log(f"  bones_map_v2에 없는 소스 본: {missing}", "WARN")


def _delete_existing_remap_actions():
    """기존 _remap 액션을 삭제하여 중복 방지."""
    removed = []
    for action in list(bpy.data.actions):
        if action.name.endswith("_remap") or "_remap." in action.name:
            removed.append(action.name)
            bpy.data.actions.remove(action)
    if removed:
        log(f"  기존 _remap 액션 삭제: {len(removed)}개")


def setup_arp_retarget(source_obj, arp_obj, bone_pairs):
    """bone_pairs를 ARP bones_map_v2로 변환하고 리타겟 씬 프로퍼티를 설정한다.

    ARP Remap 패널에서 사용자가 매핑을 확인/수정한 뒤
    ARP Re-Retarget 버튼을 직접 클릭하여 베이크한다.

    Returns:
        dict: {"overridden": int, "total_pairs": int, "remap_deleted": int}
    """
    scn = bpy.context.scene

    # 1. Scene property 세팅
    scn.source_rig = source_obj.name
    scn.target_rig = arp_obj.name
    log(f"  source_rig={source_obj.name}, target_rig={arp_obj.name}")

    # 2. ARP build_bones_list 호출 → bones_map_v2 생성
    ensure_object_mode()
    select_only(arp_obj)
    run_arp_operator(bpy.ops.arp.build_bones_list)
    log(f"  build_bones_list 완료: {len(scn.bones_map_v2)}개 엔트리")

    # 3. bone_pairs 기반 오버라이드
    _override_bones_map(bone_pairs)

    # 4. batch_retarget 활성화
    scn.batch_retarget = True
    log("  batch_retarget = True")

    # 5. 기존 _remap 액션 삭제
    _delete_existing_remap_actions()

    return {
        "overridden": len(bone_pairs),
        "total_map_entries": len(scn.bones_map_v2),
    }


def cleanup_after_retarget(source_obj, preview_obj):
    """소스/프리뷰 아마추어 삭제 + _remap 액션을 원본 이름으로 rename.

    Returns:
        dict: {"deleted_armatures": list, "renamed_actions": list}
    """
    deleted_armatures = []
    renamed_actions = []

    # 1. 소스 액션 삭제 (rename 충돌 방지)
    if source_obj and source_obj.type == "ARMATURE":
        source_bone_names = {b.name for b in source_obj.data.bones}
        for action in list(bpy.data.actions):
            if action.name.endswith("_remap") or "_remap." in action.name:
                continue
            for fc in action.fcurves:
                if fc.data_path.startswith("pose.bones["):
                    try:
                        bone_name = fc.data_path.split('"')[1]
                    except IndexError:
                        continue
                    if bone_name in source_bone_names:
                        log(f"  소스 액션 삭제: {action.name}")
                        bpy.data.actions.remove(action)
                        break

    # 2. 소스/프리뷰 아마추어 삭제
    for obj in [source_obj, preview_obj]:
        if obj is None:
            continue
        armature_data = obj.data if obj.type == "ARMATURE" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if armature_data and armature_data.users == 0:
            bpy.data.armatures.remove(armature_data)
        deleted_armatures.append(obj.name)
        log(f"  아마추어 삭제: {obj.name}")

    # 3. _remap 액션을 원본 이름으로 rename
    for action in list(bpy.data.actions):
        if action.name.endswith("_remap"):
            original_name = action.name[: -len("_remap")]
            # 이름 충돌 확인
            if bpy.data.actions.get(original_name):
                log(f"  rename 스킵 (충돌): {action.name} → {original_name}", "WARN")
                continue
            old_name = action.name
            action.name = original_name
            renamed_actions.append(f"{old_name} → {original_name}")
            log(f"  액션 rename: {old_name} → {original_name}")

    return {
        "deleted_armatures": deleted_armatures,
        "renamed_actions": renamed_actions,
    }

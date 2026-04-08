"""
ARP 변환 공유 유틸리티 (코어)
============================
로깅, Blender 컨텍스트 관리, 아마추어/메시 탐색, 매핑 프로필 로딩 등
모든 모듈이 공통으로 사용하는 기반 함수를 모은다.

리타겟 관련 함수(setup_arp_retarget, cleanup_after_retarget 등)는
arp_retarget 모듈로 분리되었으며, 하위 호환을 위해 이 파일 끝에서
재수출(re-export)한다.

Entrypoints:
  log(msg, level)               — 레벨 필터링 로깅
  find_arp_armature()           → ARP 아마추어 or None
  find_source_armature()        → 소스 아마추어 or None
  find_mesh_objects(armature)   → [mesh objects]
  run_arp_operator(op, **kw)    — ARP 오퍼레이터 안전 실행
  load_mapping_profile(name)    → deform→ref 매핑 dict
  serialize_bone_pairs(pairs)   → JSON str  (re-exported from arp_retarget)
  setup_arp_retarget(...)       → dict      (re-exported from arp_retarget)

Consumes: bpy scene state
Produces: armature/mesh discovery, operator execution, logging
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
# 하위 호환: arp_retarget의 public 심볼 재수출
# 기존 from arp_utils import X 구문이 계속 동작하도록 함
# ═══════════════════════════════════════════════════════════════
from arp_retarget import *  # noqa: F403

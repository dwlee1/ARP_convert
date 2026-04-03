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

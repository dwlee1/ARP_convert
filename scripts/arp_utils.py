"""
ARP 변환 공유 유틸리티
=====================
01_create_arp_rig.py, 02_retarget_animation.py 에서 공통 사용
"""

import bpy
import os
import json
import shutil
from datetime import datetime


def log(msg, level="INFO"):
    """로그 출력"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def ensure_object_mode():
    """Object 모드로 전환"""
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')


def select_only(obj):
    """오브젝트 하나만 선택 & 활성화"""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def get_3d_viewport_context():
    """3D Viewport 컨텍스트 반환. ARP 오퍼레이터 실행에 필요."""
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
    try:
        with bpy.context.temp_override(**ctx):
            return op_func(**kwargs)
    except RuntimeError as e:
        active = bpy.context.view_layer.objects.active
        mode = bpy.context.mode
        op_name = getattr(op_func, 'idname_py', lambda: str(op_func))()
        log(f"오퍼레이터 실패: {op_name} (active={active.name if active else None}, mode={mode})", "ERROR")
        raise


def ensure_retarget_context(source_obj, arp_obj):
    """리타게팅 전 컨텍스트 설정 (auto_scale 호출 전에 사용)"""
    ensure_object_mode()
    bpy.context.scene.source_rig = source_obj.name
    bpy.context.scene.target_rig = arp_obj.name
    select_only(source_obj)
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
            "Blender Foundation", "Blender", blender_ver,
            "extensions", "user_default", "auto_rig_pro", "remap_presets"
        ),
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Blender Foundation", "Blender", blender_ver,
            "config", "addons", "auto_rig_pro-master", "remap_presets"
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
        if obj.type != 'ARMATURE':
            continue
        arp_bones = [b for b in obj.data.bones if b.name.startswith('c_')]
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
        if obj.type != 'ARMATURE':
            continue
        c_bones = len([b for b in obj.data.bones if b.name.startswith('c_')])
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
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == armature_obj:
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
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    profile_path = os.path.join(project_root, "mapping_profiles", f"{profile_name}.json")

    if not os.path.exists(profile_path):
        raise FileNotFoundError(f"매핑 프로필 미발견: {profile_path}")

    with open(profile_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    # L→R 미러링
    mirror = raw.get("mirror_suffix", {})
    src_suffixes = mirror.get("source", ["_L", "_R"])
    arp_suffixes = mirror.get("arp", [".l", ".r"])

    deform_to_ref = dict(raw["deform_to_ref"])

    if isinstance(src_suffixes, list) and len(src_suffixes) == 2 and isinstance(arp_suffixes, list) and len(arp_suffixes) == 2:
        l_suffix, r_suffix = src_suffixes
        l_arp, r_arp = arp_suffixes
        for src_name, ref_name in list(raw["deform_to_ref"].items()):
            if src_name.endswith(l_suffix) and ref_name.endswith(l_arp):
                r_src = src_name[:-len(l_suffix)] + r_suffix
                r_ref = ref_name[:-len(l_arp)] + r_arp
                if r_src not in deform_to_ref:
                    deform_to_ref[r_src] = r_ref

    log(f"프로필 로드: '{raw['name']}' — 매핑 {len(deform_to_ref)}개 (미러 포함)")

    return {
        'name': raw['name'],
        'description': raw.get('description', ''),
        'arp_preset': raw.get('arp_preset', 'dog'),
        'bmap_preset': raw.get('bmap_preset', ''),
        'deform_to_ref': deform_to_ref,
        'ref_alignment': raw.get('ref_alignment', {}),
    }

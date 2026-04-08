"""
ARP Rig Convert 애드온
======================
소스 deform 본 → Preview Armature 생성 → 역할 배정/수정 → ARP 리그 생성.

설치:
  Edit > Preferences > Add-ons > Install > 이 파일 선택
  또는 Blender Scripting 탭에서 직접 실행 (Run Script)
  또는 tools/install_blender_addon.py 로 Blender 4.5 add-ons 폴더에 자동 설치
"""

bl_info = {
    "name": "ARP Rig Convert",
    "author": "BlenderRigConvert",
    "version": (2, 0, 0),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > ARP Convert",
    "description": "Preview Armature 기반 ARP 리그 변환",
    "category": "Rigging",
}

import json
import os
import sys
import time
import traceback

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Vector

# ═══════════════════════════════════════════════════════════════
# scripts/ 경로 설정
# ═══════════════════════════════════════════════════════════════

_PROJECT_RESOURCE_DIRS = (
    "mapping_profiles",
    "regression_fixtures",
)


def _ensure_scripts_path():
    """scripts/ 폴더를 sys.path에 추가"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "skeleton_analyzer.py")):
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        return script_dir

    # bpy.data가 restricted context (애드온 등록 중)면 filepath 접근 불가 → 조용히 skip
    try:
        blend_filepath = bpy.data.filepath
    except AttributeError:
        blend_filepath = ""

    if blend_filepath:
        d = os.path.dirname(blend_filepath)
        for _ in range(10):
            candidate = os.path.join(d, "scripts")
            if os.path.exists(os.path.join(candidate, "skeleton_analyzer.py")):
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                return candidate
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return ""


def _reload_modules():
    """개발 중 모듈 리로드.

    주의: arp_utils는 제외. import 시점에 `from arp_utils import log`로
    캡처된 함수 참조가 reload로 끊기면 외부에서 설정한 `quiet_logs()` 효과가
    reload 이후 사라진다. arp_utils 수정은 `mcp_reload_addon()`으로 처리.
    """
    import importlib

    for mod_name in [
        "skeleton_analyzer",
        "weight_transfer_rules",
        "arp_weight_xfer",
        "arp_foot_guides",
        "arp_fixture_io",
        "arp_cc_bones",
        "arp_build_helpers",
        "arp_def_separator",
        "arp_props",
        "arp_ui",
        "arp_ops_preview",
        "arp_ops_roles",
        "arp_ops_bake_regression",
        "arp_ops_build",
    ]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


_ensure_scripts_path()

# 분리된 helper 모듈 import (scripts/ 경로 설정 이후)
from arp_ops_bake_regression import (
    ARPCONV_OT_Cleanup,
    ARPCONV_OT_CopyCustomScale,
    ARPCONV_OT_RunRegression,
    ARPCONV_OT_SetupRetarget,
)
from arp_ops_build import ARPCONV_OT_BuildRig
from arp_ops_preview import ARPCONV_OT_CreatePreview
from arp_ops_roles import (
    ROLE_IDS,
    ROLE_ITEMS,
    ARPCONV_OT_SelectBone,
    ARPCONV_OT_SetParent,
    ARPCONV_OT_SetRole,
)
from arp_props import ARPCONV_HierarchyBoneItem, ARPCONV_Props
from arp_ui import ARPCONV_PT_MainPanel

# ═══════════════════════════════════════════════════════════════
# 등록
# ═══════════════════════════════════════════════════════════════

classes = [
    ARPCONV_HierarchyBoneItem,
    ARPCONV_Props,
    ARPCONV_OT_CreatePreview,
    ARPCONV_OT_SelectBone,
    ARPCONV_OT_SetParent,
    ARPCONV_OT_SetRole,
    ARPCONV_OT_BuildRig,
    ARPCONV_OT_SetupRetarget,
    ARPCONV_OT_CopyCustomScale,
    ARPCONV_OT_Cleanup,
    ARPCONV_OT_RunRegression,
    ARPCONV_PT_MainPanel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.arp_convert_props = PointerProperty(type=ARPCONV_Props)
    bpy.types.Scene.arp_source_hierarchy = CollectionProperty(type=ARPCONV_HierarchyBoneItem)


def unregister():
    if hasattr(bpy.types.Scene, "arp_source_hierarchy"):
        del bpy.types.Scene.arp_source_hierarchy
    del bpy.types.Scene.arp_convert_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

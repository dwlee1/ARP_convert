"""
arp_convert_addon에서 분리한 PropertyGroup 정의.

ARPCONV_HierarchyBoneItem: Source Hierarchy 트리의 개별 본 항목.
ARPCONV_Props: Scene 레벨 addon state (source_armature, preview 등).

register/unregister는 arp_convert_addon.py가 담당. 이 파일은 class
정의만 제공하고, import로 가져다 쓰게 한다.
"""

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
from bpy.types import PropertyGroup


class ARPCONV_HierarchyBoneItem(PropertyGroup):
    """하이어라키 트리 아이템 (name은 PropertyGroup에서 상속)"""

    depth: IntProperty(default=0)


class ARPCONV_Props(PropertyGroup):
    """전역 프로퍼티"""

    preview_armature: StringProperty(name="Preview Armature", default="")
    source_armature: StringProperty(name="소스 Armature", default="")
    is_analyzed: BoolProperty(name="분석 완료", default=False)
    confidence: FloatProperty(name="신뢰도", default=0.0)
    regression_fixture: StringProperty(
        name="Fixture JSON",
        default="",
        subtype="FILE_PATH",
    )
    regression_report_dir: StringProperty(
        name="Report Dir",
        default="",
        subtype="DIR_PATH",
    )
    front_3bones_ik: FloatProperty(
        name="앞다리 3 Bones IK",
        description="앞다리 3 Bones IK 값. 0.0이면 shoulder 독립 회전, 1.0이면 foot IK에 반응",
        default=0.0,
        min=0.0,
        max=1.0,
    )
    show_source_hierarchy: BoolProperty(
        name="Source Hierarchy",
        description="소스 본 하이어라키 트리 표시",
        default=False,
    )
    pending_parent: StringProperty(
        name="Parent",
        description="선택한 본의 새 부모 (빈 문자열 = 루트)",
        default="",
    )

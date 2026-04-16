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


def _deferred_apply_parent():
    """타이머 콜백: 3D View temp_override 안에서 set_parent 실행 후 POSE 복원"""
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    with bpy.context.temp_override(area=area, region=region):
                        bpy.ops.arp_convert.set_parent()
                    # 타이머 컨텍스트에서 오퍼레이터가 POSE 복원에 실패할 수 있음
                    with bpy.context.temp_override(area=area, region=region):
                        if bpy.context.mode != "POSE":
                            bpy.ops.object.mode_set(mode="POSE")
                    return None
    return None


def _on_pending_parent_changed(self, context):
    """pending_parent가 유효한 본 이름으로 설정되면 즉시 부모 변경 적용"""
    name = self.pending_parent.strip()
    if not name:
        return
    preview_obj = bpy.data.objects.get(self.preview_armature)
    if not preview_obj or name not in preview_obj.data.bones:
        return
    # 선택된 본이 있어야 적용 (자기 자신 제외)
    has_target = any(b.select for b in preview_obj.data.bones if b.name != name)
    if not has_target:
        return
    bpy.app.timers.register(_deferred_apply_parent, first_interval=0.01)


class ARPCONV_HierarchyBoneItem(PropertyGroup):
    """하이어라키 트리 아이템 (name은 PropertyGroup에서 상속)"""

    depth: IntProperty(default=0)
    tree_prefix: StringProperty(default="")


class ARPCONV_Props(PropertyGroup):
    """전역 프로퍼티"""

    preview_armature: StringProperty(
        name="프리뷰 아마추어",
        description="생성된 프리뷰 아마추어",
        default="",
    )
    source_armature: StringProperty(
        name="소스 아마추어",
        description="변환할 원본 아마추어",
        default="",
    )
    is_analyzed: BoolProperty(
        name="분석 완료",
        description="소스 아마추어 분석 완료 여부",
        default=False,
    )
    confidence: FloatProperty(
        name="신뢰도",
        description="자동 역할 추론 신뢰도 (0~100%)",
        default=0.0,
    )
    regression_fixture: StringProperty(
        name="Fixture JSON",
        description="회귀 테스트용 피처 파일 경로",
        default="",
        subtype="FILE_PATH",
    )
    regression_report_dir: StringProperty(
        name="리포트 폴더",
        description="회귀 테스트 결과 저장 폴더",
        default="",
        subtype="DIR_PATH",
    )
    front_3bones_ik: FloatProperty(
        name="앞다리 3본 IK",
        description="앞다리 3본 IK 영향도. 0이면 어깨 독립 회전, 1이면 발 IK에 연동",
        default=0.0,
        min=0.0,
        max=1.0,
    )
    show_source_hierarchy: BoolProperty(
        name="소스 계층 트리",
        description="소스 본 계층 트리 표시/숨김",
        default=False,
    )
    pending_parent: StringProperty(
        name="새 부모",
        description="선택한 본의 새 부모 — 선택 시 자동 적용",
        default="",
        update=_on_pending_parent_changed,
    )
    build_completed: BoolProperty(
        name="리그 생성 완료",
        description="Build Rig 완료 여부",
        default=False,
    )
    retarget_setup_done: BoolProperty(
        name="리타겟 설정 완료",
        description="Retarget Setup 완료 여부",
        default=False,
    )
    mapped_bone_count: IntProperty(
        name="매핑 본 수",
        description="역할이 매핑된 본 수",
        default=0,
    )
    total_bone_count: IntProperty(
        name="전체 본 수",
        description="프리뷰 아마추어의 전체 본 수",
        default=0,
    )

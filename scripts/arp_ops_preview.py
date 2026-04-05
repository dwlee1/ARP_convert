"""
arp_convert_addon에서 분리한 CreatePreview 오퍼레이터 + hierarchy 헬퍼.

Step 2 (Create Preview)를 담당한다. 소스 아마추어를 분석하고 Preview
Armature를 생성하며, Source Hierarchy 트리 데이터를 CollectionProperty에
채운다.
"""

import bpy
from bpy.types import Operator

from arp_utils import log

# ───────────────────────────────────────────────────────────────
# hierarchy 헬퍼 (CreatePreview 전용 + arp_cc_bones / arp_build_helpers에서도 참조)
# ───────────────────────────────────────────────────────────────


def _populate_hierarchy_collection(context, analysis):
    """deform 본 + 제외 본을 depth-first 순서로 CollectionProperty에 저장."""
    coll = context.scene.arp_source_hierarchy
    coll.clear()

    bone_data = analysis.get("bone_data", {})
    excluded = analysis.get("excluded_zero_weight", [])

    if not bone_data:
        return

    # 제외 본을 부모별로 그룹핑
    excluded_by_parent = {}
    for info in excluded:
        p = info["parent"]
        excluded_by_parent.setdefault(p, []).append(info["name"])

    # bone_data에서 루트부터 DFS
    roots = [name for name, b in bone_data.items() if b["parent"] is None]

    def _walk(name, depth):
        item = coll.add()
        item.name = name
        item.depth = depth
        # deform 자식 재귀
        for child_name in bone_data[name].get("children", []):
            _walk(child_name, depth + 1)
        # 제외 본은 deform 자식 뒤에 추가
        for excl_name in excluded_by_parent.get(name, []):
            ei = coll.add()
            ei.name = excl_name
            ei.depth = depth + 1

    for root in roots:
        _walk(root, 0)
    # 부모 없는 제외 본 (루트 레벨)
    for excl_name in excluded_by_parent.get(None, []):
        ei = coll.add()
        ei.name = excl_name
        ei.depth = 0


def _build_preview_hierarchy(preview_obj):
    hierarchy = {}
    for bone in preview_obj.data.bones:
        hierarchy[bone.name] = {
            "parent": bone.parent.name if bone.parent else None,
            "use_connect": bool(getattr(bone, "use_connect", False)),
        }
    return hierarchy


def _iter_preview_ancestors(source_bone_name, preview_hierarchy):
    visited = set()
    current_name = source_bone_name

    while current_name and current_name not in visited:
        visited.add(current_name)
        bone_info = preview_hierarchy.get(current_name, {})
        parent_name = bone_info.get("parent")
        if not parent_name:
            break
        yield parent_name
        current_name = parent_name


# ───────────────────────────────────────────────────────────────
# 오퍼레이터: Step 1 — 분석 + Preview 생성
# ───────────────────────────────────────────────────────────────


class ARPCONV_OT_CreatePreview(Operator):
    """소스 deform 본 추출 → Preview Armature 생성"""

    bl_idname = "arp_convert.create_preview"
    bl_label = "리그 분석 + Preview 생성"
    bl_description = "소스 deform 본을 분석하여 역할별 색상이 적용된 Preview Armature를 생성"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from arp_convert_addon import _ensure_scripts_path, _reload_modules

        _ensure_scripts_path()
        _reload_modules()

        try:
            from skeleton_analyzer import (
                analyze_skeleton,
                create_preview_armature,
                generate_verification_report,
            )
        except ImportError as e:
            self.report({"ERROR"}, f"skeleton_analyzer 임포트 실패: {e}")
            return {"CANCELLED"}

        # 소스 아마추어 찾기
        source_obj = self._find_source(context)
        if source_obj is None:
            self.report({"ERROR"}, "소스 아마추어를 찾을 수 없습니다.")
            return {"CANCELLED"}

        # 기존 Preview 제거
        props = context.scene.arp_convert_props
        old_preview = bpy.data.objects.get(props.preview_armature)
        if old_preview:
            bpy.data.objects.remove(old_preview, do_unlink=True)

        # Object 모드 확보
        if bpy.context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        # 분석
        analysis = analyze_skeleton(source_obj)
        if "error" in analysis:
            self.report({"ERROR"}, analysis["error"])
            return {"CANCELLED"}

        # 검증 리포트 출력
        print(generate_verification_report(analysis))

        # Preview Armature 생성
        preview_obj = create_preview_armature(source_obj, analysis)
        if preview_obj is None:
            self.report({"ERROR"}, "Preview Armature 생성 실패")
            return {"CANCELLED"}

        # 프로퍼티 저장
        props.source_armature = source_obj.name
        props.preview_armature = preview_obj.name
        props.is_analyzed = True
        props.confidence = analysis.get("confidence", 0)

        # 하이어라키 트리 데이터 채우기
        _populate_hierarchy_collection(context, analysis)

        # Preview 선택
        bpy.ops.object.select_all(action="DESELECT")
        preview_obj.select_set(True)
        context.view_layer.objects.active = preview_obj

        self.report(
            {"INFO"},
            f"Preview 생성 완료 (신뢰도: {props.confidence:.0%}). "
            f"본 선택 → 사이드바에서 역할 변경 가능.",
        )
        return {"FINISHED"}

    def _find_source(self, context):
        """소스 아마추어 찾기: 선택된 것 우선, 없으면 자동"""
        if context.active_object and context.active_object.type == "ARMATURE":
            c_count = len([b for b in context.active_object.data.bones if b.name.startswith("c_")])
            if c_count <= 5 and "_preview" not in context.active_object.name:
                return context.active_object

        best_obj = None
        best_count = 0
        for obj in bpy.data.objects:
            if obj.type != "ARMATURE":
                continue
            if "_preview" in obj.name:
                continue
            c_count = len([b for b in obj.data.bones if b.name.startswith("c_")])
            if c_count > 5:
                continue
            total = len(obj.data.bones)
            if total > best_count:
                best_count = total
                best_obj = obj
        return best_obj

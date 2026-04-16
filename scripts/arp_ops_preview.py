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


def compute_tree_prefixes(items):
    """depth 기반 아이템 리스트로 트리 연결선 접두사를 계산한다.

    Parameters
    ----------
    items : list[dict]
        각 dict에 "name"(str), "depth"(int) 키 필요.

    Returns
    -------
    list[str]
        각 아이템의 트리 접두사 문자열.
    """
    n = len(items)
    prefixes = [""] * n

    def _has_next_sibling(idx):
        """idx 아이템 뒤에 같은 depth의 형제가 있는지."""
        my_depth = items[idx]["depth"]
        for j in range(idx + 1, n):
            d = items[j]["depth"]
            if d == my_depth:
                return True
            if d < my_depth:
                return False
        return False

    for i in range(n):
        depth = items[i]["depth"]
        if depth == 0:
            prefixes[i] = ""
            continue

        parts = []
        # 조상 레벨별로 수직선(│) 또는 공백 결정
        for d in range(1, depth):
            # depth=d인 조상이 다음 형제를 갖는지 확인
            ancestor_idx = None
            for k in range(i - 1, -1, -1):
                if items[k]["depth"] == d:
                    ancestor_idx = k
                    break
                if items[k]["depth"] < d:
                    break
            if ancestor_idx is not None and _has_next_sibling(ancestor_idx):
                parts.append("│  ")
            else:
                parts.append("   ")

        # 현재 아이템의 연결 문자
        if _has_next_sibling(i):
            parts.append("├─ ")
        else:
            parts.append("└─ ")

        prefixes[i] = "".join(parts)

    return prefixes


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
        if name not in bone_data:
            return
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

    # tree_prefix 계산
    items_for_prefix = [{"name": item.name, "depth": item.depth} for item in coll]
    prefixes = compute_tree_prefixes(items_for_prefix)
    for i, item in enumerate(coll):
        item.tree_prefix = prefixes[i]


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
            from arp_def_separator import create_def_bones
            from skeleton_analyzer import (
                analyze_skeleton,
                chains_to_flat_roles,
                create_preview_from_def_bones,
                generate_verification_report,
            )
        except ImportError as e:
            self.report({"ERROR"}, f"모듈 임포트 실패: {e}")
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

        # 검증 리포트 출력 (quiet_logs 컨텍스트에서 억제됨)
        log(generate_verification_report(analysis), "INFO")

        # DEF 본 분리 (Preview 생성 전에 clean hierarchy 구축)
        flat_roles = chains_to_flat_roles(analysis)
        def_result = create_def_bones(source_obj, flat_roles)
        log(f"DEF 본 {len(def_result)}개 생성", "INFO")

        # Preview Armature 생성 (DEF 기반)
        preview_obj = create_preview_from_def_bones(source_obj, analysis)
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

        # bone count 캐시 업데이트
        _preview_for_count = bpy.data.objects.get(props.preview_armature)
        if _preview_for_count:
            from skeleton_analyzer import ROLE_PROP_KEY

            total = len(_preview_for_count.pose.bones)
            mapped = sum(
                1
                for pb in _preview_for_count.pose.bones
                if pb.get(ROLE_PROP_KEY, "unmapped") != "unmapped"
            )
            props.total_bone_count = total
            props.mapped_bone_count = mapped

        # 소스 아마추어 숨기기 (Preview 편집 중 겹침 방지)
        source_obj.hide_set(True)

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

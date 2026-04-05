"""
blender-mcp 브릿지 모듈
=======================
Claude Code에서 execute_blender_code()를 통해 호출하는 고수준 함수 모음.
각 함수는 JSON 결과를 stdout으로 출력한다.

사용법 (Claude Code → blender-mcp):
    execute_blender_code(code='''
    import sys; sys.path.insert(0, r'C:\\Users\\manag\\Desktop\\BlenderRigConvert\\scripts')
    from mcp_bridge import mcp_scene_summary
    mcp_scene_summary()
    ''')
"""

import json
import os
import sys
import traceback

import bpy

# ── 프로젝트 모듈 경로 보장 ──
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


def _result(success, data=None, error=None):
    """표준 JSON 결과를 stdout으로 출력."""
    out = {"success": success}
    if data is not None:
        out["data"] = data
    if error is not None:
        out["error"] = error
    print(json.dumps(out, ensure_ascii=False, default=str))


def _reload():
    """개발 중 모듈 리로드."""
    import importlib

    for mod_name in [
        "skeleton_analyzer",
        "arp_utils",
        "weight_transfer_rules",
        "mcp_verify",
    ]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


# ═══════════════════════════════════════════════════════════════
# 1. mcp_scene_summary — 씬 요약
# ═══════════════════════════════════════════════════════════════


def mcp_scene_summary():
    """현재 씬의 아마추어, 메시, 액션 요약을 JSON으로 출력."""
    try:
        armatures = []
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                bone_count = len(obj.data.bones)
                c_bones = len([b for b in obj.data.bones if b.name.startswith("c_")])
                armatures.append(
                    {
                        "name": obj.name,
                        "bone_count": bone_count,
                        "c_bone_count": c_bones,
                        "is_arp": c_bones > 5,
                    }
                )

        meshes = []
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                arm_mod = None
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE" and mod.object:
                        arm_mod = mod.object.name
                        break
                meshes.append(
                    {
                        "name": obj.name,
                        "vertex_count": len(obj.data.vertices),
                        "bound_armature": arm_mod,
                    }
                )

        actions = []
        for action in bpy.data.actions:
            frame_range = (int(action.frame_range[0]), int(action.frame_range[1]))
            actions.append(
                {
                    "name": action.name,
                    "frame_range": frame_range,
                    "fcurve_count": len(action.fcurves),
                }
            )

        _result(
            True,
            {
                "blend_file": bpy.data.filepath or "(unsaved)",
                "armatures": armatures,
                "meshes": meshes,
                "actions": actions,
                "frame_range": [bpy.context.scene.frame_start, bpy.context.scene.frame_end],
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 2. mcp_create_preview — Preview Armature 생성
# ═══════════════════════════════════════════════════════════════


def mcp_create_preview():
    """소스 아마추어를 분석하고 Preview Armature를 생성."""
    try:
        _reload()
        from arp_utils import ensure_object_mode, get_3d_viewport_context

        ensure_object_mode()
        ctx = get_3d_viewport_context()
        if ctx is None:
            _result(False, error="3D Viewport를 찾을 수 없습니다.")
            return

        with bpy.context.temp_override(**ctx):
            result = bpy.ops.arp_convert.create_preview()

        if "FINISHED" not in result:
            _result(False, error="Preview 생성 실패 (operator가 FINISHED를 반환하지 않음)")
            return

        props = bpy.context.scene.arp_convert_props
        _result(
            True,
            {
                "source_armature": props.source_armature,
                "preview_armature": props.preview_armature,
                "confidence": round(props.confidence, 4),
                "is_analyzed": props.is_analyzed,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 3. mcp_build_rig — ARP Build Rig
# ═══════════════════════════════════════════════════════════════


def mcp_build_rig():
    """ARP Build Rig를 실행하고 결과를 반환."""
    try:
        _reload()
        from arp_utils import ensure_object_mode, find_arp_armature, get_3d_viewport_context

        ensure_object_mode()
        ctx = get_3d_viewport_context()
        if ctx is None:
            _result(False, error="3D Viewport를 찾을 수 없습니다.")
            return

        with bpy.context.temp_override(**ctx):
            result = bpy.ops.arp_convert.build_rig()

        if "FINISHED" not in result:
            _result(False, error="BuildRig 실패 (operator가 FINISHED를 반환하지 않음)")
            return

        arp_obj = find_arp_armature()
        data = {"build_rig": True}
        if arp_obj:
            data["arp_armature"] = arp_obj.name
            data["arp_bone_count"] = len(arp_obj.data.bones)

        _result(True, data)
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 4. mcp_run_regression — 회귀 테스트 실행
# ═══════════════════════════════════════════════════════════════


def mcp_run_regression(fixture_path):
    """Fixture JSON 기반 회귀 테스트: Preview → 역할 적용 → BuildRig."""
    try:
        _reload()
        from arp_utils import ensure_object_mode, get_3d_viewport_context

        ensure_object_mode()
        ctx = get_3d_viewport_context()
        if ctx is None:
            _result(False, error="3D Viewport를 찾을 수 없습니다.")
            return

        props = bpy.context.scene.arp_convert_props
        props.regression_fixture = fixture_path

        with bpy.context.temp_override(**ctx):
            result = bpy.ops.arp_convert.run_regression()

        if "FINISHED" not in result:
            _result(False, error="회귀 테스트 실패")
            return

        # 가장 최근 리포트 파일 읽기
        report_dir = None
        report_dir_prop = props.regression_report_dir.strip()
        if report_dir_prop and os.path.isdir(report_dir_prop):
            report_dir = report_dir_prop

        if report_dir is None:
            from arp_utils import resolve_project_root

            project_root = resolve_project_root()
            report_dir = os.path.join(project_root, "regression_reports")

        report_data = None
        if os.path.isdir(report_dir):
            reports = sorted(
                [f for f in os.listdir(report_dir) if f.endswith(".json")],
                reverse=True,
            )
            if reports:
                report_path = os.path.join(report_dir, reports[0])
                with open(report_path, encoding="utf-8") as f:
                    report_data = json.load(f)

        _result(
            True,
            {
                "regression_passed": True,
                "report": report_data,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 5. mcp_get_bone_roles — 본 역할 매핑 조회
# ═══════════════════════════════════════════════════════════════


def mcp_get_bone_roles():
    """Preview Armature의 모든 본 역할 매핑을 JSON으로 반환."""
    try:
        props = bpy.context.scene.arp_convert_props
        preview_name = props.preview_armature
        if not preview_name:
            _result(False, error="Preview Armature가 없습니다. 먼저 create_preview를 실행하세요.")
            return

        preview_obj = bpy.data.objects.get(preview_name)
        if preview_obj is None:
            _result(False, error=f"Preview '{preview_name}' 오브젝트를 찾을 수 없습니다.")
            return

        roles = {}
        unmapped = []
        for bone in preview_obj.data.bones:
            role = bone.get("arp_role", "")
            if role:
                roles[bone.name] = role
            else:
                unmapped.append(bone.name)

        _result(
            True,
            {
                "preview_armature": preview_name,
                "roles": roles,
                "unmapped_bones": unmapped,
                "total_bones": len(preview_obj.data.bones),
                "mapped_count": len(roles),
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 6. mcp_set_bone_role — 개별 본 역할 변경
# ═══════════════════════════════════════════════════════════════


def mcp_set_bone_role(bone_name, role):
    """Preview Armature의 특정 본 역할을 변경.

    Args:
        bone_name: 본 이름
        role: 새 역할 (빈 문자열이면 역할 제거)
    """
    try:
        props = bpy.context.scene.arp_convert_props
        preview_name = props.preview_armature
        if not preview_name:
            _result(False, error="Preview Armature가 없습니다.")
            return

        preview_obj = bpy.data.objects.get(preview_name)
        if preview_obj is None:
            _result(False, error=f"Preview '{preview_name}'를 찾을 수 없습니다.")
            return

        bone = preview_obj.data.bones.get(bone_name)
        if bone is None:
            _result(False, error=f"본 '{bone_name}'을 찾을 수 없습니다.")
            return

        old_role = bone.get("arp_role", "")
        if role:
            bone["arp_role"] = role
        elif "arp_role" in bone:
            del bone["arp_role"]

        _result(
            True,
            {
                "bone": bone_name,
                "old_role": old_role,
                "new_role": role,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 7. mcp_validate_weights — 웨이트 커버리지 검증
# ═══════════════════════════════════════════════════════════════


def mcp_validate_weights():
    """ARP 리그에 바인딩된 메시의 웨이트 커버리지를 검증."""
    try:
        _reload()
        from arp_utils import find_arp_armature, find_mesh_objects

        arp_obj = find_arp_armature()
        if arp_obj is None:
            _result(False, error="ARP 아마추어를 찾을 수 없습니다.")
            return

        meshes = find_mesh_objects(arp_obj)
        if not meshes:
            _result(False, error=f"'{arp_obj.name}'에 바인딩된 메시가 없습니다.")
            return

        results = []
        for mesh_obj in meshes:
            vgroup_info = []
            total_verts = len(mesh_obj.data.vertices)

            for vg in mesh_obj.vertex_groups:
                vg_idx = vg.index
                weighted_count = 0
                for vert in mesh_obj.data.vertices:
                    for g in vert.groups:
                        if g.group == vg_idx and g.weight > 0.001:
                            weighted_count += 1
                            break

                vgroup_info.append(
                    {
                        "name": vg.name,
                        "weighted_verts": weighted_count,
                        "coverage": round(weighted_count / max(total_verts, 1), 4),
                    }
                )

            # 웨이트 없는 정점 체크
            unweighted = 0
            for vert in mesh_obj.data.vertices:
                has_weight = False
                for g in vert.groups:
                    if g.weight > 0.001:
                        has_weight = True
                        break
                if not has_weight:
                    unweighted += 1

            results.append(
                {
                    "mesh": mesh_obj.name,
                    "total_verts": total_verts,
                    "unweighted_verts": unweighted,
                    "vertex_groups": sorted(vgroup_info, key=lambda x: x["coverage"]),
                }
            )

        _result(
            True,
            {
                "arp_armature": arp_obj.name,
                "meshes": results,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 8. mcp_bake_animation — F12 애니메이션 베이크
# ═══════════════════════════════════════════════════════════════


def mcp_bake_animation():
    """소스 아마추어의 모든 액션을 ARP 컨트롤러에 베이크."""
    try:
        _reload()
        from arp_utils import (
            BAKE_PAIRS_KEY,
            bake_all_actions,
            deserialize_bone_pairs,
            ensure_object_mode,
            find_arp_armature,
            find_source_armature,
        )

        ensure_object_mode()
        source_obj = find_source_armature()
        if source_obj is None:
            _result(False, error="소스 아마추어를 찾을 수 없습니다.")
            return

        arp_obj = find_arp_armature()
        if arp_obj is None:
            _result(False, error="ARP 아마추어를 찾을 수 없습니다.")
            return

        # bone_pairs는 BuildRig 후 ARP 아마추어에 저장됨
        pairs_json = arp_obj.get(BAKE_PAIRS_KEY, "")
        if not pairs_json:
            _result(
                False,
                error=f"'{arp_obj.name}'에 bone_pairs 데이터가 없습니다. BuildRig를 먼저 실행하세요.",
            )
            return

        bone_pairs = deserialize_bone_pairs(pairs_json)
        created = bake_all_actions(source_obj, arp_obj, bone_pairs)

        _result(
            True,
            {
                "source_armature": source_obj.name,
                "arp_armature": arp_obj.name,
                "total_pairs": len(bone_pairs),
                "created_actions": created,
                "created_count": len(created),
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 9. mcp_inspect_bone_pairs — bone_pairs 조회
# ═══════════════════════════════════════════════════════════════


def mcp_inspect_bone_pairs(role_filter=None):
    """ARP 리그의 arpconv_bone_pairs를 디코드하고 역할 정보를 첨부해 반환.

    Args:
        role_filter: None | str | list — 역할 필터 (mcp_verify.filter_pairs_by_role 참조).

    사용 예: F12 bake 이후 특정 역할(예: back_leg_l)이 어느 컨트롤러에 매핑됐는지 확인.
    """
    try:
        _reload()
        from arp_utils import BAKE_PAIRS_KEY, deserialize_bone_pairs, find_arp_armature
        from mcp_verify import filter_pairs_by_role
        from skeleton_analyzer import discover_arp_ctrl_map

        arp_obj = find_arp_armature()
        if arp_obj is None:
            _result(False, error="ARP 아마추어를 찾을 수 없습니다.")
            return

        pairs_json = arp_obj.get(BAKE_PAIRS_KEY, "")
        if not pairs_json:
            _result(
                False,
                error=f"'{arp_obj.name}'에 bone_pairs 데이터가 없습니다. BuildRig를 먼저 실행하세요.",
            )
            return

        bone_pairs = deserialize_bone_pairs(pairs_json)

        # discover_arp_ctrl_map: {role: [ctrl_names...]} → target_to_role 구성
        ctrl_map = discover_arp_ctrl_map(arp_obj)
        target_to_role = {}
        for role, ctrls in ctrl_map.items():
            for c in ctrls:
                target_to_role[c] = role

        filtered = filter_pairs_by_role(bone_pairs, target_to_role, role_filter)

        _result(
            True,
            {
                "arp_armature": arp_obj.name,
                "total_pairs": len(bone_pairs),
                "filtered_count": len(filtered),
                "role_filter": role_filter,
                "pairs": filtered,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 10. mcp_compare_frames — 프레임별 월드 위치 비교
# ═══════════════════════════════════════════════════════════════


def mcp_compare_frames(pairs, frames, action_name=None):
    """소스와 ARP 본의 월드 위치를 지정 프레임에서 비교.

    Args:
        pairs: [(src_bone_name, arp_bone_name), ...] — 비교할 본 쌍.
        frames: [int, ...] — 샘플 프레임 리스트.
        action_name: None이면 현재 액션 유지. 문자열이면 소스에 '<name>',
                     ARP에 '<name>_arp'를 자동 할당.

    사용 예: F12 Task 6에서 walk 액션 8프레임 샘플로 leg 오차 0.186m → 0.00000m 검증.
    """
    try:
        _reload()
        from arp_utils import find_arp_armature, find_source_armature
        from mcp_verify import compute_position_stats, format_comparison_report

        src_obj = find_source_armature()
        arp_obj = find_arp_armature()
        if src_obj is None:
            _result(False, error="소스 아마추어를 찾을 수 없습니다.")
            return
        if arp_obj is None:
            _result(False, error="ARP 아마추어를 찾을 수 없습니다.")
            return

        # 액션 세팅 (옵션)
        if action_name:
            src_action = bpy.data.actions.get(action_name)
            arp_action = bpy.data.actions.get(f"{action_name}_arp")
            if src_action is None or arp_action is None:
                _result(
                    False,
                    error=f"액션 '{action_name}' 또는 '{action_name}_arp'를 찾을 수 없습니다.",
                )
                return
            if src_obj.animation_data is None:
                src_obj.animation_data_create()
            if arp_obj.animation_data is None:
                arp_obj.animation_data_create()
            src_obj.animation_data.action = src_action
            arp_obj.animation_data.action = arp_action

        pair_results = []
        all_distances = []
        for src_name, arp_name in pairs:
            src_pb = src_obj.pose.bones.get(src_name)
            arp_pb = arp_obj.pose.bones.get(arp_name)
            if src_pb is None or arp_pb is None:
                pair_results.append(
                    {
                        "src": src_name,
                        "arp": arp_name,
                        "error": "bone not found",
                        "max_err": 0.0,
                        "mean_err": 0.0,
                        "per_frame": [],
                    }
                )
                continue

            per_frame = []
            for f in frames:
                bpy.context.scene.frame_set(f)
                s_pos = src_obj.matrix_world @ src_obj.pose.bones[src_name].head
                a_pos = arp_obj.matrix_world @ arp_obj.pose.bones[arp_name].head
                d = (a_pos - s_pos).length
                per_frame.append(d)
                all_distances.append(d)

            stats = compute_position_stats(per_frame)
            pair_results.append(
                {
                    "src": src_name,
                    "arp": arp_name,
                    "max_err": stats["max"],
                    "mean_err": stats["mean"],
                    "per_frame": per_frame,
                }
            )

        overall = compute_position_stats(all_distances)
        report = format_comparison_report(pair_results)

        current_action_name = None
        if src_obj.animation_data and src_obj.animation_data.action:
            current_action_name = src_obj.animation_data.action.name

        _result(
            True,
            {
                "action": action_name or current_action_name,
                "frame_count": len(frames),
                "pair_count": len(pairs),
                "results": pair_results,
                "overall_max_err": overall["max"],
                "overall_mean_err": overall["mean"],
                "report": report,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")

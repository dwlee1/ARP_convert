"""
blender-mcp 브릿지 모듈 — Claude Code → Blender 자동화 JSON API
================================================================
Entrypoints (모두 JSON stdout 출력):
  mcp_scene_summary()                       — 씬 요약
  mcp_create_preview()                      — Preview 생성
  mcp_build_rig()                           — Build Rig 실행
  mcp_run_regression(fixture_path)          — 회귀 테스트 실행
  mcp_get_bone_roles()                      — 역할 매핑 조회
  mcp_set_bone_role(bone, role)             — 역할 변경
  mcp_validate_weights()                    — 웨이트 검증
  mcp_inspect_bone_pairs(role_filter=None)  — bone_pairs 디코드
  mcp_compare_frames(pairs, frames, ...)    — 소스-ARP 위치 비교
  mcp_agent_convert_current_file()          — 단일 파일 agent 변환 하네스
  mcp_inspect_preset_bones(preset, pattern) — ARP 프리셋 본 조회
  mcp_bake_animation()                      — F12 애니메이션 베이크 (= mcp_setup_retarget alias)
  mcp_reload_addon()                        — 애드온 재등록

Consumes: Blender scene state, arp_utils, skeleton_analyzer, mcp_verify
Produces: JSON via stdout (success/error + data)

상세 사용 레시피: docs/MCP_Recipes.md
"""

import json
import math
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

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
    """개발 중 모듈 리로드.

    주의: arp_utils는 reload 대상에서 제외한다. 이미 등록된 addon 모듈들이
    모듈 로드 시점에 `from arp_utils import log`로 함수 참조를 캡처하므로,
    arp_utils를 reload하면 `_LOG_LEVEL` 등 global 상태가 분리되어
    `quiet_logs()` 효과가 addon 내부까지 전파되지 않는다. arp_utils 자체
    수정 사항은 `mcp_reload_addon()`으로 전체 addon을 재등록해야 반영된다.
    """
    import importlib

    for mod_name in [
        "skeleton_detection",
        "skeleton_analyzer",
        "weight_transfer_rules",
        "mcp_verify",
        "agent_convert_contract",
    ]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])


# ═══════════════════════════════════════════════════════════════
# 0. Agent Convert Harness helpers
# ═══════════════════════════════════════════════════════════════


def _agent_emit(payload):
    """Print an agent harness payload without the legacy data/error wrapper."""
    print(json.dumps(payload, ensure_ascii=False, default=str))


def _agent_default_report_dir():
    repo_root = Path(_SCRIPT_DIR).parent
    return repo_root / "agent_reports"


def _agent_write_report(report_path, report):
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _agent_action_summary():
    actions = []
    for action in bpy.data.actions:
        frame_start, frame_end = action.frame_range
        actions.append(
            {
                "name": action.name,
                "frame_start": round(frame_start),
                "frame_end": round(frame_end),
            }
        )
    return actions


def _agent_preflight():
    from arp_utils import (
        find_arp_armature,
        find_mesh_objects,
        find_source_armature,
        get_3d_viewport_context,
        quiet_logs,
    )

    props = getattr(bpy.context.scene, "arp_convert_props", None)
    if props is None:
        return {
            "success": False,
            "status": "failed",
            "problem": "ARP Convert addon properties are not registered.",
            "evidence": {"scene": bpy.context.scene.name},
        }

    with quiet_logs():
        source_obj = find_source_armature()
        arp_obj = find_arp_armature()
        viewport_context = get_3d_viewport_context()

    if source_obj is None:
        return {
            "success": False,
            "status": "blocked",
            "problem": "No source armature was found in the current scene.",
            "evidence": {"armature_count": len([o for o in bpy.data.objects if o.type == "ARMATURE"])},
            "recommended_fix": "Open a quadruped .blend containing one source armature, then rerun the harness.",
            "retry_from": "preflight",
        }

    if arp_obj is not None:
        return {
            "success": False,
            "status": "blocked",
            "problem": "An ARP armature already exists in the current scene.",
            "evidence": {"arp_armature": arp_obj.name},
            "recommended_fix": "Open an unconverted source file or clean the existing ARP rig before rerunning.",
            "retry_from": "preflight",
        }

    if viewport_context is None:
        return {
            "success": False,
            "status": "failed",
            "problem": "3D View context is unavailable for Blender operators.",
            "evidence": {"window_count": len(bpy.context.window_manager.windows)},
        }

    bound_meshes = find_mesh_objects(source_obj)
    warnings = []
    if not bound_meshes:
        warnings.append("No mesh is bound to the source armature; weight verification will be limited.")

    actions = _agent_action_summary()
    if not actions:
        warnings.append("No actions found; retarget will be skipped.")

    return {
        "success": True,
        "blend_file": bpy.data.filepath,
        "source_obj": source_obj,
        "source_armature": source_obj.name,
        "bound_meshes": [mesh.name for mesh in bound_meshes],
        "actions": actions,
        "warnings": warnings,
    }


def _agent_create_preview(confidence_threshold, report, report_path, verbosity):
    import agent_convert_contract as acc
    from arp_utils import ensure_object_mode, get_3d_viewport_context, quiet_logs

    with quiet_logs():
        ensure_object_mode()
        ctx = get_3d_viewport_context()
        if ctx is None:
            return acc.failed(
                "preview",
                "3D View context is unavailable for Create Preview.",
                {},
                report_path,
            )
        with bpy.context.temp_override(**ctx):
            result = bpy.ops.arp_convert.create_preview()

    if "FINISHED" not in result:
        return acc.failed(
            "preview",
            "Create Preview operator did not finish.",
            {"operator_result": list(result)},
            report_path,
        )

    props = bpy.context.scene.arp_convert_props
    confidence = float(getattr(props, "confidence", 0.0) or 0.0)
    preview_data = {
        "source_armature": props.source_armature,
        "preview_armature": props.preview_armature,
        "confidence": round(confidence, 4),
        "is_analyzed": bool(props.is_analyzed),
    }
    report["steps"].append({"stage": "preview", "data": preview_data})

    if confidence < confidence_threshold:
        roles_payload = _agent_collect_roles_payload()
        report["diagnostic"] = {
            "stage": "preview_roles",
            **acc.compact_payload(roles_payload, verbosity=verbosity),
        }
        _agent_write_report(report_path, report)
        return acc.blocked(
            "preview_roles",
            "Preview role confidence is below threshold.",
            {
                "confidence": round(confidence, 4),
                "threshold": confidence_threshold,
                "unmapped_count": len(roles_payload.get("unmapped_bones", [])),
            },
            "Open ARP Convert > Source Hierarchy, fix role assignments, then rerun the harness.",
            "preview_roles",
            report_path,
        )

    return {"success": True, "data": preview_data}


def _agent_collect_roles_payload():
    from skeleton_analyzer import read_preview_roles

    props = bpy.context.scene.arp_convert_props
    preview_obj = bpy.data.objects.get(props.preview_armature)
    if preview_obj is None:
        return {"roles": {}, "unmapped_bones": []}

    roles = read_preview_roles(preview_obj)
    return {"roles": roles, "unmapped_bones": list(roles.get("unmapped", []))}


def _agent_build_rig(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import ensure_object_mode, find_arp_armature, get_3d_viewport_context, quiet_logs

    with quiet_logs():
        ensure_object_mode()
        ctx = get_3d_viewport_context()
        if ctx is None:
            return acc.failed(
                "build_rig",
                "3D View context is unavailable for Build Rig.",
                {},
                report_path,
            )
        with bpy.context.temp_override(**ctx):
            result = bpy.ops.arp_convert.build_rig()

    if "FINISHED" not in result:
        return acc.failed(
            "build_rig",
            "Build Rig operator did not finish.",
            {"operator_result": list(result)},
            report_path,
        )

    arp_obj = find_arp_armature()
    if arp_obj is None:
        return acc.failed(
            "build_rig",
            "Build Rig finished but no ARP armature was found.",
            {"operator_result": list(result)},
            report_path,
        )

    c_bone_count = len([bone for bone in arp_obj.data.bones if bone.name.startswith("c_")])
    data = {
        "arp_armature": arp_obj.name,
        "bone_count": len(arp_obj.data.bones),
        "c_bone_count": c_bone_count,
    }
    report["steps"].append({"stage": "build_rig", "data": data})
    return {"success": True, "arp_obj": arp_obj, "data": data}


def _agent_validate_weights(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import find_arp_armature, find_mesh_objects, quiet_logs

    with quiet_logs():
        arp_obj = find_arp_armature()
        meshes = find_mesh_objects(arp_obj) if arp_obj else []

    if arp_obj is None:
        return acc.failed("weights", "ARP armature was not found.", {}, report_path)

    mesh_results = []
    total_unweighted = 0
    for mesh_obj in meshes:
        unweighted = 0
        for vert in mesh_obj.data.vertices:
            if not any(group.weight > 0.001 for group in vert.groups):
                unweighted += 1
        total_unweighted += unweighted
        mesh_results.append(
            {
                "mesh": mesh_obj.name,
                "total_verts": len(mesh_obj.data.vertices),
                "unweighted_verts": unweighted,
                "total_groups": len(mesh_obj.vertex_groups),
            }
        )

    data = {
        "arp_armature": arp_obj.name,
        "meshes": mesh_results,
        "unweighted_vertices": total_unweighted,
    }
    report["steps"].append({"stage": "weights", "data": data})

    if meshes and total_unweighted > 0:
        _agent_write_report(report_path, report)
        return acc.blocked(
            "weights",
            "One or more bound meshes contain unweighted vertices.",
            data,
            "Inspect the listed meshes in Weight Paint and assign weights before rerunning.",
            "weights",
            report_path,
        )

    return {"success": True, "data": data}


def _agent_inspect_pairs(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import BAKE_PAIRS_KEY, deserialize_bone_pairs, find_arp_armature, quiet_logs
    from mcp_verify import filter_pairs_by_role
    from skeleton_analyzer import discover_arp_ctrl_map

    with quiet_logs():
        arp_obj = find_arp_armature()

    if arp_obj is None:
        return acc.failed("bone_pairs", "ARP armature was not found.", {}, report_path)

    pairs_json = arp_obj.get(BAKE_PAIRS_KEY, "")
    if not pairs_json:
        return acc.failed(
            "bone_pairs",
            "ARP armature has no arpconv_bone_pairs data.",
            {"arp_armature": arp_obj.name},
            report_path,
        )

    bone_pairs = deserialize_bone_pairs(pairs_json)
    ctrl_map = discover_arp_ctrl_map(arp_obj)
    target_to_role = {ctrl: role for role, ctrls in ctrl_map.items() for ctrl in ctrls}
    filtered = filter_pairs_by_role(bone_pairs, target_to_role)
    validation = acc.validate_required_roles(filtered)
    data = {"total_pairs": len(bone_pairs), "pairs": filtered, **validation}
    report["steps"].append({"stage": "bone_pairs", "data": acc.compact_payload(data)})

    if not validation["ok"]:
        report["diagnostic"] = {"stage": "bone_pairs", "pairs": filtered}
        _agent_write_report(report_path, report)
        return acc.blocked(
            "bone_pairs",
            "Core role mappings are missing from bone_pairs.",
            {"missing_roles": validation["missing_roles"], "total_pairs": len(bone_pairs)},
            "Fix Preview role assignments for the missing roles and rerun Build Rig.",
            "preview_roles",
            report_path,
        )

    return {"success": True, "data": data}


def _agent_setup_retarget(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import (
        BAKE_PAIRS_KEY,
        deserialize_bone_pairs,
        find_arp_armature,
        find_source_armature,
        preflight_check_transforms,
        quiet_logs,
        setup_arp_retarget,
    )

    try:
        with quiet_logs():
            source_obj = find_source_armature()
            arp_obj = find_arp_armature()
    except Exception as e:
        return acc.failed(
            "setup_retarget",
            "Retarget setup preflight failed.",
            {"error": str(e), "traceback": traceback.format_exc()},
            report_path,
        )

    if source_obj is None:
        return acc.failed("setup_retarget", "Source armature was not found.", {}, report_path)
    if arp_obj is None:
        return acc.failed("setup_retarget", "ARP armature was not found.", {}, report_path)

    pairs_json = arp_obj.get(BAKE_PAIRS_KEY, "")
    if not pairs_json:
        return acc.failed(
            "setup_retarget",
            "ARP armature has no arpconv_bone_pairs data.",
            {"arp_armature": arp_obj.name},
            report_path,
        )

    bone_pairs = deserialize_bone_pairs(pairs_json)
    error = preflight_check_transforms(source_obj, arp_obj)
    if error:
        return acc.failed(
            "setup_retarget",
            "Retarget transform preflight failed.",
            {"error": error},
            report_path,
        )

    try:
        with quiet_logs():
            result = setup_arp_retarget(source_obj, arp_obj, bone_pairs)
    except Exception as e:
        return acc.failed(
            "setup_retarget",
            "setup_arp_retarget raised an exception.",
            {"error": str(e), "traceback": traceback.format_exc()},
            report_path,
        )

    data = {
        "source_armature": source_obj.name,
        "arp_armature": arp_obj.name,
        "total_pairs": len(bone_pairs),
        **result,
    }
    report["steps"].append({"stage": "setup_retarget", "data": data})
    return {"success": True, "data": data}


def _agent_run_arp_retarget(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import find_arp_armature, quiet_logs, run_arp_operator, select_only

    before_actions = {action.name for action in bpy.data.actions}
    try:
        with quiet_logs():
            arp_obj = find_arp_armature()
            if arp_obj is None:
                return acc.failed("arp_retarget", "ARP armature was not found.", {}, report_path)
            select_only(arp_obj)
            result = run_arp_operator(bpy.ops.arp.retarget)
    except Exception as e:
        return acc.failed(
            "arp_retarget",
            "ARP retarget operator raised an exception.",
            {"error": str(e), "traceback": traceback.format_exc()},
            report_path,
        )

    if "FINISHED" not in result:
        return acc.failed(
            "arp_retarget",
            "ARP retarget operator did not finish.",
            {"operator_result": list(result)},
            report_path,
        )

    remap_actions = sorted(
        action.name
        for action in bpy.data.actions
        if action.name not in before_actions
        and (action.name.endswith("_remap") or "_remap." in action.name)
    )
    data = {"operator_result": list(result), "remap_actions": remap_actions}
    report["steps"].append({"stage": "arp_retarget", "data": data})

    if not remap_actions:
        _agent_write_report(report_path, report)
        return acc.blocked(
            "arp_retarget",
            "ARP retarget finished but no remap actions were created.",
            data,
            "Run ARP Re-Retarget manually in the Remap panel, then rerun frame verification.",
            "arp_retarget",
            report_path,
        )

    return {"success": True, "data": data}


def _agent_cleanup(report):
    try:
        result = bpy.ops.arp_convert.cleanup()
    except Exception as e:
        warning = f"Cleanup raised an exception: {e}"
        report["warnings"].append(warning)
        return {"success": False, "warning": warning}

    data = {"operator_result": list(result)}
    report["steps"].append({"stage": "cleanup", "data": data})
    if "FINISHED" not in result:
        warning = f"Cleanup did not finish: {list(result)}"
        report["warnings"].append(warning)
        return {"success": False, "warning": warning}
    return {"success": True, "data": data}


def _agent_copy_custom_scale(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import _copy_custom_scale_fcurves, find_arp_armature, quiet_logs

    with quiet_logs():
        arp_obj = find_arp_armature()
    if arp_obj is None:
        return acc.failed("copy_custom_scale", "ARP armature was not found.", {}, report_path)

    try:
        copied = _copy_custom_scale_fcurves(arp_obj)
    except Exception as e:
        return acc.failed(
            "copy_custom_scale",
            "Custom scale copy raised an exception.",
            {"error": str(e), "traceback": traceback.format_exc()},
            report_path,
        )

    data = {"arp_armature": arp_obj.name, "copied_fcurves": copied}
    report["steps"].append({"stage": "copy_custom_scale", "data": data})
    return {"success": True, "data": data}


def _agent_verify_frames(report, report_path, pairs_data, actions):
    import agent_convert_contract as acc

    compare_pairs = acc.select_core_pairs(pairs_data.get("pairs", []), limit=8)
    if not compare_pairs:
        return acc.blocked(
            "frame_verify",
            "No core bone pairs are available for frame verification.",
            {"total_pairs": pairs_data.get("total_pairs", 0)},
            "Inspect bone_pairs and fix role assignments before rerunning retarget verification.",
            "preview_roles",
            report_path,
        )

    action = actions[0]
    frames = acc.sample_frames(action["frame_start"], action["frame_end"], count=5)
    try:
        compare_result = _agent_compare_frames_inline(
            compare_pairs, frames, action_name=action["name"], detailed=False
        )
    except Exception as e:
        return acc.failed(
            "frame_verify",
            "Frame verification could not run.",
            {"error": str(e), "traceback": traceback.format_exc()},
            report_path,
        )

    threshold = acc.evaluate_frame_thresholds(compare_result)
    data = {
        **compare_result,
        "frames": frames,
        "pass_rate": threshold["pass_rate"],
        "violations": threshold["violations"],
    }
    report["steps"].append({"stage": "frame_verify", "data": acc.compact_payload(data)})

    if not threshold["ok"]:
        try:
            detailed = _agent_compare_frames_inline(
                compare_pairs, frames, action_name=action["name"], detailed=True
            )
        except Exception:
            detailed = data
        report["diagnostic"] = {"stage": "frame_verify", **detailed}
        _agent_write_report(report_path, report)
        return acc.blocked(
            "frame_verify",
            "Frame verification exceeded allowed error thresholds.",
            {"violations": threshold["violations"], "action": action["name"], "frames": frames},
            "Inspect the frame verification offenders in the report before accepting the retarget.",
            "frame_verify",
            report_path,
        )

    return {"success": True, "data": data}


def _agent_compare_frames_inline(pairs, frames, action_name=None, detailed=False):
    from arp_utils import find_arp_armature, find_source_armature, quiet_logs
    from mcp_verify import (
        compute_position_stats,
        compute_rotation_stats,
        format_comparison_report,
        summarize_pair_results,
    )

    with quiet_logs():
        src_obj = find_source_armature()
        arp_obj = find_arp_armature()
    if src_obj is None:
        raise RuntimeError("소스 아마추어를 찾을 수 없습니다.")
    if arp_obj is None:
        raise RuntimeError("ARP 아마추어를 찾을 수 없습니다.")

    if action_name:
        src_action = bpy.data.actions.get(action_name)
        arp_action = (
            bpy.data.actions.get(f"{action_name}_remap")
            or bpy.data.actions.get(f"{action_name}_arp")
            or next(
                (
                    action
                    for action in bpy.data.actions
                    if action.name.startswith(f"{action_name}_remap.")
                ),
                None,
            )
        )
        if src_action is None or arp_action is None:
            raise RuntimeError(f"액션 '{action_name}' 또는 retarget 결과 액션을 찾을 수 없습니다.")
        if src_obj.animation_data is None:
            src_obj.animation_data_create()
        if arp_obj.animation_data is None:
            arp_obj.animation_data_create()
        src_obj.animation_data.action = src_action
        arp_obj.animation_data.action = arp_action

    pair_results = []
    all_distances = []
    all_rotation_errors = []
    for src_name, arp_name in pairs:
        src_pb = src_obj.pose.bones.get(src_name)
        arp_pb = arp_obj.pose.bones.get(arp_name)
        if src_pb is None or arp_pb is None:
            pair_results.append(
                {
                    "src": src_name,
                    "arp": arp_name,
                    "error": "bone not found",
                    "max_err": 1.0,
                    "mean_err": 1.0,
                    "rot_max_deg": 180.0,
                    "rot_mean_deg": 180.0,
                    "per_frame": [],
                    "per_frame_rot_deg": [],
                }
            )
            all_distances.append(1.0)
            all_rotation_errors.append(180.0)
            continue

        per_frame = []
        per_frame_rot_deg = []
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            src_matrix = src_obj.matrix_world @ src_pb.matrix
            arp_matrix = arp_obj.matrix_world @ arp_pb.matrix
            s_pos = src_obj.matrix_world @ src_pb.head
            a_pos = arp_obj.matrix_world @ arp_pb.head
            distance = (a_pos - s_pos).length
            rot_deg = src_matrix.to_quaternion().rotation_difference(
                arp_matrix.to_quaternion()
            ).angle
            rot_deg = math.degrees(rot_deg)
            per_frame.append(distance)
            per_frame_rot_deg.append(rot_deg)
            all_distances.append(distance)
            all_rotation_errors.append(rot_deg)

        pos_stats = compute_position_stats(per_frame)
        rot_stats = compute_rotation_stats(per_frame_rot_deg)
        pair_results.append(
            {
                "src": src_name,
                "arp": arp_name,
                "max_err": pos_stats["max"],
                "mean_err": pos_stats["mean"],
                "rot_max_deg": rot_stats["max"],
                "rot_mean_deg": rot_stats["mean"],
                "per_frame": per_frame,
                "per_frame_rot_deg": per_frame_rot_deg,
            }
        )

    overall = compute_position_stats(all_distances)
    overall_rot = compute_rotation_stats(all_rotation_errors)
    current_action_name = None
    if src_obj.animation_data and src_obj.animation_data.action:
        current_action_name = src_obj.animation_data.action.name

    data = {
        "action": action_name or current_action_name,
        "frame_count": len(frames),
        "pair_count": len(pairs),
        "overall_max_err": overall["max"],
        "overall_mean_err": overall["mean"],
        "overall_rot_max_deg": overall_rot["max"],
        "overall_rot_mean_deg": overall_rot["mean"],
    }
    if detailed:
        data["results"] = pair_results
        data["report"] = format_comparison_report(pair_results)
    else:
        summary = summarize_pair_results(pair_results)
        data["pass_count"] = summary["pass_count"]
        data["top_offenders"] = summary["top_offenders"]
    return data


def mcp_agent_convert_current_file(
    *,
    include_retarget=True,
    allow_cleanup=False,
    confidence_threshold=0.80,
    verbosity="summary",
    report_dir=None,
):
    """Run the current-scene agent conversion pipeline and print a standard JSON result."""
    try:
        _reload()
        import agent_convert_contract as acc

        blend_file = bpy.data.filepath or "untitled.blend"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = acc.build_report_path(
            blend_file=blend_file,
            report_dir=str(report_dir or _agent_default_report_dir()),
            timestamp=timestamp,
        )
        report = {
            "blend_file": blend_file,
            "parameters": {
                "include_retarget": include_retarget,
                "allow_cleanup": allow_cleanup,
                "confidence_threshold": confidence_threshold,
                "verbosity": verbosity,
            },
            "steps": [],
            "warnings": [],
        }

        preflight = _agent_preflight()
        if preflight.get("success") is not True:
            report["diagnostic"] = {"stage": "preflight", "evidence": preflight.get("evidence", {})}
            _agent_write_report(report_path, report)
            if preflight.get("status") == "blocked":
                _agent_emit(
                    acc.blocked(
                        "preflight",
                        preflight["problem"],
                        preflight.get("evidence", {}),
                        preflight["recommended_fix"],
                        preflight["retry_from"],
                        report_path,
                    )
                )
                return
            _agent_emit(
                acc.failed(
                    "preflight",
                    preflight["problem"],
                    preflight.get("evidence", {}),
                    report_path,
                )
            )
            return

        report["warnings"].extend(preflight["warnings"])
        report["steps"].append(
            {
                "stage": "preflight",
                "data": {
                    "source_armature": preflight["source_armature"],
                    "bound_meshes": preflight["bound_meshes"],
                    "actions": preflight["actions"],
                },
            }
        )

        preview_result = _agent_create_preview(
            confidence_threshold, report, report_path, verbosity
        )
        if preview_result.get("success") is not True:
            _agent_emit(preview_result)
            return

        build_result = _agent_build_rig(report, report_path)
        if build_result.get("success") is not True:
            _agent_write_report(report_path, report)
            _agent_emit(build_result)
            return

        weight_result = _agent_validate_weights(report, report_path)
        if weight_result.get("success") is not True:
            _agent_emit(weight_result)
            return

        pairs_result = _agent_inspect_pairs(report, report_path)
        if pairs_result.get("success") is not True:
            _agent_emit(pairs_result)
            return

        if not include_retarget or not preflight["actions"]:
            data = {
                "blend_file": blend_file,
                "source_armature": preflight["source_armature"],
                "arp_armature": build_result["data"]["arp_armature"],
                "preview_confidence": preview_result["data"]["confidence"],
                "steps_completed": [
                    "preflight",
                    "preview",
                    "build_rig",
                    "weights",
                    "bone_pairs",
                ],
                "warnings": report["warnings"],
                "summary": {
                    "bound_meshes": len(preflight["bound_meshes"]),
                    "actions": len(preflight["actions"]),
                    "bone_pairs": pairs_result["data"]["total_pairs"],
                    "unweighted_vertices": weight_result["data"]["unweighted_vertices"],
                },
                "report_path": report_path,
            }
            if include_retarget and not preflight["actions"]:
                data["warnings"].append("No actions found; retarget was skipped.")
                status = acc.partial("retarget_skipped", data)
            else:
                status = acc.complete("build_rig_complete", data)
            _agent_write_report(report_path, report)
            _agent_emit(status)
            return

        setup_result = _agent_setup_retarget(report, report_path)
        if setup_result.get("success") is not True:
            _agent_write_report(report_path, report)
            _agent_emit(setup_result)
            return

        retarget_result = _agent_run_arp_retarget(report, report_path)
        if retarget_result.get("success") is not True:
            _agent_write_report(report_path, report)
            _agent_emit(retarget_result)
            return

        scale_result = _agent_copy_custom_scale(report, report_path)
        if scale_result.get("success") is not True:
            _agent_write_report(report_path, report)
            _agent_emit(scale_result)
            return

        frame_result = _agent_verify_frames(
            report, report_path, pairs_result["data"], preflight["actions"]
        )
        if frame_result.get("success") is not True:
            _agent_emit(frame_result)
            return

        if allow_cleanup:
            _agent_cleanup(report)

        data = {
            "blend_file": blend_file,
            "source_armature": preflight["source_armature"],
            "arp_armature": build_result["data"]["arp_armature"],
            "preview_confidence": preview_result["data"]["confidence"],
            "steps_completed": [
                "preflight",
                "preview",
                "build_rig",
                "weights",
                "bone_pairs",
                "setup_retarget",
                "arp_retarget",
                "copy_custom_scale",
                "frame_verify",
            ],
            "warnings": report["warnings"],
            "summary": {
                "bound_meshes": len(preflight["bound_meshes"]),
                "actions": len(preflight["actions"]),
                "bone_pairs": pairs_result["data"]["total_pairs"],
                "unweighted_vertices": weight_result["data"]["unweighted_vertices"],
                "remap_actions": len(retarget_result["data"]["remap_actions"]),
                "copied_scale_fcurves": scale_result["data"]["copied_fcurves"],
                "frame_verify_pass_rate": frame_result["data"]["pass_rate"],
                "max_position_error_mm": frame_result["data"]["overall_max_err"] * 1000,
                "max_rotation_error_deg": frame_result["data"]["overall_rot_max_deg"],
            },
            "report_path": report_path,
        }
        _agent_write_report(report_path, report)
        _agent_emit(acc.complete("complete", data))
    except Exception as e:
        _agent_emit(
            {
                "success": False,
                "status": "failed",
                "stage": "agent_exception",
                "error": {
                    "problem": str(e),
                    "evidence": {"traceback": traceback.format_exc()},
                },
            }
        )


# ═══════════════════════════════════════════════════════════════
# 1. mcp_scene_summary — 씬 요약
# ═══════════════════════════════════════════════════════════════


def mcp_scene_summary(brief=False):
    """현재 씬의 아마추어, 메시, 액션 요약을 JSON으로 출력.

    Args:
        brief: True면 개수만 반환 (이름/상세 리스트 생략).
    """
    try:
        armatures = []
        source_count = 0
        arp_count = 0
        for obj in bpy.data.objects:
            if obj.type == "ARMATURE":
                bone_count = len(obj.data.bones)
                c_bones = len([b for b in obj.data.bones if b.name.startswith("c_")])
                is_arp = c_bones > 5
                if is_arp:
                    arp_count += 1
                else:
                    source_count += 1
                armatures.append(
                    {
                        "name": obj.name,
                        "bone_count": bone_count,
                        "c_bone_count": c_bones,
                        "is_arp": is_arp,
                    }
                )

        bound_mesh_count = 0
        meshes = []
        for obj in bpy.data.objects:
            if obj.type == "MESH":
                arm_mod = None
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE" and mod.object:
                        arm_mod = mod.object.name
                        break
                if arm_mod:
                    bound_mesh_count += 1
                meshes.append(
                    {
                        "name": obj.name,
                        "vertex_count": len(obj.data.vertices),
                        "bound_armature": arm_mod,
                    }
                )

        action_count = len(bpy.data.actions)
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

        if brief:
            _result(
                True,
                {
                    "blend_file": bpy.data.filepath or "(unsaved)",
                    "source_armatures": source_count,
                    "arp_rigs": arp_count,
                    "bound_meshes": bound_mesh_count,
                    "actions": action_count,
                },
            )
        else:
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
        from arp_utils import ensure_object_mode, get_3d_viewport_context, quiet_logs

        with quiet_logs():
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
            data = {
                "source_armature": props.source_armature,
                "preview_armature": props.preview_armature,
                "confidence": round(props.confidence, 4),
                "is_analyzed": props.is_analyzed,
            }

        _result(True, data)
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 3. mcp_build_rig — ARP Build Rig
# ═══════════════════════════════════════════════════════════════


def mcp_build_rig():
    """ARP Build Rig를 실행하고 결과를 반환."""
    try:
        _reload()
        from arp_utils import (
            ensure_object_mode,
            find_arp_armature,
            get_3d_viewport_context,
            quiet_logs,
        )

        with quiet_logs():
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
        from arp_utils import ensure_object_mode, get_3d_viewport_context, quiet_logs

        with quiet_logs():
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


def mcp_get_bone_roles(compact=False):
    """Preview Armature의 모든 본 역할 매핑을 JSON으로 반환.

    Args:
        compact: True면 역할별 개수만 반환 (본 이름 리스트 생략).
    """
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
        for pbone in preview_obj.pose.bones:
            role = pbone.get("arp_role", "")
            if role and role != "unmapped":
                roles[pbone.name] = role
            else:
                unmapped.append(pbone.name)

        if compact:
            from collections import Counter

            role_counts = dict(Counter(roles.values()))
            _result(
                True,
                {
                    "preview_armature": preview_name,
                    "role_counts": role_counts,
                    "unmapped_count": len(unmapped),
                    "total_bones": len(preview_obj.data.bones),
                    "mapped_count": len(roles),
                },
            )
        else:
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


def mcp_validate_weights(summary=False):
    """ARP 리그에 바인딩된 메시의 웨이트 커버리지를 검증.

    Args:
        summary: True면 메시별 요약만 반환 (vertex group 상세 생략).
    """
    try:
        _reload()
        from arp_utils import find_arp_armature, find_mesh_objects, quiet_logs

        with quiet_logs():
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
            total_verts = len(mesh_obj.data.vertices)

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

            if summary:
                results.append(
                    {
                        "mesh": mesh_obj.name,
                        "total_verts": total_verts,
                        "unweighted_verts": unweighted,
                        "total_groups": len(mesh_obj.vertex_groups),
                    }
                )
            else:
                vgroup_info = []
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


def mcp_setup_retarget():
    """bone_pairs → ARP bones_map_v2 변환 및 리타겟 씬 설정."""
    try:
        _reload()
        from arp_utils import (
            BAKE_PAIRS_KEY,
            deserialize_bone_pairs,
            ensure_object_mode,
            find_arp_armature,
            find_source_armature,
            preflight_check_transforms,
            quiet_logs,
            setup_arp_retarget,
        )

        with quiet_logs():
            ensure_object_mode()
            source_obj = find_source_armature()
            if source_obj is None:
                _result(False, error="소스 아마추어를 찾을 수 없습니다.")
                return

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

            error = preflight_check_transforms(source_obj, arp_obj)
            if error:
                _result(False, error=f"Preflight 실패: {error}")
                return

            bone_pairs = deserialize_bone_pairs(pairs_json)
            result = setup_arp_retarget(source_obj, arp_obj, bone_pairs)

        _result(
            True,
            {
                "source_armature": source_obj.name,
                "arp_armature": arp_obj.name,
                "total_pairs": len(bone_pairs),
                **result,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# 하위 호환 alias
mcp_bake_animation = mcp_setup_retarget


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
        from arp_utils import (
            BAKE_PAIRS_KEY,
            deserialize_bone_pairs,
            find_arp_armature,
            quiet_logs,
        )
        from mcp_verify import filter_pairs_by_role
        from skeleton_analyzer import discover_arp_ctrl_map

        with quiet_logs():
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


def mcp_compare_frames(pairs, frames, action_name=None, detailed=False):
    """소스와 ARP 본의 월드 위치/회전을 지정 프레임에서 비교.

    Args:
        pairs: [(src_bone_name, arp_bone_name), ...] — 비교할 본 쌍.
        frames: [int, ...] — 샘플 프레임 리스트.
        action_name: None이면 현재 액션 유지. 문자열이면 소스에 '<name>',
                     ARP에 '<name>_arp'를 자동 할당.
        detailed: False(기본)면 per_frame 배열과 report 문자열을 빈 값으로
                  돌려 토큰을 줄인다. True면 전체 데이터 반환.

    사용 예: F12 Task 6에서 walk 액션 8프레임 샘플로 leg 오차 0.186m → 0.00000m 검증.
    """
    try:
        _reload()
        from arp_utils import find_arp_armature, find_source_armature, quiet_logs
        from mcp_verify import (
            compute_position_stats,
            compute_rotation_stats,
            format_comparison_report,
            summarize_pair_results,
        )

        with quiet_logs():
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
        all_rotation_errors = []
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
                        "rot_max_deg": 0.0,
                        "rot_mean_deg": 0.0,
                        "per_frame": [],
                        "per_frame_rot_deg": [],
                    }
                )
                continue

            per_frame = []
            per_frame_rot_deg = []
            for f in frames:
                bpy.context.scene.frame_set(f)
                bpy.context.view_layer.update()
                src_matrix = src_obj.matrix_world @ src_obj.pose.bones[src_name].matrix
                arp_matrix = arp_obj.matrix_world @ arp_obj.pose.bones[arp_name].matrix
                s_pos = src_obj.matrix_world @ src_obj.pose.bones[src_name].head
                a_pos = arp_obj.matrix_world @ arp_obj.pose.bones[arp_name].head
                d = (a_pos - s_pos).length
                rot_deg = (
                    src_matrix.to_quaternion().rotation_difference(arp_matrix.to_quaternion()).angle
                )
                rot_deg = math.degrees(rot_deg)
                per_frame.append(d)
                per_frame_rot_deg.append(rot_deg)
                all_distances.append(d)
                all_rotation_errors.append(rot_deg)

            pos_stats = compute_position_stats(per_frame)
            rot_stats = compute_rotation_stats(per_frame_rot_deg)
            pair_results.append(
                {
                    "src": src_name,
                    "arp": arp_name,
                    "max_err": pos_stats["max"],
                    "mean_err": pos_stats["mean"],
                    "rot_max_deg": rot_stats["max"],
                    "rot_mean_deg": rot_stats["mean"],
                    "per_frame": per_frame,
                    "per_frame_rot_deg": per_frame_rot_deg,
                }
            )

        overall = compute_position_stats(all_distances)
        overall_rot = compute_rotation_stats(all_rotation_errors)

        current_action_name = None
        if src_obj.animation_data and src_obj.animation_data.action:
            current_action_name = src_obj.animation_data.action.name

        if detailed:
            report = format_comparison_report(pair_results)
            _result(
                True,
                {
                    "action": action_name or current_action_name,
                    "frame_count": len(frames),
                    "pair_count": len(pairs),
                    "results": pair_results,
                    "overall_max_err": overall["max"],
                    "overall_mean_err": overall["mean"],
                    "overall_rot_max_deg": overall_rot["max"],
                    "overall_rot_mean_deg": overall_rot["mean"],
                    "report": report,
                },
            )
        else:
            summary = summarize_pair_results(pair_results)
            _result(
                True,
                {
                    "action": action_name or current_action_name,
                    "frame_count": len(frames),
                    "pair_count": len(pairs),
                    "pass_count": summary["pass_count"],
                    "overall_max_err": overall["max"],
                    "overall_mean_err": overall["mean"],
                    "overall_rot_max_deg": overall_rot["max"],
                    "overall_rot_mean_deg": overall_rot["mean"],
                    "top_offenders": summary["top_offenders"],
                },
            )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 11. mcp_inspect_preset_bones — ARP 프리셋 본 이름 조회
# ═══════════════════════════════════════════════════════════════


def mcp_inspect_preset_bones(preset="dog", pattern=None):
    """ARP 애드온의 armature_presets/<preset>.blend를 libraries.load로 읽고 본 이름을 반환.

    Args:
        preset: 프리셋 이름 (기본 'dog').
        pattern: 정규식 문자열. None이면 전체 반환.

    사용 예: F12에서 c_toes vs c_toes_fk 확정, c_thigh_b.l 실존 확인.

    Note: _append_arp는 MCP 컨텍스트에서 'overlay' 에러를 일으키므로
    libraries.load로 직접 armature data를 읽는다. 임시 데이터는 함수 종료 시 cleanup.
    """
    try:
        _reload()
        from mcp_verify import match_bone_names

        # ARP 애드온 경로 탐색
        try:
            from bl_ext.user_default.auto_rig_pro.src import auto_rig
        except ImportError as ie:
            _result(False, error=f"Auto-Rig Pro 애드온을 찾을 수 없습니다: {ie}")
            return

        src_dir = os.path.dirname(os.path.abspath(auto_rig.__file__))
        addon_dir = os.path.dirname(src_dir)
        preset_path = os.path.join(addon_dir, "armature_presets", f"{preset}.blend")
        if not os.path.exists(preset_path):
            _result(False, error=f"프리셋 파일 없음: {preset_path}")
            return

        # libraries.load로 armature data만 로드
        with bpy.data.libraries.load(preset_path, link=False) as (data_from, data_to):
            data_to.armatures = list(data_from.armatures)

        loaded_armatures = list(data_to.armatures)
        if not loaded_armatures:
            _result(False, error=f"프리셋 '{preset}'에 armature 데이터가 없습니다.")
            return

        arm_data = loaded_armatures[0]
        bone_names = [b.name for b in arm_data.bones]
        matched = match_bone_names(bone_names, pattern)

        # Cleanup: 로드된 armature data를 제거해 고아 데이터 방지
        for ad in loaded_armatures:
            try:
                bpy.data.armatures.remove(ad)
            except Exception:
                pass

        _result(
            True,
            {
                "preset": preset,
                "preset_path": preset_path,
                "total_bones": len(bone_names),
                "pattern": pattern,
                "matched_count": len(matched),
                "matched_bones": matched,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")


# ═══════════════════════════════════════════════════════════════
# 12. mcp_reload_addon — ARP Convert 애드온 파일 sync + 재등록
# ═══════════════════════════════════════════════════════════════


def mcp_reload_addon():
    """repo의 scripts/arp_*.py를 Blender addons 디렉토리로 sync하고 애드온을 재등록.

    Sub-project ③(addon.py 분할) 리팩터링 사이클에서 매 커밋 후 호출한다.
    repo에서 파일을 수정해도 Blender가 로드한 캐시는 구버전이므로, 이 함수가:
    1) BLENDER_ADDONS/arp_*.py를 모두 삭제 (구버전 잔재 방지)
    2) repo의 최신 arp_*.py + arp_convert_addon.py를 복사
    3) sys.modules에서 arp_* 캐시 제거 (arp_utils 제외 — 의존 없음)
    4) bpy.ops.preferences.addon_disable → addon_enable로 재등록

    반환: 복사된 파일 목록과 재등록 상태.
    """
    try:
        import glob
        import shutil

        repo_scripts = os.path.dirname(os.path.abspath(__file__))
        blender_user = os.environ.get("APPDATA", "")
        if not blender_user:
            _result(False, error="APPDATA 환경변수 없음 (Windows 전용 경로)")
            return

        blender_addons = os.path.join(
            blender_user,
            "Blender Foundation",
            "Blender",
            "4.5",
            "scripts",
            "addons",
        )
        if not os.path.isdir(blender_addons):
            _result(False, error=f"Blender addons 디렉토리 없음: {blender_addons}")
            return

        # 애드온이 runtime에 의존하는 프로젝트 모듈 allowlist.
        # arp_* 와 addon 엔트리 외에도 skeleton_analyzer / weight_transfer_rules는
        # 애드온 오퍼레이터 내부에서 import되므로 반드시 같이 sync해야 한다.
        _ADDON_DEPS_EXTRA = {
            "skeleton_analyzer.py",
            "skeleton_detection.py",
            "weight_transfer_rules.py",
        }

        def _should_sync(name: str) -> bool:
            if not name.endswith(".py"):
                return False
            if name.startswith("arp_"):
                return True
            if name == "arp_convert_addon.py":
                return True
            return name in _ADDON_DEPS_EXTRA

        # 1) 기존 arp_*.py + 의존 모듈 삭제
        removed = []
        for old in glob.glob(os.path.join(blender_addons, "arp_*.py")):
            os.remove(old)
            removed.append(os.path.basename(old))
        for dep in _ADDON_DEPS_EXTRA:
            dep_path = os.path.join(blender_addons, dep)
            if os.path.exists(dep_path):
                os.remove(dep_path)
                removed.append(dep)

        # 2) repo의 arp_*.py + arp_convert_addon.py + 의존 모듈 복사
        copied = []
        for name in sorted(os.listdir(repo_scripts)):
            if _should_sync(name):
                shutil.copy2(
                    os.path.join(repo_scripts, name),
                    os.path.join(blender_addons, name),
                )
                copied.append(name)

        # 3) sys.modules 캐시 제거 — 애드온 의존 모듈 전부 (arp_utils 포함 이번엔)
        purged = []
        for m in list(sys.modules.keys()):
            if m.startswith("arp_") or m in (
                "skeleton_analyzer",
                "skeleton_detection",
                "weight_transfer_rules",
            ):
                del sys.modules[m]
                purged.append(m)

        # 4) 애드온 재등록
        addon_name = "arp_convert_addon"
        disable_ok = True
        try:
            bpy.ops.preferences.addon_disable(module=addon_name)
        except Exception:
            disable_ok = False  # 이미 비활성이면 OK

        enable_ok = True
        enable_error = None
        try:
            bpy.ops.preferences.addon_enable(module=addon_name)
        except Exception as ee:
            enable_ok = False
            enable_error = str(ee)

        _result(
            True,
            {
                "blender_addons_dir": blender_addons,
                "removed_count": len(removed),
                "removed": removed,
                "copied_count": len(copied),
                "copied": copied,
                "purged_modules_count": len(purged),
                "purged_modules": purged,
                "disable_ok": disable_ok,
                "enable_ok": enable_ok,
                "enable_error": enable_error,
            },
        )
    except Exception as e:
        _result(False, error=f"{e}\n{traceback.format_exc()}")

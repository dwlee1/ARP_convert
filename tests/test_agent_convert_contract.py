import ast
from pathlib import Path

import agent_convert_contract as acc


def test_blocked_result_has_required_user_fix_fields():
    result = acc.blocked(
        stage="preview_roles",
        problem="Preview role confidence is below threshold.",
        evidence={"confidence": 0.63, "threshold": 0.8},
        recommended_fix="Assign missing front leg roles in Source Hierarchy.",
        retry_from="preview_roles",
        report_path="C:/repo/agent_reports/rabbit.json",
    )

    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["stage"] == "preview_roles"
    assert result["error"]["problem"] == "Preview role confidence is below threshold."
    assert result["error"]["evidence"]["confidence"] == 0.63
    assert result["error"]["recommended_fix"].startswith("Assign missing")
    assert result["error"]["retry_from"] == "preview_roles"
    assert result["report_path"].endswith("rabbit.json")


def test_failed_result_carries_traceback_without_user_retry_claim():
    result = acc.failed(
        stage="build_rig",
        problem="Build Rig operator failed.",
        evidence={"operator_result": ["CANCELLED"]},
        report_path="C:/repo/agent_reports/fox.json",
    )

    assert result["success"] is False
    assert result["status"] == "failed"
    assert result["error"]["problem"] == "Build Rig operator failed."
    assert "retry_from" not in result["error"]


def test_complete_result_wraps_summary_under_data():
    result = acc.complete(
        stage="complete",
        data={"summary": {"actions": 12}, "report_path": "C:/repo/agent_reports/fox.json"},
    )

    assert result["success"] is True
    assert result["status"] == "complete"
    assert result["stage"] == "complete"
    assert result["data"]["summary"]["actions"] == 12


def test_partial_result_is_successful_but_not_complete():
    result = acc.partial(
        stage="retarget_skipped",
        data={"summary": {"actions": 0}, "warnings": ["No actions found."]},
    )

    assert result["success"] is True
    assert result["status"] == "partial"
    assert result["stage"] == "retarget_skipped"
    assert result["data"]["warnings"] == ["No actions found."]


def test_compact_payload_removes_large_lists_in_summary_mode():
    payload = {
        "summary": {"actions": 3},
        "roles": {"spine": ["spine01", "spine02"]},
        "unmapped_bones": ["eye_L", "eye_R"],
        "nested": {"pairs": [{"source": "DEF-a", "target": "c_a"}]},
    }

    result = acc.compact_payload(payload, verbosity="summary")

    assert result == {"summary": {"actions": 3}, "nested": {}}


def test_compact_payload_keeps_large_lists_in_diagnostic_mode():
    payload = {"roles": {"spine": ["spine01"]}, "unmapped_bones": ["eye_L"]}

    result = acc.compact_payload(payload, verbosity="diagnostic")

    assert result == payload


def test_sample_frames_returns_five_sorted_unique_frames_for_long_range():
    assert acc.sample_frames(1, 101, count=5) == [1, 26, 51, 76, 101]


def test_sample_frames_handles_single_frame_action():
    assert acc.sample_frames(12, 12, count=5) == [12]


def test_sample_frames_orders_reversed_ranges():
    assert acc.sample_frames(10, 2, count=5) == [2, 4, 6, 8, 10]


def test_evaluate_frame_thresholds_passes_clean_summary():
    result = acc.evaluate_frame_thresholds(
        {
            "pair_count": 8,
            "pass_count": 8,
            "overall_max_err": 0.004,
            "overall_rot_max_deg": 2.0,
        }
    )

    assert result["ok"] is True
    assert result["violations"] == []
    assert result["pass_rate"] == 1.0


def test_evaluate_frame_thresholds_blocks_large_position_error():
    result = acc.evaluate_frame_thresholds(
        {
            "pair_count": 8,
            "pass_count": 7,
            "overall_max_err": 0.011,
            "overall_rot_max_deg": 2.0,
        }
    )

    assert result["ok"] is False
    assert "position error 11.000mm exceeds 10.000mm" in result["violations"]


def test_evaluate_frame_thresholds_blocks_large_rotation_error():
    result = acc.evaluate_frame_thresholds(
        {
            "pair_count": 8,
            "pass_count": 8,
            "overall_max_err": 0.001,
            "overall_rot_max_deg": 6.0,
        }
    )

    assert result["ok"] is False
    assert "rotation error 6.000deg exceeds 5.000deg" in result["violations"]


def test_evaluate_frame_thresholds_blocks_low_pass_rate():
    result = acc.evaluate_frame_thresholds(
        {
            "pair_count": 10,
            "pass_count": 7,
            "overall_max_err": 0.001,
            "overall_rot_max_deg": 2.0,
        }
    )

    assert result["ok"] is False
    assert "pass rate 70.0% is below 80.0%" in result["violations"]


def test_select_core_pairs_prioritizes_root_spine_head_legs_feet():
    pairs = [
        {"source": "DEF-eye", "target": "cc_eye", "role": None},
        {"source": "DEF-tail", "target": "c_tail_01.x", "role": "tail"},
        {"source": "DEF-root", "target": "c_root.x", "role": "root"},
        {"source": "DEF-spine", "target": "c_spine_01.x", "role": "spine"},
        {"source": "DEF-head", "target": "c_head.x", "role": "head"},
        {"source": "DEF-thigh_L", "target": "c_thigh_b.l", "role": "back_leg_l"},
        {"source": "DEF-foot_L", "target": "c_foot_fk.l", "role": "back_foot_l"},
        {"source": "DEF-thigh_R", "target": "c_thigh_b.r", "role": "back_leg_r"},
        {"source": "DEF-foot_R", "target": "c_foot_fk.r", "role": "back_foot_r"},
    ]

    result = acc.select_core_pairs(pairs, limit=5)

    assert result == [
        ("DEF-root", "c_root.x"),
        ("DEF-spine", "c_spine_01.x"),
        ("DEF-head", "c_head.x"),
        ("DEF-thigh_L", "c_thigh_b.l"),
        ("DEF-thigh_R", "c_thigh_b.r"),
    ]


def test_build_report_path_uses_blend_stem_and_timestamp(tmp_path: Path):
    result = acc.build_report_path(
        blend_file="C:/animals/Fox AllAni.blend",
        report_dir=str(tmp_path),
        timestamp="20260426_180000",
    )

    assert result == str(tmp_path / "Fox_AllAni_20260426_180000.json")


def test_validate_required_roles_accepts_root_spine_head_and_feet():
    pairs = [
        {"source": "DEF-root", "target": "c_root.x", "role": "root"},
        {"source": "DEF-spine", "target": "c_spine_01.x", "role": "spine"},
        {"source": "DEF-head", "target": "c_head.x", "role": "head"},
        {"source": "DEF-thigh_L", "target": "c_thigh_b.l", "role": "back_leg_l"},
        {"source": "DEF-thigh_R", "target": "c_thigh_b.r", "role": "back_leg_r"},
        {"source": "DEF-foot_L", "target": "c_foot_fk.l", "role": "back_foot_l"},
        {"source": "DEF-foot_R", "target": "c_foot_fk.r", "role": "back_foot_r"},
    ]

    result = acc.validate_required_roles(pairs)

    assert result == {"ok": True, "missing_roles": []}


def test_validate_required_roles_blocks_missing_head_and_foot():
    pairs = [
        {"source": "DEF-root", "target": "c_root.x", "role": "root"},
        {"source": "DEF-spine", "target": "c_spine_01.x", "role": "spine"},
        {"source": "DEF-thigh_L", "target": "c_thigh_b.l", "role": "back_leg_l"},
        {"source": "DEF-thigh_R", "target": "c_thigh_b.r", "role": "back_leg_r"},
    ]

    result = acc.validate_required_roles(pairs)

    assert result == {"ok": False, "missing_roles": ["head", "back_foot_l", "back_foot_r"]}


def test_mcp_bridge_exposes_agent_convert_entrypoint():
    source = Path("scripts/mcp_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    assert "mcp_agent_convert_current_file" in function_names


def test_mcp_bridge_has_agent_report_and_preflight_helpers():
    source = Path("scripts/mcp_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    assert {"_agent_emit", "_agent_write_report", "_agent_preflight"} <= function_names
    assert '"agent_convert_contract"' in source


def test_mcp_bridge_has_build_gate_helpers():
    source = Path("scripts/mcp_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}

    assert {
        "_agent_create_preview",
        "_agent_collect_roles_payload",
        "_agent_build_rig",
        "_agent_validate_weights",
        "_agent_inspect_pairs",
    } <= function_names


def test_agent_entrypoint_runs_preview_build_weight_and_pair_gates():
    source = Path("scripts/mcp_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    entrypoint = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "mcp_agent_convert_current_file"
    )
    called_names = {
        node.func.id
        for node in ast.walk(entrypoint)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert {
        "_agent_create_preview",
        "_agent_build_rig",
        "_agent_validate_weights",
        "_agent_inspect_pairs",
    } <= called_names

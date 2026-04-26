# Agent Convert Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MCP-first single-file harness so Codex, Claude, or another AI agent can convert the currently open quadruped `.blend` to ARP and retarget animations through one shared entrypoint.

**Architecture:** Put all pure status/result/report contracts in `scripts/agent_convert_contract.py` and cover them with pytest. Keep Blender-dependent orchestration in `scripts/mcp_bridge.py` as one public `mcp_agent_convert_current_file()` function that calls existing ARP Convert operators through return-value helpers and emits compact JSON while writing detailed reports to `agent_reports/`. Do not call existing public MCP functions from inside the harness when they print JSON through `_result()`; extract or share internal helpers instead.

**Tech Stack:** Blender 4.5 Python, Auto-Rig Pro, existing ARP Convert addon operators, MCP bridge JSON stdout, pytest, ruff.

---

## File Structure

- Create `scripts/agent_convert_contract.py`
  - Pure Python helpers for stage result contracts, compact payload filtering, report paths, frame sampling, thresholds, and pair selection.
- Create `tests/test_agent_convert_contract.py`
  - Unit tests for the pure helpers; no `bpy` import.
- Modify `scripts/mcp_bridge.py`
  - Add `mcp_agent_convert_current_file()` and private stage helpers.
  - Reuse existing setup/weight/frame comparison logic where practical by extracting return-value helpers, but keep stdout-printing public MCP functions as wrappers only.
- Modify `.gitignore`
  - Ignore `/agent_reports/`.
- Modify `docs/MCP_Recipes.md`
  - Document the new entrypoint and status contract.
- Modify `.claude/skills/arp-quadruped-convert/SKILL.md`
  - Replace the long raw-call flow with the single MCP entrypoint and blocked/failed handling.
- Modify `.agents/skills/arp-quadruped-convert/SKILL.md`
  - Keep Codex-facing conversion instructions in sync with the Claude skill.
- Modify `AGENTS.md`
  - Add a short Codex/Claude common rule for actual conversion work.
- Modify `docs/ProjectPlan.md`
  - Note Unity migration is paused and agent convert harness is the active priority.

---

### Task 0: Baseline Corrections Before Implementation

**Files:**
- Modify: `.gitignore`
- Modify: `docs/ProjectPlan.md`
- Modify: `docs/superpowers/specs/2026-04-26-agent-convert-harness-design.md`
- Modify: `docs/superpowers/plans/2026-04-26-agent-convert-harness.md`

- [x] **Step 1: Work from `feat/agent-convert-harness` based on `origin/master`**

Do not implement harness code on `master`; keep unrelated local MCP environment changes out of this branch.

- [x] **Step 2: Ignore generated agent reports**

Add `/agent_reports/` to `.gitignore`.

- [x] **Step 3: Align the active priority**

Update `docs/ProjectPlan.md` so Agent Convert Harness is the active priority and Unity Phase 3 is explicitly paused until the harness is stable.

- [x] **Step 4: Clarify retry behavior**

Keep `retry_from` as a diagnostic label only for v1. After user fixes, rerun `mcp_agent_convert_current_file()` from the beginning. Do not add partial resume support in this implementation.

- [x] **Step 5: Avoid stdout MCP function reuse**

Plan implementation around return-value helpers. Existing public MCP functions that call `_result()` remain wrappers so the harness does not emit multiple JSON payloads.

- [x] **Step 6: Keep agent instructions synchronized**

When documenting the final flow, update both `.claude/skills/arp-quadruped-convert/SKILL.md` and `.agents/skills/arp-quadruped-convert/SKILL.md`.

- [x] **Step 7: Provision Python 3.11 verification tooling**

Use the project-local virtual environment when direct `pytest`/`ruff` commands are unavailable:

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/Scripts/python.exe pytest ruff
.venv/Scripts/python.exe -m pytest tests/ -v
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```

Baseline on 2026-04-26: Python 3.11.15, pytest 9.0.3, ruff 0.15.12;
`262 passed, 2 skipped`; `All checks passed!`.

---

### Task 1: Pure Contract Helpers

**Files:**
- Create: `scripts/agent_convert_contract.py`
- Create: `tests/test_agent_convert_contract.py`

- [ ] **Step 1: Write failing tests for result contracts, compact payloads, frame sampling, thresholds, and pair selection**

Create `tests/test_agent_convert_contract.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail because the module is missing**

Run:

```bash
pytest tests/test_agent_convert_contract.py -v
```

Expected:

```text
ModuleNotFoundError: No module named 'agent_convert_contract'
```

- [ ] **Step 3: Implement the pure helper module**

Create `scripts/agent_convert_contract.py`:

```python
from __future__ import annotations

import re
from pathlib import Path

LARGE_DETAIL_KEYS = {
    "roles",
    "unmapped_bones",
    "pairs",
    "results",
    "per_frame",
    "per_frame_rot_deg",
    "bone_names",
    "top_offenders_detailed",
}

CORE_ROLE_ORDER = [
    "root",
    "trajectory",
    "spine",
    "head",
    "back_leg_l",
    "back_leg_r",
    "front_leg_l",
    "front_leg_r",
    "back_foot_l",
    "back_foot_r",
    "front_foot_l",
    "front_foot_r",
    "tail",
    "ear_l",
    "ear_r",
]


def blocked(stage, problem, evidence, recommended_fix, retry_from, report_path=None):
    result = {
        "success": False,
        "status": "blocked",
        "stage": stage,
        "error": {
            "problem": problem,
            "evidence": evidence,
            "recommended_fix": recommended_fix,
            "retry_from": retry_from,
        },
    }
    if report_path:
        result["report_path"] = report_path
    return result


def failed(stage, problem, evidence, report_path=None):
    result = {
        "success": False,
        "status": "failed",
        "stage": stage,
        "error": {
            "problem": problem,
            "evidence": evidence,
        },
    }
    if report_path:
        result["report_path"] = report_path
    return result


def complete(stage, data):
    return {"success": True, "status": "complete", "stage": stage, "data": data}


def partial(stage, data):
    return {"success": True, "status": "partial", "stage": stage, "data": data}


def compact_payload(value, *, verbosity="summary"):
    if verbosity == "diagnostic":
        return value
    if isinstance(value, dict):
        compact = {}
        for key, child in value.items():
            if key in LARGE_DETAIL_KEYS:
                continue
            compact[key] = compact_payload(child, verbosity=verbosity)
        return compact
    if isinstance(value, list):
        return [compact_payload(item, verbosity=verbosity) for item in value]
    return value


def sample_frames(frame_start, frame_end, *, count=5):
    start = int(min(frame_start, frame_end))
    end = int(max(frame_start, frame_end))
    if start == end:
        return [start]
    if count <= 1:
        return [start]
    step = (end - start) / (count - 1)
    frames = [int(round(start + step * i)) for i in range(count)]
    return sorted(set(frames))


def evaluate_frame_thresholds(
    summary,
    *,
    position_threshold_m=0.01,
    rotation_threshold_deg=5.0,
    min_pass_rate=0.80,
):
    pair_count = int(summary.get("pair_count", 0) or 0)
    pass_count = int(summary.get("pass_count", 0) or 0)
    pass_rate = 1.0 if pair_count == 0 else pass_count / pair_count
    max_position_m = float(summary.get("overall_max_err", 0.0) or 0.0)
    max_rotation_deg = float(summary.get("overall_rot_max_deg", 0.0) or 0.0)

    violations = []
    if max_position_m > position_threshold_m:
        violations.append(
            f"position error {max_position_m * 1000:.3f}mm exceeds "
            f"{position_threshold_m * 1000:.3f}mm"
        )
    if max_rotation_deg > rotation_threshold_deg:
        violations.append(
            f"rotation error {max_rotation_deg:.3f}deg exceeds "
            f"{rotation_threshold_deg:.3f}deg"
        )
    if pass_rate < min_pass_rate:
        violations.append(f"pass rate {pass_rate * 100:.1f}% is below {min_pass_rate * 100:.1f}%")

    return {"ok": not violations, "violations": violations, "pass_rate": pass_rate}


def select_core_pairs(pairs, *, limit=8):
    role_rank = {role: index for index, role in enumerate(CORE_ROLE_ORDER)}

    def rank(pair):
        role = pair.get("role")
        return (role_rank.get(role, len(role_rank)), str(pair.get("source", "")))

    selected = []
    for pair in sorted(pairs, key=rank):
        source = pair.get("source")
        target = pair.get("target")
        if not source or not target:
            continue
        selected.append((source, target))
        if len(selected) >= limit:
            break
    return selected


def build_report_path(blend_file, report_dir, timestamp):
    stem = Path(blend_file).stem if blend_file else "unsaved"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_") or "unsaved"
    return str(Path(report_dir) / f"{safe_stem}_{timestamp}.json")
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
pytest tests/test_agent_convert_contract.py -v
```

Expected:

```text
16 passed
```

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add scripts/agent_convert_contract.py tests/test_agent_convert_contract.py
git commit -m "test(harness): add agent convert contract helpers"
```

---

### Task 2: Agent Entrypoint, Preflight, and Report Emission

**Files:**
- Modify: `scripts/mcp_bridge.py`
- Modify: `.gitignore`
- Test: `tests/test_agent_convert_contract.py`

- [ ] **Step 1: Add report-dir ignore**

Append this line to `.gitignore` near the cache/output entries:

```gitignore
/agent_reports/
```

- [ ] **Step 2: Add a failing static test for the bridge entrypoint name in the public module**

Append to `tests/test_agent_convert_contract.py`:

```python
import ast


def test_mcp_bridge_exposes_agent_convert_entrypoint():
    source = Path("scripts/mcp_bridge.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    assert "mcp_agent_convert_current_file" in function_names
```

- [ ] **Step 3: Run the static test and verify it fails**

Run:

```bash
pytest tests/test_agent_convert_contract.py::test_mcp_bridge_exposes_agent_convert_entrypoint -v
```

Expected:

```text
AssertionError: assert 'mcp_agent_convert_current_file' in function_names
```

- [ ] **Step 4: Update `mcp_bridge.py` imports and reload list**

At the top of `scripts/mcp_bridge.py`, add:

```python
from datetime import datetime
from pathlib import Path
```

In `_reload()`, add `"agent_convert_contract"` after `"mcp_verify"`:

```python
    for mod_name in [
        "skeleton_detection",
        "skeleton_analyzer",
        "weight_transfer_rules",
        "mcp_verify",
        "agent_convert_contract",
    ]:
```

- [ ] **Step 5: Add agent report and emit helpers to `mcp_bridge.py`**

Insert these helpers after `_result()`:

```python
def _agent_emit(payload):
    """Print an agent harness payload without forcing the legacy data/error wrapper."""
    print(json.dumps(payload, ensure_ascii=False, default=str))


def _agent_default_report_dir():
    repo_root = Path(_SCRIPT_DIR).parent
    return repo_root / "agent_reports"


def _agent_write_report(report_path, report):
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return str(path)
```

- [ ] **Step 6: Add preflight helper to `mcp_bridge.py`**

Insert this helper before `mcp_agent_convert_current_file()`:

```python
def _agent_preflight():
    from arp_utils import find_arp_armature, find_source_armature, get_3d_viewport_context

    source_obj = find_source_armature()
    arp_obj = find_arp_armature()
    ctx = get_3d_viewport_context()

    bound_meshes = []
    meshes = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        armature_name = None
        for mod in obj.modifiers:
            if mod.type == "ARMATURE" and mod.object:
                armature_name = mod.object.name
                break
        meshes.append({"name": obj.name, "bound_armature": armature_name})
        if armature_name:
            bound_meshes.append(obj.name)

    actions = [
        {
            "name": action.name,
            "frame_range": [int(action.frame_range[0]), int(action.frame_range[1])],
            "fcurve_count": len(action.fcurves),
        }
        for action in bpy.data.actions
    ]

    has_props = hasattr(bpy.context.scene, "arp_convert_props")

    return {
        "blend_file": bpy.data.filepath or "",
        "source_obj": source_obj,
        "arp_obj": arp_obj,
        "has_view3d_context": ctx is not None,
        "has_addon_props": has_props,
        "bound_meshes": bound_meshes,
        "meshes": meshes,
        "actions": actions,
    }
```

- [ ] **Step 7: Add the first public entrypoint implementation with preflight blocking**

Insert this function before `mcp_scene_summary()`:

```python
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

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(report_dir) if report_dir else _agent_default_report_dir()
        report_path = acc.build_report_path(bpy.data.filepath or "unsaved", str(output_dir), timestamp)
        report = {
            "blend_file": bpy.data.filepath or "",
            "include_retarget": include_retarget,
            "allow_cleanup": allow_cleanup,
            "confidence_threshold": confidence_threshold,
            "verbosity": verbosity,
            "steps": [],
            "warnings": [],
        }

        preflight = _agent_preflight()
        report["steps"].append({"stage": "preflight", "data": acc.compact_payload(preflight)})

        if preflight["source_obj"] is None:
            _agent_write_report(report_path, report)
            _agent_emit(
                acc.blocked(
                    "preflight",
                    "No source armature was found in the current Blender scene.",
                    {"blend_file": preflight["blend_file"] or "(unsaved)"},
                    "Open a .blend file that contains the source animal armature, then rerun the harness.",
                    "preflight",
                    report_path,
                )
            )
            return

        if preflight["arp_obj"] is not None:
            _agent_write_report(report_path, report)
            _agent_emit(
                acc.blocked(
                    "preflight",
                    "An ARP rig already exists in the current scene.",
                    {"arp_armature": preflight["arp_obj"].name},
                    "Open a clean source file or remove the existing ARP rig before rerunning.",
                    "preflight",
                    report_path,
                )
            )
            return

        if not preflight["has_addon_props"]:
            _agent_write_report(report_path, report)
            _agent_emit(
                acc.failed(
                    "preflight",
                    "ARP Convert addon properties are not registered on the scene.",
                    {"has_addon_props": False},
                    report_path,
                )
            )
            return

        if not preflight["has_view3d_context"]:
            _agent_write_report(report_path, report)
            _agent_emit(
                acc.failed(
                    "preflight",
                    "No 3D View context is available for Blender operators.",
                    {"has_view3d_context": False},
                    report_path,
                )
            )
            return

        warnings = []
        if not preflight["bound_meshes"]:
            warnings.append("No mesh is bound to an armature; weight verification will be limited.")

        data = {
            "blend_file": preflight["blend_file"],
            "source_armature": preflight["source_obj"].name,
            "steps_completed": ["preflight"],
            "warnings": warnings,
            "summary": {
                "bound_meshes": len(preflight["bound_meshes"]),
                "actions": len(preflight["actions"]),
            },
            "report_path": report_path,
        }
        report["warnings"].extend(warnings)
        _agent_write_report(report_path, report)
        _agent_emit(acc.partial("preflight", data))
    except Exception as e:
        _agent_emit(
            {
                "success": False,
                "status": "failed",
                "stage": "exception",
                "error": {
                    "problem": str(e),
                    "evidence": traceback.format_exc(),
                },
            }
        )
```

- [ ] **Step 8: Run focused tests and compile the bridge**

Run:

```bash
pytest tests/test_agent_convert_contract.py -v
python -m compileall -q scripts/mcp_bridge.py scripts/agent_convert_contract.py
```

Expected:

```text
17 passed
```

Compileall should exit with code 0 and print no output.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add .gitignore scripts/mcp_bridge.py tests/test_agent_convert_contract.py
git commit -m "feat(harness): add agent convert preflight entrypoint"
```

---

### Task 3: Preview, Build Rig, Weight, and Bone Pair Gates

**Files:**
- Modify: `scripts/mcp_bridge.py`
- Modify: `scripts/agent_convert_contract.py`
- Modify: `tests/test_agent_convert_contract.py`

- [ ] **Step 1: Add pure tests for required role validation**

Append to `tests/test_agent_convert_contract.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify the new validation function is missing**

Run:

```bash
pytest tests/test_agent_convert_contract.py::test_validate_required_roles_accepts_root_spine_head_and_feet -v
```

Expected:

```text
AttributeError: module 'agent_convert_contract' has no attribute 'validate_required_roles'
```

- [ ] **Step 3: Implement required role validation**

Append to `scripts/agent_convert_contract.py`:

```python
REQUIRED_ROLE_GROUPS = [
    ("root_or_trajectory", {"root", "trajectory"}),
    ("spine", {"spine"}),
    ("head", {"head"}),
    ("back_leg_l", {"back_leg_l"}),
    ("back_leg_r", {"back_leg_r"}),
    ("back_foot_l", {"back_foot_l"}),
    ("back_foot_r", {"back_foot_r"}),
]


def validate_required_roles(pairs):
    present = {pair.get("role") for pair in pairs if pair.get("role")}
    missing = []
    for label, accepted_roles in REQUIRED_ROLE_GROUPS:
        if present.isdisjoint(accepted_roles):
            if label == "root_or_trajectory":
                missing.append("root")
            else:
                missing.append(label)
    return {"ok": not missing, "missing_roles": missing}
```

- [ ] **Step 4: Add bridge helpers for preview, build, weight summary, and bone pairs**

Insert these helpers before `mcp_agent_convert_current_file()`:

```python
def _agent_create_preview(confidence_threshold, report, report_path, verbosity):
    import agent_convert_contract as acc
    from arp_utils import ensure_object_mode, get_3d_viewport_context, quiet_logs

    with quiet_logs():
        ensure_object_mode()
        ctx = get_3d_viewport_context()
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
        report["diagnostic"] = {"stage": "preview_roles", **roles_payload}
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
    props = bpy.context.scene.arp_convert_props
    roles = {}
    unmapped = []
    for item in props.bone_roles:
        roles.setdefault(item.role, []).append(item.name)
        if item.role == "unmapped":
            unmapped.append(item.name)
    return {"roles": roles, "unmapped_bones": unmapped}


def _agent_build_rig(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import ensure_object_mode, find_arp_armature, get_3d_viewport_context, quiet_logs

    with quiet_logs():
        ensure_object_mode()
        ctx = get_3d_viewport_context()
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
    report["steps"].append(
        {
            "stage": "build_rig",
            "data": {
                "arp_armature": arp_obj.name,
                "bone_count": len(arp_obj.data.bones),
                "c_bone_count": c_bone_count,
            },
        }
    )
    return {"success": True, "arp_obj": arp_obj, "data": report["steps"][-1]["data"]}


def _agent_validate_weights(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import find_arp_armature, find_mesh_objects, quiet_logs

    with quiet_logs():
        arp_obj = find_arp_armature()
        meshes = find_mesh_objects(arp_obj) if arp_obj else []

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

    data = {"meshes": mesh_results, "unweighted_vertices": total_unweighted}
    report["steps"].append({"stage": "weights", "data": data})

    if meshes and total_unweighted > 0:
        _agent_write_report(report_path, report)
        return acc.blocked(
            "weights",
            "One or more bound meshes contain unweighted vertices.",
            data,
            "Inspect the listed meshes in Weight Paint and assign weights before rerunning retarget.",
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
```

- [ ] **Step 5: Extend `mcp_agent_convert_current_file()` through Build Rig and pair gates**

In `mcp_agent_convert_current_file()`, after preflight passes, replace the current final partial emission with this sequence:

```python
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
                "blend_file": preflight["blend_file"],
                "source_armature": preflight["source_obj"].name,
                "arp_armature": build_result["data"]["arp_armature"],
                "preview_confidence": preview_result["data"]["confidence"],
                "steps_completed": ["preflight", "preview", "build_rig", "weights", "bone_pairs"],
                "warnings": report["warnings"],
                "summary": {
                    "bound_meshes": len(preflight["bound_meshes"]),
                    "actions": len(preflight["actions"]),
                    "bone_pairs": pairs_result["data"]["total_pairs"],
                    "unweighted_vertices": weight_result["data"]["unweighted_vertices"],
                },
                "report_path": report_path,
            }
            _agent_write_report(report_path, report)
            status = acc.complete("build_rig_complete", data)
            if include_retarget and not preflight["actions"]:
                data["warnings"].append("No actions found; retarget was skipped.")
                status = acc.partial("retarget_skipped", data)
            _agent_emit(status)
            return
```

- [ ] **Step 6: Run focused tests and compile**

Run:

```bash
pytest tests/test_agent_convert_contract.py -v
python -m compileall -q scripts/mcp_bridge.py scripts/agent_convert_contract.py
```

Expected:

```text
19 passed
```

- [ ] **Step 7: Commit Task 3**

Run:

```bash
git add scripts/agent_convert_contract.py scripts/mcp_bridge.py tests/test_agent_convert_contract.py
git commit -m "feat(harness): add build rig validation gates"
```

---

### Task 4: Retarget, Custom Scale, and Compact Frame Verification

**Files:**
- Modify: `scripts/mcp_bridge.py`

- [ ] **Step 1: Add retarget helpers to `mcp_bridge.py`**

Insert before `mcp_agent_convert_current_file()`:

```python
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

    with quiet_logs():
        source_obj = find_source_armature()
        arp_obj = find_arp_armature()

    if source_obj is None or arp_obj is None:
        return acc.failed(
            "setup_retarget",
            "Source or ARP armature is missing before retarget setup.",
            {
                "source_found": source_obj is not None,
                "arp_found": arp_obj is not None,
            },
            report_path,
        )

    transform_error = preflight_check_transforms(source_obj, arp_obj)
    if transform_error:
        return acc.blocked(
            "setup_retarget",
            "Armature transform preflight failed.",
            {"error": transform_error},
            "Apply or reset the listed armature transforms, then rerun setup retarget.",
            "setup_retarget",
            report_path,
        )

    pairs_json = arp_obj.get(BAKE_PAIRS_KEY, "")
    bone_pairs = deserialize_bone_pairs(pairs_json)
    result = setup_arp_retarget(source_obj, arp_obj, bone_pairs)
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
    from arp_utils import ensure_object_mode, quiet_logs

    before = {action.name for action in bpy.data.actions}
    with quiet_logs():
        ensure_object_mode()
        result = bpy.ops.arp.retarget()
    after = {action.name for action in bpy.data.actions}
    remap_actions = sorted(name for name in after if "_remap" in name and name not in before)

    data = {"operator_result": list(result), "remap_actions": remap_actions}
    report["steps"].append({"stage": "arp_retarget", "data": data})

    if "FINISHED" not in result:
        return acc.failed(
            "arp_retarget",
            "Auto-Rig Pro retarget operator did not finish.",
            data,
            report_path,
        )

    if not remap_actions:
        return acc.blocked(
            "arp_retarget",
            "Auto-Rig Pro retarget finished but no _remap actions were created.",
            data,
            "Run ARP Re-Retarget manually in the Remap panel, then rerun the harness from frame verification.",
            "arp_retarget",
            report_path,
        )

    return {"success": True, "data": data}


def _agent_copy_custom_scale(report, report_path):
    import agent_convert_contract as acc
    from arp_utils import ensure_object_mode, get_3d_viewport_context, quiet_logs

    with quiet_logs():
        ensure_object_mode()
        ctx = get_3d_viewport_context()
        with bpy.context.temp_override(**ctx):
            result = bpy.ops.arp_convert.copy_custom_scale()

    data = {"operator_result": list(result)}
    report["steps"].append({"stage": "copy_custom_scale", "data": data})
    if "FINISHED" not in result:
        return acc.failed(
            "copy_custom_scale",
            "Copy Custom Scale operator did not finish.",
            data,
            report_path,
        )
    return {"success": True, "data": data}
```

- [ ] **Step 2: Add compact frame verification helper to `mcp_bridge.py`**

Insert before `mcp_agent_convert_current_file()`:

```python
def _agent_verify_frames(report, report_path, pairs_data, actions):
    import agent_convert_contract as acc

    compare_pairs = acc.select_core_pairs(pairs_data["pairs"], limit=8)
    if not compare_pairs:
        return acc.blocked(
            "frame_verify",
            "No core bone pairs are available for frame verification.",
            {"pair_count": len(pairs_data.get("pairs", []))},
            "Inspect bone_pairs and fix role assignments before rerunning retarget verification.",
            "bone_pairs",
            report_path,
        )

    action = actions[0]
    frames = acc.sample_frames(action["frame_range"][0], action["frame_range"][1], count=5)
    compare_result = _agent_compare_frames_inline(compare_pairs, frames, action["name"], detailed=False)
    report["steps"].append({"stage": "frame_verify", "data": compare_result})

    threshold = acc.evaluate_frame_thresholds(compare_result)
    if not threshold["ok"]:
        detailed = _agent_compare_frames_inline(compare_pairs, frames, action["name"], detailed=True)
        report["diagnostic"] = {"stage": "frame_verify", "details": detailed}
        _agent_write_report(report_path, report)
        return acc.blocked(
            "frame_verify",
            "Frame verification exceeded allowed error thresholds.",
            {"violations": threshold["violations"], "summary": compare_result},
            "Inspect the top offending source/ARP pairs and correct role mappings or retarget settings.",
            "frame_verify",
            report_path,
        )

    return {"success": True, "data": {**compare_result, "pass_rate": threshold["pass_rate"]}}
```

Add this inline compare helper by extracting the body of `mcp_compare_frames()` without printing:

```python
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
        arp_action = bpy.data.actions.get(f"{action_name}_arp")
        if src_action is None or arp_action is None:
            arp_action = bpy.data.actions.get(f"{action_name}_remap")
        if src_action is None or arp_action is None:
            raise RuntimeError(f"액션 '{action_name}' 또는 대응 ARP/remap 액션을 찾을 수 없습니다.")
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
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            src_matrix = src_obj.matrix_world @ src_pb.matrix
            arp_matrix = arp_obj.matrix_world @ arp_pb.matrix
            src_pos = src_obj.matrix_world @ src_pb.head
            arp_pos = arp_obj.matrix_world @ arp_pb.head
            distance = (arp_pos - src_pos).length
            rotation_deg = math.degrees(
                src_matrix.to_quaternion().rotation_difference(arp_matrix.to_quaternion()).angle
            )
            per_frame.append(distance)
            per_frame_rot_deg.append(rotation_deg)
            all_distances.append(distance)
            all_rotation_errors.append(rotation_deg)

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
    if detailed:
        return {
            "action": action_name,
            "frame_count": len(frames),
            "pair_count": len(pairs),
            "results": pair_results,
            "overall_max_err": overall["max"],
            "overall_mean_err": overall["mean"],
            "overall_rot_max_deg": overall_rot["max"],
            "overall_rot_mean_deg": overall_rot["mean"],
            "report": format_comparison_report(pair_results),
        }

    summary = summarize_pair_results(pair_results)
    return {
        "action": action_name,
        "frame_count": len(frames),
        "pair_count": len(pairs),
        "pass_count": summary["pass_count"],
        "overall_max_err": overall["max"],
        "overall_mean_err": overall["mean"],
        "overall_rot_max_deg": overall_rot["max"],
        "overall_rot_mean_deg": overall_rot["mean"],
        "top_offenders": summary["top_offenders"],
    }
```

- [ ] **Step 3: Extend `mcp_agent_convert_current_file()` through retarget and final completion**

After `pairs_result` succeeds, replace the no-retarget block from Task 3 with this full branch:

```python
        if not include_retarget or not preflight["actions"]:
            data = {
                "blend_file": preflight["blend_file"],
                "source_armature": preflight["source_obj"].name,
                "arp_armature": build_result["data"]["arp_armature"],
                "preview_confidence": preview_result["data"]["confidence"],
                "steps_completed": ["preflight", "preview", "build_rig", "weights", "bone_pairs"],
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
                _agent_write_report(report_path, report)
                _agent_emit(acc.partial("retarget_skipped", data))
            else:
                _agent_write_report(report_path, report)
                _agent_emit(acc.complete("build_rig_complete", data))
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

        frame_result = _agent_verify_frames(report, report_path, pairs_result["data"], preflight["actions"])
        if frame_result.get("success") is not True:
            _agent_emit(frame_result)
            return

        data = {
            "blend_file": preflight["blend_file"],
            "source_armature": preflight["source_obj"].name,
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
                "frame_verify_pass_rate": frame_result["data"]["pass_rate"],
                "max_position_error_mm": frame_result["data"]["overall_max_err"] * 1000,
                "max_rotation_error_deg": frame_result["data"]["overall_rot_max_deg"],
            },
            "report_path": report_path,
        }
        _agent_write_report(report_path, report)
        _agent_emit(acc.complete("complete", data))
        return
```

- [ ] **Step 4: Run tests and compile**

Run:

```bash
pytest tests/test_agent_convert_contract.py -v
python -m compileall -q scripts/mcp_bridge.py scripts/agent_convert_contract.py
```

Expected:

```text
19 passed
```

Compileall should exit with code 0 and print no output.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add scripts/mcp_bridge.py
git commit -m "feat(harness): run retarget and compact frame verification"
```

---

### Task 5: Documentation and Agent Instructions

**Files:**
- Modify: `docs/MCP_Recipes.md`
- Modify: `.claude/skills/arp-quadruped-convert/SKILL.md`
- Modify: `AGENTS.md`
- Modify: `docs/ProjectPlan.md`

- [ ] **Step 1: Update MCP recipes with the new single-call flow**

Add this section near the top of `docs/MCP_Recipes.md`, after "함수 인덱스":

```markdown
## Agent Convert Harness

단일 파일 실제 변환은 `mcp_agent_convert_current_file()`을 우선 사용한다.
Blender에 대상 `.blend`가 열려 있고 BlenderMCP가 연결된 상태에서 호출한다.

```python
import sys
repo_scripts = r"<repo-root>\scripts"
if repo_scripts not in sys.path:
    sys.path.insert(0, repo_scripts)
from mcp_bridge import mcp_agent_convert_current_file
mcp_agent_convert_current_file(include_retarget=True)
```

반환 상태:

| status | 의미 | 에이전트 행동 |
|--------|------|--------------|
| `complete` | Build Rig + Retarget + 검증 완료 | 요약과 report_path 보고 |
| `partial` | Build Rig는 됐지만 Retarget 생략 또는 일부 중단 | 완료 범위와 다음 조치 보고 |
| `blocked` | 사용자가 수정하면 재시도 가능한 상태 | `problem`, `evidence`, `recommended_fix`를 그대로 보고하고 중단 |
| `failed` | 환경/코드/ARP 호출 실패 | error와 report_path를 보고하고 중단 |

기본 응답은 compact JSON이다. 전체 role, bone_pairs, 프레임별 상세는
`agent_reports/<blend>_<timestamp>.json`에 저장된다.
```

- [ ] **Step 2: Collapse the conversion skills to the shared entrypoint**

In both `.claude/skills/arp-quadruped-convert/SKILL.md` and
`.agents/skills/arp-quadruped-convert/SKILL.md`, keep the front matter and replace the
long phase-by-phase MCP snippets with this operational core:

```markdown
## 기본 실행

실제 변환 작업은 공통 MCP 하네스를 사용한다.

```python
import sys
repo_scripts = r"<repo-root>\scripts"
if repo_scripts not in sys.path:
    sys.path.insert(0, repo_scripts)
from mcp_bridge import mcp_agent_convert_current_file
mcp_agent_convert_current_file(include_retarget=True)
```

## 결과 해석

- `complete`: 변환 완료. summary와 report_path를 사용자에게 보고한다.
- `partial`: Build Rig 등 일부 단계는 완료됐지만 retarget이 생략되었거나 멈췄다. 완료된 단계와 다음 행동을 보고한다.
- `blocked`: 사용자가 수정 가능한 상태다. `problem`, `evidence`, `recommended_fix`, `retry_from`을 그대로 보여주고 중단한다.
- `failed`: 환경, 코드, ARP operator 실패다. error와 report_path를 보여주고 중단한다.

## 원칙

- `blocked` 상태에서 임의로 다음 단계로 진행하지 않는다.
- 기본 반환에 없는 상세 데이터가 필요하면 report_path의 JSON을 확인한다.
- raw Blender Python 작성은 하네스가 `failed`를 반환했고 원인 확인이 필요한 경우에만 사용한다.
- Cleanup은 기본 자동 실행하지 않는다. 사용자가 명시적으로 원할 때만 `allow_cleanup=True`로 호출한다.
```

- [ ] **Step 3: Add Codex-facing common instruction to `AGENTS.md`**

Add this short section after "MCP 자동화" or the validation section:

```markdown
## AI 에이전트 변환 하네스

실제 단일 `.blend` 리깅 변환 작업은 공통 MCP 진입점 `mcp_agent_convert_current_file(include_retarget=True)`를 우선 사용한다.
Codex와 Claude 모두 같은 status 계약을 따른다.

- `complete`: 요약과 report_path 보고
- `partial`: 완료된 범위와 다음 행동 보고
- `blocked`: 사용자가 수정 가능한 문제이므로 `problem/evidence/recommended_fix/retry_from` 보고 후 중단
- `failed`: 환경/코드/ARP 실패이므로 error와 report_path 보고 후 중단

하네스가 `blocked`를 반환한 상태에서 임의로 다음 단계로 진행하지 않는다.
```

- [ ] **Step 4: Update `docs/ProjectPlan.md` priority section**

In `docs/ProjectPlan.md`, change the priority section so agent convert harness is first and Unity Phase 3 is paused:

```markdown
## 우선순위

1. **Agent Convert Harness** — Blender에 열린 단일 사족보행 `.blend`를 AI 에이전트가 MCP 단일 진입점으로 Build Rig + Retarget까지 진행하고, 문제 발생 시 사용자가 수정 가능한 진단을 반환하도록 한다.
2. **자동 역할 추론 정확도 개선** — 새 동물 리그에서 수동 수정 횟수 최소화
3. **Unity 이주 Phase 3 (blend-first)** — 현재 보류. 하네스 안정화 후 재개한다.
4. **기타 UX/툴 개선** — 회귀 테스트, MCP 레시피, 파일 정리 등 부수 작업
```

- [ ] **Step 5: Run markdown/static checks available locally**

Run:

```bash
python -m compileall -q scripts
pytest tests/test_agent_convert_contract.py -v
```

Expected:

```text
19 passed
```

Compileall should exit with code 0 and print no output.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add docs/MCP_Recipes.md .claude/skills/arp-quadruped-convert/SKILL.md .agents/skills/arp-quadruped-convert/SKILL.md AGENTS.md docs/ProjectPlan.md .gitignore
git commit -m "docs(harness): document shared agent convert flow"
```

If the `AGENTS.md 하드링크 동기화` hook rewrites unrelated files, inspect `git show --stat HEAD`. Amend immediately so the commit contains only intentional doc changes.

---

### Task 6: Full Verification and Blender MCP Smoke

**Files:**
- Verify only; no code changes expected.

- [ ] **Step 1: Check Python tool availability**

Run in this order from the project-local Python 3.11 environment:

```bash
.venv/Scripts/python.exe --version
.venv/Scripts/python.exe -m pytest --version
.venv/Scripts/python.exe -m ruff --version
```

Expected:

```text
pytest prints a version
ruff prints a version
python prints Python 3.11.x or newer
```

If these commands are unavailable in the current shell, use the project-approved Python environment or document the exact failure in the final report. Do not claim pytest or ruff passed without command output.

- [ ] **Step 2: Run full pytest**

Run:

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

Expected:

```text
all tests pass
```

- [ ] **Step 3: Run ruff**

Run:

```bash
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```

Expected:

```text
All checks passed!
```

- [ ] **Step 4: Run Blender addon reload smoke in an open Blender session**

In BlenderMCP execute:

```python
import sys
repo_scripts = r"<repo-root>\scripts"
if repo_scripts not in sys.path:
    sys.path.insert(0, repo_scripts)
from mcp_bridge import mcp_reload_addon
mcp_reload_addon()
```

Expected JSON:

```json
{
  "success": true
}
```

- [ ] **Step 5: Run agent harness smoke on a test `.blend`**

Open a known quadruped `.blend` in Blender. Then run:

```python
import sys
repo_scripts = r"<repo-root>\scripts"
if repo_scripts not in sys.path:
    sys.path.insert(0, repo_scripts)
from mcp_bridge import mcp_agent_convert_current_file
mcp_agent_convert_current_file(include_retarget=True)
```

Expected acceptable outcomes:

```json
{
  "success": true,
  "status": "complete"
}
```

or, if the file needs user correction:

```json
{
  "success": false,
  "status": "blocked",
  "error": {
    "problem": "Preview role confidence is below threshold.",
    "evidence": {"confidence": 0.63, "threshold": 0.8},
    "recommended_fix": "Open ARP Convert > Source Hierarchy and assign the missing roles.",
    "retry_from": "preview_roles"
  }
}
```

`blocked` is acceptable for a real animal if the report identifies a concrete user-fixable issue and does not proceed to later stages.

- [ ] **Step 6: Inspect generated report**

Open the `report_path` from the smoke result and verify it contains:

```json
{
  "blend_file": "C:/animals/fox.blend",
  "steps": [],
  "warnings": []
}
```

For a blocked case, verify it also contains:

```json
{
  "diagnostic": {
    "stage": "preview_roles"
  }
}
```

- [ ] **Step 7: Commit any verification fixes**

If verification required small fixes, commit them:

```bash
git add scripts tests docs .claude AGENTS.md .gitignore
git commit -m "fix(harness): address verification findings"
```

If no fixes were needed, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage: Tasks cover pure contract helpers, compact diagnostics, single MCP entrypoint, preflight, preview confidence gate, Build Rig, weight verification, bone_pairs verification, retarget, custom scale, frame verification, report files, docs, and verification.
- Red-flag scan: This plan contains no deferred marker, incomplete section, or undefined task dependency.
- Type consistency: The status contract consistently uses `success`, `status`, `stage`, `data`, `error`, and `report_path`; helper names match across tests and implementation snippets.
- Scope check: This plan intentionally excludes Unity batch migration, folder queues, new UI, and headless Blender guarantees.

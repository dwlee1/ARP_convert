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
}

CORE_ROLE_PRIORITY = [
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
    "neck",
    "tail",
    "ear_l",
    "ear_r",
]

REQUIRED_ROLE_GROUPS = [
    ("root_or_trajectory", {"root", "trajectory"}),
    ("spine", {"spine"}),
    ("head", {"head"}),
    ("back_leg_l", {"back_leg_l"}),
    ("back_leg_r", {"back_leg_r"}),
    ("back_foot_l", {"back_foot_l"}),
    ("back_foot_r", {"back_foot_r"}),
]


def blocked(stage, problem, evidence, recommended_fix, retry_from, report_path):
    return {
        "success": False,
        "status": "blocked",
        "stage": stage,
        "error": {
            "problem": problem,
            "evidence": evidence,
            "recommended_fix": recommended_fix,
            "retry_from": retry_from,
        },
        "report_path": report_path,
    }


def failed(stage, problem, evidence, report_path):
    return {
        "success": False,
        "status": "failed",
        "stage": stage,
        "error": {
            "problem": problem,
            "evidence": evidence,
        },
        "report_path": report_path,
    }


def complete(stage, data):
    return {"success": True, "status": "complete", "stage": stage, "data": data}


def partial(stage, data):
    return {"success": True, "status": "partial", "stage": stage, "data": data}


def compact_payload(payload, verbosity="summary"):
    if verbosity == "diagnostic":
        return payload
    if isinstance(payload, dict):
        return {
            key: compact_payload(value, verbosity=verbosity)
            for key, value in payload.items()
            if key not in LARGE_DETAIL_KEYS
        }
    if isinstance(payload, list):
        return [compact_payload(item, verbosity=verbosity) for item in payload]
    return payload


def sample_frames(start, end, count=5):
    lo, hi = sorted((int(start), int(end)))
    count = max(int(count), 1)
    if lo == hi or count == 1:
        return [lo]
    if hi - lo + 1 <= count:
        return list(range(lo, hi + 1))

    span = hi - lo
    frames = {round(lo + (span * idx / (count - 1))) for idx in range(count)}
    return sorted(frames)


def evaluate_frame_thresholds(
    summary,
    *,
    max_position_error_m=0.01,
    max_rotation_error_deg=5.0,
    min_pass_rate=0.80,
):
    pair_count = int(summary.get("pair_count", 0) or 0)
    pass_count = int(summary.get("pass_count", 0) or 0)
    pass_rate = pass_count / pair_count if pair_count else 0.0

    violations = []
    position_error = float(summary.get("overall_max_err", 0.0) or 0.0)
    if position_error > max_position_error_m:
        violations.append(
            "position error "
            f"{position_error * 1000:.3f}mm exceeds {max_position_error_m * 1000:.3f}mm"
        )

    rotation_error = float(summary.get("overall_rot_max_deg", 0.0) or 0.0)
    if rotation_error > max_rotation_error_deg:
        violations.append(
            f"rotation error {rotation_error:.3f}deg exceeds {max_rotation_error_deg:.3f}deg"
        )

    if pass_rate < min_pass_rate:
        violations.append(f"pass rate {pass_rate:.1%} is below {min_pass_rate:.1%}")

    return {"ok": not violations, "violations": violations, "pass_rate": pass_rate}


def select_core_pairs(pairs, limit=8):
    selected = []
    for role in CORE_ROLE_PRIORITY:
        for pair in pairs:
            if pair.get("role") != role:
                continue
            source = pair.get("source")
            target = pair.get("target")
            if source and target:
                selected.append((source, target))
                if len(selected) >= limit:
                    return selected
    return selected


def build_report_path(blend_file, report_dir, timestamp):
    stem = Path(blend_file).stem or "untitled"
    safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("_") or "untitled"
    return str(Path(report_dir) / f"{safe_stem}_{timestamp}.json")


def validate_required_roles(pairs):
    present = {pair.get("role") for pair in pairs if pair.get("role")}
    missing = []
    for label, accepted_roles in REQUIRED_ROLE_GROUPS:
        if present.isdisjoint(accepted_roles):
            missing.append("root" if label == "root_or_trajectory" else label)
    return {"ok": not missing, "missing_roles": missing}

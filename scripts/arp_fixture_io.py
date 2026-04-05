"""
arp_convert_addon에서 분리한 regression fixture I/O 헬퍼.

프로젝트 루트 탐색, fixture JSON 로드, Preview Armature에 역할 적용 등
회귀 테스트 파이프라인에서 사용하는 함수들을 담는다.
"""

import json
import os

import bpy


def _resolve_project_root():
    from arp_convert_addon import _PROJECT_RESOURCE_DIRS, _ensure_scripts_path

    script_dir = _ensure_scripts_path() or os.path.dirname(os.path.abspath(__file__))
    current = os.path.abspath(script_dir)

    for _ in range(6):
        if any(os.path.isdir(os.path.join(current, name)) for name in _PROJECT_RESOURCE_DIRS):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    if os.path.basename(script_dir) == "scripts":
        return os.path.dirname(script_dir)
    return script_dir


def _resolve_regression_path(raw_path):
    if not raw_path:
        return ""
    if os.path.isabs(raw_path):
        return raw_path
    return os.path.normpath(os.path.join(_resolve_project_root(), raw_path))


def _default_regression_report_dir():
    return os.path.join(_resolve_project_root(), "regression_reports")


def _load_regression_fixture(fixture_path):
    from arp_convert_addon import ROLE_IDS

    resolved_path = _resolve_regression_path(fixture_path)
    if not resolved_path or not os.path.exists(resolved_path):
        raise FileNotFoundError(f"Fixture JSON 미발견: {resolved_path or fixture_path}")

    with open(resolved_path, encoding="utf-8") as f:
        data = json.load(f)

    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise ValueError("Fixture JSON에는 'roles' 객체가 필요합니다.")

    normalized_roles = {}
    for role, bone_names in roles.items():
        if role not in ROLE_IDS:
            raise ValueError(f"지원하지 않는 role: {role}")
        if not isinstance(bone_names, list) or not all(
            isinstance(name, str) for name in bone_names
        ):
            raise ValueError(f"role '{role}'의 값은 문자열 리스트여야 합니다.")
        normalized_roles[role] = bone_names

    apply_mode = str(data.get("apply_mode", "replace")).lower()
    if apply_mode not in {"replace", "overlay"}:
        raise ValueError("apply_mode는 'replace' 또는 'overlay'여야 합니다.")

    return {
        "path": resolved_path,
        "description": data.get("description", ""),
        "apply_mode": apply_mode,
        "roles": normalized_roles,
    }


def _apply_fixture_roles(context, preview_obj, fixture_data):
    from arp_foot_guides import (
        FOOT_ROLES,
        _create_foot_guides_for_role,
        _set_preview_pose_bone_role,
    )
    from skeleton_analyzer import ROLE_COLORS, ROLE_PROP_KEY

    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="DESELECT")
    preview_obj.select_set(True)
    context.view_layer.objects.active = preview_obj
    bpy.ops.object.mode_set(mode="POSE")

    if fixture_data["apply_mode"] == "replace":
        for pbone in preview_obj.pose.bones:
            _set_preview_pose_bone_role(pbone, "unmapped", ROLE_COLORS, ROLE_PROP_KEY)

    assigned = {}
    duplicate_bones = []
    missing_bones = []
    foot_roles = {}

    for role, bone_names in fixture_data["roles"].items():
        for bone_name in bone_names:
            pbone = preview_obj.pose.bones.get(bone_name)
            if pbone is None:
                missing_bones.append(bone_name)
                continue

            previous_role = assigned.get(bone_name)
            if previous_role and previous_role != role:
                duplicate_bones.append(
                    {
                        "bone": bone_name,
                        "previous_role": previous_role,
                        "new_role": role,
                    }
                )

            _set_preview_pose_bone_role(pbone, role, ROLE_COLORS, ROLE_PROP_KEY)
            assigned[bone_name] = role

            if role in FOOT_ROLES:
                foot_roles.setdefault(role, []).append(bone_name)

    bpy.ops.object.mode_set(mode="OBJECT")

    guide_count = 0
    for role, foot_bones in foot_roles.items():
        guide_count += _create_foot_guides_for_role(
            context,
            preview_obj,
            foot_bones,
            role,
            ROLE_PROP_KEY,
        )

    role_counts = {}
    for role in assigned.values():
        role_counts[role] = role_counts.get(role, 0) + 1

    return {
        "assigned_count": len(assigned),
        "guide_count": guide_count,
        "missing_bones": missing_bones,
        "duplicate_bones": duplicate_bones,
        "role_counts": role_counts,
        "apply_mode": fixture_data["apply_mode"],
    }

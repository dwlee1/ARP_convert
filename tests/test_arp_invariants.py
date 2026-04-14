"""ARP invariant tests.

These tests enforce project rules automatically when running `pytest tests/ -v`.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# Canonical role set shared by skeleton_analyzer.py and arp_convert_addon.py.
CANONICAL_ROLES = {
    "root",
    "spine",
    "neck",
    "head",
    "back_leg_l",
    "back_leg_r",
    "back_foot_l",
    "back_foot_r",
    "front_leg_l",
    "front_leg_r",
    "front_foot_l",
    "front_foot_r",
    "ear_l",
    "ear_r",
    "tail",
    "trajectory",
    "unmapped",
}


def _extract_dict_keys_from_source(filepath: Path, var_name: str) -> set[str]:
    """Extract dict keys from a top-level assignment."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    if isinstance(node.value, ast.Dict):
                        return {
                            k.value
                            for k in node.value.keys
                            if isinstance(k, ast.Constant) and isinstance(k.value, str)
                        }
    return set()


def _extract_list_first_elements(filepath: Path, var_name: str) -> set[str]:
    """Extract the first item of each tuple in a top-level list assignment."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == var_name:
                    if isinstance(node.value, ast.List):
                        result = set()
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Tuple) and elt.elts:
                                first = elt.elts[0]
                                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                                    result.add(first.value)
                        return result
    return set()


def _call_chain_parts(
    node: ast.AST, aliases: dict[str, tuple[str, ...]] | None = None
) -> tuple[str, ...] | None:
    """Resolve a dotted call target, expanding aliases when possible."""
    aliases = aliases or {}
    raw = _raw_chain_parts(node)
    if raw is None:
        return None
    return _expand_alias_chain(raw, aliases)


def _raw_chain_parts(node: ast.AST) -> tuple[str, ...] | None:
    """Return a dotted chain without alias expansion."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
        return tuple(reversed(parts))
    return None


def _expand_alias_chain(
    chain: tuple[str, ...], aliases: dict[str, tuple[str, ...]], seen: set[str] | None = None
) -> tuple[str, ...]:
    """Expand aliases recursively until the chain is fully resolved."""
    if not chain:
        return chain

    seen = set() if seen is None else seen
    head, *tail = chain
    if head in aliases and head not in seen:
        seen.add(head)
        return _expand_alias_chain(aliases[head], aliases, seen) + tuple(tail)
    return chain


def _collect_simple_aliases(tree: ast.AST) -> dict[str, tuple[str, ...]]:
    """Collect simple dotted aliases like `ops = bpy.ops.object`."""
    aliases: dict[str, tuple[str, ...]] = {}
    assign_nodes: list[ast.AST] = list(ast.walk(tree))
    for node in assign_nodes:
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
            targets = [node.target]
        else:
            continue

        chain = _raw_chain_parts(value)
        if chain is None:
            continue

        for target in targets:
            if isinstance(target, ast.Name):
                aliases[target.id] = chain
    return aliases


def _find_matching_call_chains(filepath: Path, prefixes: tuple[tuple[str, ...], ...]) -> list[str]:
    """Return dotted call chains whose prefix matches any forbidden pattern."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    aliases = _collect_simple_aliases(tree)
    hits: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _call_chain_parts(node.func, aliases)
        if chain and any(_chain_has_prefix(chain, prefix) for prefix in prefixes):
            hits.append(".".join(chain))
    return hits


def _chain_has_prefix(chain: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    """Return True when `chain` starts with `prefix`, allowing the tail to widen."""
    if len(chain) < len(prefix):
        return False
    for index, expected in enumerate(prefix):
        actual = chain[index]
        if index == len(prefix) - 1:
            return actual.startswith(expected)
        if actual != expected:
            return False
    return True


def _target_has_attr_chain(node: ast.AST, attr_names: set[str]) -> bool:
    """Return True when an assignment target touches any forbidden attribute chain."""
    if isinstance(node, ast.Attribute):
        if node.attr in attr_names:
            return True
        return _target_has_attr_chain(node.value, attr_names)
    if isinstance(node, ast.Subscript):
        return _target_has_attr_chain(node.value, attr_names)
    if isinstance(node, ast.Tuple | ast.List):
        return any(_target_has_attr_chain(elt, attr_names) for elt in node.elts)
    if isinstance(node, ast.Starred):
        return _target_has_attr_chain(node.value, attr_names)
    return False


def _find_target_attribute_mutation_hits(filepath: Path, attr_names: set[str]) -> list[str]:
    """Return assignment lines that mutate any forbidden attribute chain."""
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    source_lines = source.splitlines()
    hits: list[str] = []

    for node in ast.walk(tree):
        targets: list[ast.AST]
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            targets = [node.target]
        else:
            continue

        if any(_target_has_attr_chain(target, attr_names) for target in targets):
            line = source_lines[node.lineno - 1].strip() if node.lineno else ""
            hits.append(f"{filepath.name}:{node.lineno}: {line}")

    return hits


class TestRoleConsistency:
    """Keep role definitions aligned across modules."""

    def test_role_colors_matches_canonical(self):
        role_colors_keys = _extract_dict_keys_from_source(
            SCRIPTS_DIR / "skeleton_detection.py", "ROLE_COLORS"
        )
        assert role_colors_keys, "ROLE_COLORS not found"
        assert role_colors_keys == CANONICAL_ROLES, (
            f"ROLE_COLORS mismatch "
            f"added={role_colors_keys - CANONICAL_ROLES}, "
            f"missing={CANONICAL_ROLES - role_colors_keys}"
        )

    def test_role_items_matches_canonical(self):
        role_items_ids = _extract_list_first_elements(
            SCRIPTS_DIR / "arp_ops_roles.py", "ROLE_ITEMS"
        )
        assert role_items_ids, "ROLE_ITEMS not found"
        assert role_items_ids == CANONICAL_ROLES, (
            f"ROLE_ITEMS mismatch "
            f"added={role_items_ids - CANONICAL_ROLES}, "
            f"missing={CANONICAL_ROLES - role_items_ids}"
        )


class TestNoRefBoneCreation:
    """Disallow direct edit_bones.new() creation of *_ref bones."""

    REF_PATTERN = re.compile(r'edit_bones\.new\([^)]*["\'][\w]*_ref[\w]*["\']')

    def test_no_ref_bone_string_literals(self):
        violations = []
        for py_file in SCRIPTS_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(source.splitlines(), 1):
                if self.REF_PATTERN.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")
        assert not violations, (
            "edit_bones.new() direct *_ref name usage is forbidden "
            "(use ARP native set_* functions):\n" + "\n".join(violations)
        )


class TestNoHardcodedPaths:
    """Disallow hardcoded Windows paths in scripts/."""

    HARDCODED_PATH = re.compile(r'["\'][A-Z]:\\Users\\', re.IGNORECASE)
    EXCLUDED_FILES = {"extract_test_fixture.py", "inspect_rig.py", "diagnose_arp_operators.py"}

    def test_no_hardcoded_windows_paths(self):
        violations = []
        for py_file in SCRIPTS_DIR.glob("*.py"):
            if py_file.name in self.EXCLUDED_FILES:
                continue
            source = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(source.splitlines(), 1):
                if self.HARDCODED_PATH.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")
        assert not violations, "Hardcoded Windows paths found in scripts/:\n" + "\n".join(
            violations
        )


class TestControllerAutoSizeGuardrails:
    """Ensure controller auto-size code stays on the safe path."""

    def test_build_rig_wires_controller_auto_size_after_match_to_rig(self):
        filepath = SCRIPTS_DIR / "arp_ops_build.py"
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_helper_names = set()
        execute_node = None
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "arp_build_helpers":
                imported_helper_names.update(alias.name for alias in node.names)
            if isinstance(node, ast.ClassDef) and node.name == "ARPCONV_OT_BuildRig":
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == "execute":
                        execute_node = child

        assert execute_node is not None, "ARPCONV_OT_BuildRig.execute not found"
        assert {
            "_apply_controller_auto_size",
            "_build_controller_size_targets_per_bone",
            "_collect_arp_ctrl_bone_lengths",
        }.issubset(imported_helper_names)

        ordered_calls: list[tuple[int, int, str]] = []
        for node in ast.walk(execute_node):
            if not isinstance(node, ast.Call):
                continue
            chain = _call_chain_parts(node.func)
            if chain:
                ordered_calls.append((node.lineno, node.col_offset, ".".join(chain)))

        ordered_calls.sort()

        def _line_for(call_name: str, *, after_line: int) -> int:
            for lineno, _, name in ordered_calls:
                if name == call_name and lineno > after_line:
                    return lineno
            raise AssertionError(f"{call_name} not found after line {after_line}")

        match_line = _line_for("run_arp_operator", after_line=200)
        discover_line = _line_for("discover_arp_ctrl_map", after_line=match_line)
        ik_line = _line_for("_apply_ik_to_foot_ctrl", after_line=discover_line)
        lengths_line = _line_for("_collect_arp_ctrl_bone_lengths", after_line=discover_line)
        targets_line = _line_for("_build_controller_size_targets_per_bone", after_line=lengths_line)
        apply_line = _line_for("_apply_controller_auto_size", after_line=targets_line)

        assert match_line < discover_line < ik_line < lengths_line < targets_line < apply_line

    def test_no_shape_object_scale_mutation(self):
        scale_hits = _find_target_attribute_mutation_hits(
            SCRIPTS_DIR / "arp_build_helpers.py",
            {"scale"},
        )

        assert not scale_hits, "Forbidden .scale target mutation found:\n" + "\n".join(scale_hits)

    def test_no_apply_transforms_or_set_custom_shape_operator(self):
        build_files = [SCRIPTS_DIR / "arp_build_helpers.py", SCRIPTS_DIR / "arp_ops_build.py"]

        apply_transform_hits: list[str] = []
        custom_shape_hits: list[str] = []

        for py_file in build_files:
            apply_transform_hits.extend(
                _find_matching_call_chains(py_file, (("bpy", "ops", "object", "transform_apply"),))
            )
            custom_shape_hits.extend(
                _find_matching_call_chains(py_file, (("bpy", "ops", "pose", "custom_shape"),))
            )

        assert not apply_transform_hits, (
            "Forbidden transform_apply operator calls found:\n" + "\n".join(apply_transform_hits)
        )
        assert not custom_shape_hits, (
            "Forbidden pose.custom_shape operator calls found:\n" + "\n".join(custom_shape_hits)
        )

    def test_no_custom_shape_property_assignment(self):
        build_files = [SCRIPTS_DIR / "arp_build_helpers.py", SCRIPTS_DIR / "arp_ops_build.py"]
        forbidden_attrs = {"custom_shape", "custom_shape_transform"}
        assignment_hits: list[str] = []

        for py_file in build_files:
            assignment_hits.extend(_find_target_attribute_mutation_hits(py_file, forbidden_attrs))

        assert not assignment_hits, (
            "Forbidden custom shape property assignments found:\n" + "\n".join(assignment_hits)
        )

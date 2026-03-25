"""ARP 도메인 불변 조건 테스트.

에이전트(Claude Code / Codex)가 코드를 수정한 뒤 `pytest tests/ -v`를 실행하면
도메인 규칙 위반을 자동으로 잡아준다.
"""

import ast
import re
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# ─── 정규 역할 이름 집합 ─────────────────────────────────────
# skeleton_analyzer.py의 ROLE_COLORS와 arp_convert_addon.py의 ROLE_ITEMS가
# 동일한 역할 집합을 사용해야 한다.
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
    "unmapped",
}


def _extract_dict_keys_from_source(filepath: Path, var_name: str) -> set[str]:
    """소스 파일에서 딕셔너리 변수의 키 집합을 추출한다."""
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
    """소스 파일에서 리스트[튜플] 변수의 첫 번째 원소 집합을 추출한다."""
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


# ─── 테스트 1: 역할 이름 일관성 ───────────────────────────────
class TestRoleConsistency:
    """skeleton_analyzer.ROLE_COLORS와 arp_convert_addon.ROLE_ITEMS의 역할 집합이 일치."""

    def test_role_colors_matches_canonical(self):
        role_colors_keys = _extract_dict_keys_from_source(
            SCRIPTS_DIR / "skeleton_analyzer.py", "ROLE_COLORS"
        )
        assert role_colors_keys, "ROLE_COLORS를 파싱할 수 없음"
        assert role_colors_keys == CANONICAL_ROLES, (
            f"ROLE_COLORS 불일치: "
            f"추가={role_colors_keys - CANONICAL_ROLES}, "
            f"누락={CANONICAL_ROLES - role_colors_keys}"
        )

    def test_role_items_matches_canonical(self):
        role_items_ids = _extract_list_first_elements(
            SCRIPTS_DIR / "arp_convert_addon.py", "ROLE_ITEMS"
        )
        assert role_items_ids, "ROLE_ITEMS를 파싱할 수 없음"
        assert role_items_ids == CANONICAL_ROLES, (
            f"ROLE_ITEMS 불일치: "
            f"추가={role_items_ids - CANONICAL_ROLES}, "
            f"누락={CANONICAL_ROLES - role_items_ids}"
        )


# ─── 테스트 2: edit_bones.new()로 ARP ref 본 생성 금지 ────────
class TestNoRefBoneCreation:
    """edit_bones.new() 호출에서 '_ref' 패턴 본 이름 생성을 금지한다.

    허용되는 사용:
    - 커스텀 본 (원본 이름 유지, custom_bone 프로퍼티로 태깅)
    - Preview armature 본 (bone_name 등)
    - heel / bank 보조 본
    - __virtual_neck__ 등 가상 본
    """

    # _ref 패턴의 문자열 리터럴이 edit_bones.new() 인자로 사용되는 경우 차단
    REF_PATTERN = re.compile(r'edit_bones\.new\([^)]*["\'][\w]*_ref[\w]*["\']')

    def test_no_ref_bone_string_literals(self):
        """edit_bones.new("..._ref...") 패턴의 직접 문자열 사용 금지."""
        violations = []
        for py_file in SCRIPTS_DIR.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for i, line in enumerate(source.splitlines(), 1):
                if self.REF_PATTERN.search(line):
                    violations.append(f"{py_file.name}:{i}: {line.strip()}")
        assert not violations, (
            "edit_bones.new()에 _ref 본 이름 직접 사용 금지 "
            "(ARP 네이티브 set_* 함수 사용 필요):\n" + "\n".join(violations)
        )


# ─── 테스트 3: 하드코딩된 Windows 경로 금지 ──────────────────
class TestNoHardcodedPaths:
    """scripts/ 내에 하드코딩된 사용자 경로가 없어야 한다."""

    HARDCODED_PATH = re.compile(r'["\'][A-Z]:\\Users\\', re.IGNORECASE)
    # 유틸리티/진단 스크립트는 로컬 경로 참조 허용
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
        assert not violations, "scripts/ 내 하드코딩된 Windows 경로 발견:\n" + "\n".join(violations)

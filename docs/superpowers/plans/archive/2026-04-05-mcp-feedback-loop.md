# MCP 피드백 루프 확장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** F12 작업에서 반복 사용된 3가지 검증 패턴(bone_pairs 조회, 프레임별 월드 위치 비교, 프리셋 본 이름 조회)을 `mcp_bridge.py`에 승격하고, 순수 Python 로직을 `scripts/mcp_verify.py`로 분리해 pytest로 커버하고, 사용 레시피를 `docs/MCP_Recipes.md`에 정리한다.

**Architecture:** TDD. 먼저 순수 헬퍼 4개의 pytest 17개를 작성해 실패 확인(Red) → 헬퍼 구현해 통과(Green) → mcp_bridge에 3개 브릿지 함수 추가(각각 독립 커밋) → MCP 스모크 테스트로 Blender에서 수동 검증 → 레시피 문서 작성 → ProjectPlan 갱신.

**Tech Stack:** Python 3.11, pytest, Blender 4.5 bpy (bridge 함수만), BlenderMCP 브릿지, Auto-Rig Pro dog preset.

**Spec:** `docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md`

**Pre-flight 확인 (이미 완료)**:
- 현재 `scripts/mcp_bridge.py`는 8개 함수(`mcp_scene_summary`, `mcp_create_preview`, `mcp_build_rig`, `mcp_run_regression`, `mcp_get_bone_roles`, `mcp_set_bone_role`, `mcp_validate_weights`, `mcp_bake_animation`) 보유
- `_reload()` 내부에서 `skeleton_analyzer`, `arp_utils`, `weight_transfer_rules`만 리로드 → `mcp_verify` 추가 필요
- 기존 테스트 파일 스타일: 클래스 기반(`TestXxx`), `import module as alias` 패턴

**브랜치**: `feat/mcp-feedback-loop` (새로 생성)

---

## Task 1: `mcp_verify.py` 스켈레톤 + pytest (Red)

**Files:**
- Create: `scripts/mcp_verify.py`
- Create: `tests/test_mcp_verify.py`

- [ ] **Step 1: `scripts/mcp_verify.py` 스켈레톤 작성 (NotImplementedError 스텁)**

Create file `scripts/mcp_verify.py`:

```python
"""
mcp_bridge에서 분리한 순수 데이터 가공 로직.

bpy 의존 없이 단위 테스트 가능. mcp_bridge의 각 함수는
(1) bpy 호출로 raw 데이터 수집 → (2) 이 모듈의 헬퍼로 가공 → (3) JSON 출력
구조를 가진다.
"""


def filter_pairs_by_role(bone_pairs, target_to_role, role_filter=None):
    """bone_pairs를 역할별로 필터링한다.

    Args:
        bone_pairs: [(src, tgt, is_custom), ...] 리스트 (3-tuple 또는 list).
        target_to_role: {target_bone_name: role_or_None} 매핑 (호출부에서 구성).
        role_filter: None이면 전체. 문자열이면 정확 매칭. list/set이면 포함 매칭.

    Returns:
        [{"source": str, "target": str, "is_custom": bool, "role": str|None}, ...]
    """
    raise NotImplementedError


def compute_position_stats(distances):
    """거리(float) 리스트에서 min/max/mean/count를 집계한다.

    빈 리스트는 {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'count': 0}을 반환한다.
    """
    raise NotImplementedError


def format_comparison_report(pair_results):
    """프레임 비교 결과 리스트를 읽기 쉬운 멀티라인 문자열로 변환한다.

    입력: [{"src": str, "arp": str, "max_err": float, "mean_err": float, ...}, ...]
    빈 입력은 "no pairs compared"를 반환한다.
    """
    raise NotImplementedError


def match_bone_names(bone_names, pattern):
    """본 이름 리스트에서 정규식(re.search) 매칭되는 항목을 정렬 반환한다.

    pattern이 None이면 전체를 정렬 반환한다. 잘못된 정규식은 re.error 전파.
    """
    raise NotImplementedError
```

- [ ] **Step 2: `tests/test_mcp_verify.py` 작성 (17 tests)**

Create file `tests/test_mcp_verify.py`:

```python
"""
mcp_verify 순수 헬퍼 pytest.
"""

import pytest

import mcp_verify as mv


# ─────────────────────────────────────────────────────────────
# TestFilterPairsByRole
# ─────────────────────────────────────────────────────────────


class TestFilterPairsByRole:
    def _sample_pairs(self):
        # (src, tgt, is_custom) 형식
        return [
            ("DEF-thigh_L", "c_thigh_b.l", False),
            ("DEF-thigh_R", "c_thigh_b.r", False),
            ("DEF-toe_L", "c_foot_fk.l", False),
            ("DEF-eye_L", "DEF-eye_L", True),
        ]

    def _sample_target_to_role(self):
        return {
            "c_thigh_b.l": "back_leg_l",
            "c_thigh_b.r": "back_leg_r",
            "c_foot_fk.l": "back_foot_l",
            # DEF-eye_L은 target_to_role에 없음 → role=None
        }

    def test_none_filter_returns_all(self):
        pairs = self._sample_pairs()
        mapping = self._sample_target_to_role()
        result = mv.filter_pairs_by_role(pairs, mapping, role_filter=None)
        assert len(result) == 4
        assert result[0]["source"] == "DEF-thigh_L"
        assert result[0]["target"] == "c_thigh_b.l"
        assert result[0]["role"] == "back_leg_l"
        assert result[0]["is_custom"] is False

    def test_string_filter_exact_match(self):
        pairs = self._sample_pairs()
        mapping = self._sample_target_to_role()
        result = mv.filter_pairs_by_role(pairs, mapping, role_filter="back_leg_l")
        assert len(result) == 1
        assert result[0]["target"] == "c_thigh_b.l"

    def test_list_filter_multi_role(self):
        pairs = self._sample_pairs()
        mapping = self._sample_target_to_role()
        result = mv.filter_pairs_by_role(
            pairs, mapping, role_filter=["back_leg_l", "back_foot_l"]
        )
        assert len(result) == 2
        targets = {r["target"] for r in result}
        assert targets == {"c_thigh_b.l", "c_foot_fk.l"}

    def test_empty_pairs_returns_empty(self):
        result = mv.filter_pairs_by_role([], {}, role_filter=None)
        assert result == []

    def test_pair_with_unknown_target_has_none_role(self):
        pairs = [("DEF-eye_L", "DEF-eye_L", True)]
        mapping = {}
        result = mv.filter_pairs_by_role(pairs, mapping, role_filter=None)
        assert len(result) == 1
        assert result[0]["role"] is None
        assert result[0]["is_custom"] is True


# ─────────────────────────────────────────────────────────────
# TestComputePositionStats
# ─────────────────────────────────────────────────────────────


class TestComputePositionStats:
    def test_empty_returns_zero_stats(self):
        result = mv.compute_position_stats([])
        assert result == {"min": 0.0, "max": 0.0, "mean": 0.0, "count": 0}

    def test_uniform_distances(self):
        result = mv.compute_position_stats([1.0, 1.0, 1.0])
        assert result["min"] == 1.0
        assert result["max"] == 1.0
        assert result["mean"] == 1.0
        assert result["count"] == 3

    def test_mixed_distances(self):
        result = mv.compute_position_stats([1.0, 2.0, 3.0])
        assert result["min"] == 1.0
        assert result["max"] == 3.0
        assert result["mean"] == 2.0
        assert result["count"] == 3

    def test_single_element(self):
        result = mv.compute_position_stats([5.0])
        assert result["min"] == 5.0
        assert result["max"] == 5.0
        assert result["mean"] == 5.0
        assert result["count"] == 1


# ─────────────────────────────────────────────────────────────
# TestFormatComparisonReport
# ─────────────────────────────────────────────────────────────


class TestFormatComparisonReport:
    def test_report_contains_pair_names(self):
        data = [
            {"src": "DEF-thigh_L", "arp": "c_thigh_b.l", "max_err": 0.0, "mean_err": 0.0}
        ]
        result = mv.format_comparison_report(data)
        assert "DEF-thigh_L" in result
        assert "c_thigh_b.l" in result

    def test_report_shows_max_error(self):
        data = [
            {"src": "A", "arp": "B", "max_err": 0.00364, "mean_err": 0.00200}
        ]
        result = mv.format_comparison_report(data)
        assert "0.00364" in result

    def test_empty_results_returns_fallback_text(self):
        result = mv.format_comparison_report([])
        assert result == "no pairs compared"


# ─────────────────────────────────────────────────────────────
# TestMatchBoneNames
# ─────────────────────────────────────────────────────────────


class TestMatchBoneNames:
    def test_none_pattern_returns_sorted_all(self):
        result = mv.match_bone_names(["b", "a", "c"], None)
        assert result == ["a", "b", "c"]

    def test_prefix_match(self):
        bones = ["c_thigh_b.l", "c_leg_fk.l", "c_thigh_b.r"]
        result = mv.match_bone_names(bones, r"^c_thigh_b")
        assert result == ["c_thigh_b.l", "c_thigh_b.r"]

    def test_regex_alternation(self):
        result = mv.match_bone_names(["alpha", "beta", "gamma"], r"^(alpha|gamma)$")
        assert result == ["alpha", "gamma"]

    def test_escape_dot(self):
        result = mv.match_bone_names(["c_thigh_b.l", "c_thigh_bxl"], r"^c_thigh_b\.l$")
        assert result == ["c_thigh_b.l"]

    def test_no_match_returns_empty(self):
        result = mv.match_bone_names(["a", "b"], r"^z")
        assert result == []
```

- [ ] **Step 3: pytest로 실패 확인 (Red 상태)**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_mcp_verify.py -v
```

Expected: **17 errors (NotImplementedError)** 또는 17 failed. 스텁이 NotImplementedError를 raise하므로 모두 실패해야 정상. 만약 하나라도 pass면 스텁/테스트 작성 오류이므로 중단 후 재조사.

- [ ] **Step 4: 전체 회귀 (기존 테스트 영향 없음 확인)**

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: **103 passed, 17 failed** (기존 103 + 신규 17 실패). `test_mcp_verify.py` 외 기존 테스트는 모두 통과해야 한다. 기존 테스트가 하나라도 깨졌으면 중단 후 조사.

- [ ] **Step 5: Red 커밋**

```bash
git add scripts/mcp_verify.py tests/test_mcp_verify.py
git commit -m "$(cat <<'EOF'
test(mcp): mcp_verify 헬퍼 4개 + pytest 17개 작성 (TDD Red)

scripts/mcp_verify.py에 스텁(NotImplementedError)만 배치하고
tests/test_mcp_verify.py에 17개 테스트 작성. 모두 실패 상태.

다음 Task에서 헬퍼를 구현해 Green 상태로 전환.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

---

## Task 2: `filter_pairs_by_role` 구현

**Files:**
- Modify: `scripts/mcp_verify.py` (`filter_pairs_by_role` 함수)

- [ ] **Step 1: Edit — `filter_pairs_by_role` 구현**

Edit `scripts/mcp_verify.py`:
- old_string:
```python
def filter_pairs_by_role(bone_pairs, target_to_role, role_filter=None):
    """bone_pairs를 역할별로 필터링한다.

    Args:
        bone_pairs: [(src, tgt, is_custom), ...] 리스트 (3-tuple 또는 list).
        target_to_role: {target_bone_name: role_or_None} 매핑 (호출부에서 구성).
        role_filter: None이면 전체. 문자열이면 정확 매칭. list/set이면 포함 매칭.

    Returns:
        [{"source": str, "target": str, "is_custom": bool, "role": str|None}, ...]
    """
    raise NotImplementedError
```
- new_string:
```python
def filter_pairs_by_role(bone_pairs, target_to_role, role_filter=None):
    """bone_pairs를 역할별로 필터링한다.

    Args:
        bone_pairs: [(src, tgt, is_custom), ...] 리스트 (3-tuple 또는 list).
        target_to_role: {target_bone_name: role_or_None} 매핑 (호출부에서 구성).
        role_filter: None이면 전체. 문자열이면 정확 매칭. list/set이면 포함 매칭.

    Returns:
        [{"source": str, "target": str, "is_custom": bool, "role": str|None}, ...]
    """
    if role_filter is None:
        filter_set = None
    elif isinstance(role_filter, str):
        filter_set = {role_filter}
    else:
        filter_set = set(role_filter)

    result = []
    for pair in bone_pairs:
        src = pair[0]
        tgt = pair[1]
        is_custom = bool(pair[2]) if len(pair) > 2 else False
        role = target_to_role.get(tgt)
        if filter_set is not None and role not in filter_set:
            continue
        result.append(
            {"source": src, "target": tgt, "is_custom": is_custom, "role": role}
        )
    return result
```

- [ ] **Step 2: 해당 테스트 클래스만 실행해 통과 확인**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_mcp_verify.py::TestFilterPairsByRole -v
```

Expected: **5 passed**. 하나라도 실패면 구현 재검토.

---

## Task 3: `compute_position_stats` 구현

**Files:**
- Modify: `scripts/mcp_verify.py` (`compute_position_stats` 함수)

- [ ] **Step 1: Edit — `compute_position_stats` 구현**

Edit `scripts/mcp_verify.py`:
- old_string:
```python
def compute_position_stats(distances):
    """거리(float) 리스트에서 min/max/mean/count를 집계한다.

    빈 리스트는 {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'count': 0}을 반환한다.
    """
    raise NotImplementedError
```
- new_string:
```python
def compute_position_stats(distances):
    """거리(float) 리스트에서 min/max/mean/count를 집계한다.

    빈 리스트는 {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'count': 0}을 반환한다.
    """
    if not distances:
        return {"min": 0.0, "max": 0.0, "mean": 0.0, "count": 0}
    return {
        "min": min(distances),
        "max": max(distances),
        "mean": sum(distances) / len(distances),
        "count": len(distances),
    }
```

- [ ] **Step 2: 해당 테스트 클래스 실행**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_mcp_verify.py::TestComputePositionStats -v
```

Expected: **4 passed**.

---

## Task 4: `format_comparison_report` 구현

**Files:**
- Modify: `scripts/mcp_verify.py` (`format_comparison_report` 함수)

- [ ] **Step 1: Edit — `format_comparison_report` 구현**

Edit `scripts/mcp_verify.py`:
- old_string:
```python
def format_comparison_report(pair_results):
    """프레임 비교 결과 리스트를 읽기 쉬운 멀티라인 문자열로 변환한다.

    입력: [{"src": str, "arp": str, "max_err": float, "mean_err": float, ...}, ...]
    빈 입력은 "no pairs compared"를 반환한다.
    """
    raise NotImplementedError
```
- new_string:
```python
def format_comparison_report(pair_results):
    """프레임 비교 결과 리스트를 읽기 쉬운 멀티라인 문자열로 변환한다.

    입력: [{"src": str, "arp": str, "max_err": float, "mean_err": float, ...}, ...]
    빈 입력은 "no pairs compared"를 반환한다.
    """
    if not pair_results:
        return "no pairs compared"
    lines = [f"{'src_bone':<25} -> {'arp_bone':<30} | {'max_err':>9} | {'mean_err':>9}"]
    lines.append("-" * 85)
    for r in pair_results:
        src = str(r.get("src", ""))
        arp = str(r.get("arp", ""))
        max_err = float(r.get("max_err", 0.0))
        mean_err = float(r.get("mean_err", 0.0))
        lines.append(f"{src:<25} -> {arp:<30} | {max_err:>9.5f} | {mean_err:>9.5f}")
    return "\n".join(lines)
```

- [ ] **Step 2: 해당 테스트 클래스 실행**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_mcp_verify.py::TestFormatComparisonReport -v
```

Expected: **3 passed**.

---

## Task 5: `match_bone_names` 구현 + 전체 Green 커밋

**Files:**
- Modify: `scripts/mcp_verify.py` (`match_bone_names` 함수)

- [ ] **Step 1: Edit — `match_bone_names` 구현**

Edit `scripts/mcp_verify.py`:
- old_string:
```python
def match_bone_names(bone_names, pattern):
    """본 이름 리스트에서 정규식(re.search) 매칭되는 항목을 정렬 반환한다.

    pattern이 None이면 전체를 정렬 반환한다. 잘못된 정규식은 re.error 전파.
    """
    raise NotImplementedError
```
- new_string:
```python
def match_bone_names(bone_names, pattern):
    """본 이름 리스트에서 정규식(re.search) 매칭되는 항목을 정렬 반환한다.

    pattern이 None이면 전체를 정렬 반환한다. 잘못된 정규식은 re.error 전파.
    """
    import re

    names = sorted(bone_names)
    if pattern is None:
        return names
    regex = re.compile(pattern)
    return [n for n in names if regex.search(n)]
```

- [ ] **Step 2: 전체 mcp_verify 테스트 실행**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_mcp_verify.py -v
```

Expected: **17 passed**.

- [ ] **Step 3: 전체 pytest 실행**

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: **120 passed** (기존 103 + 신규 17).

- [ ] **Step 4: Ruff 린트**

Run:
```
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```

Expected: `All checks passed!`

- [ ] **Step 5: Green 커밋**

```bash
git add scripts/mcp_verify.py
git commit -m "$(cat <<'EOF'
feat(mcp): mcp_verify 순수 헬퍼 4개 구현 (TDD Green)

filter_pairs_by_role, compute_position_stats, format_comparison_report,
match_bone_names 구현. 이전 커밋의 17개 테스트 모두 통과.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

---

## Task 6: `mcp_bridge.mcp_inspect_bone_pairs` 추가

**Files:**
- Modify: `scripts/mcp_bridge.py` (`_reload` 업데이트 + 파일 끝에 신규 함수)

- [ ] **Step 1: `_reload()`에 `mcp_verify` 추가**

Read `scripts/mcp_bridge.py` offset=36 limit=10 로 현재 `_reload` 확인.

Edit `scripts/mcp_bridge.py`:
- old_string:
```python
def _reload():
    """개발 중 모듈 리로드."""
    import importlib

    for mod_name in ["skeleton_analyzer", "arp_utils", "weight_transfer_rules"]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
```
- new_string:
```python
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
```

- [ ] **Step 2: `mcp_inspect_bone_pairs` 함수를 파일 끝에 추가**

Edit `scripts/mcp_bridge.py`:
- old_string (파일의 맨 마지막 줄을 기준으로 찾음): 먼저 Read로 파일 끝 20줄 확인 후, 마지막 함수(`mcp_bake_animation`의 종료) 뒤에 추가. 실제 파일 끝 부분의 정확한 형태를 Read로 확인한 뒤 그 뒤에 append.

아래 텍스트를 파일 끝에 추가한다 (기존 맨 마지막 함수의 마지막 줄 바로 뒤, 빈 줄 2개 다음):

```python


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
```

- [ ] **Step 3: import 문법 검증 (Blender 없이)**

Run:
```
.venv/Scripts/python.exe -m ruff check scripts/mcp_bridge.py
```

Expected: `All checks passed!` (bpy import가 module 레벨이라 Python 실행은 실패하지만 ruff 구문 검사는 통과)

- [ ] **Step 4: 커밋**

```bash
git add scripts/mcp_bridge.py
git commit -m "$(cat <<'EOF'
feat(mcp): mcp_inspect_bone_pairs 함수 추가

_reload에 mcp_verify 추가 + ARP bone_pairs 디코드 + 역할 필터 기능.
순수 로직은 mcp_verify.filter_pairs_by_role에 위임.

사용 예: F12 bake 후 back_leg_l 역할이 어느 컨트롤러에 매핑됐는지 확인.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

---

## Task 7: `mcp_bridge.mcp_compare_frames` 추가

**Files:**
- Modify: `scripts/mcp_bridge.py` (파일 끝에 신규 함수)

- [ ] **Step 1: `mcp_compare_frames` 함수를 파일 끝에 추가**

Edit `scripts/mcp_bridge.py` — 이전 Task에서 추가한 `mcp_inspect_bone_pairs` 함수 뒤에 다음을 append (빈 줄 2개 뒤):

```python


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
```

- [ ] **Step 2: Ruff 검증**

Run:
```
.venv/Scripts/python.exe -m ruff check scripts/mcp_bridge.py
```

Expected: `All checks passed!`

- [ ] **Step 3: 전체 pytest도 실행 (안전망)**

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: **120 passed** (mcp_bridge에 추가만 했으므로 회귀 없음).

- [ ] **Step 4: 커밋**

```bash
git add scripts/mcp_bridge.py
git commit -m "$(cat <<'EOF'
feat(mcp): mcp_compare_frames 함수 추가

소스와 ARP 본의 월드 위치를 지정 프레임에서 비교. 액션명 주어지면
소스에 '<name>', ARP에 '<name>_arp' 자동 할당. 순수 로직(통계, 리포트
포맷)은 mcp_verify에 위임.

사용 예: F12 Task 6에서 walk 액션 샘플 프레임으로 leg 오차 검증.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

---

## Task 8: `mcp_bridge.mcp_inspect_preset_bones` 추가

**Files:**
- Modify: `scripts/mcp_bridge.py` (파일 끝에 신규 함수)

- [ ] **Step 1: `mcp_inspect_preset_bones` 함수 추가**

Edit `scripts/mcp_bridge.py` — `mcp_compare_frames` 뒤에 append (빈 줄 2개 뒤):

```python


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
        loaded_armatures = []
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
```

- [ ] **Step 2: Ruff 검증**

Run:
```
.venv/Scripts/python.exe -m ruff check scripts/mcp_bridge.py
```

Expected: `All checks passed!`

- [ ] **Step 3: 전체 pytest (안전망)**

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -q
```

Expected: **120 passed**.

- [ ] **Step 4: 커밋**

```bash
git add scripts/mcp_bridge.py
git commit -m "$(cat <<'EOF'
feat(mcp): mcp_inspect_preset_bones 함수 추가

ARP 프리셋 .blend를 bpy.data.libraries.load로 읽고 본 이름을 정규식
필터와 함께 반환. _append_arp는 MCP 컨텍스트에서 overlay 에러가
발생하므로 libraries.load 경로를 사용. 로드된 armature data는 cleanup.

사용 예: F12 Task 5에서 c_toes_fk 실존 확인에 사용된 방법.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

---

## Task 9: MCP 스모크 테스트 (Blender 수동 검증)

**Files:** 없음 (검증만)

이 Task는 Blender가 실행 중이고 BlenderMCP 브릿지가 연결된 상태에서 수행. 세 함수가 정상 동작하는지 최소 호출로 확인.

- [ ] **Step 1: 모듈 리로드 + `mcp_inspect_bone_pairs` 호출**

MCP execute_blender_code:
```python
import sys, importlib
sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
for m in ["skeleton_analyzer", "arp_utils", "weight_transfer_rules", "mcp_verify", "mcp_bridge"]:
    if m in sys.modules:
        importlib.reload(sys.modules[m])

from mcp_bridge import mcp_inspect_bone_pairs
mcp_inspect_bone_pairs(role_filter="back_leg_l")
```

Expected: JSON 결과에 `DEF-thigh_L → c_thigh_b.l`, `DEF-thigh_R → c_thigh_b.r` 2개 pair가 포함됨 (F12 작업 결과 기준). `success: true`.

실패 시: Blender에 ARP 리그가 없거나 bone_pairs 없음 → 사용자에게 Build Rig 선행 요청.

- [ ] **Step 2: `mcp_compare_frames` 호출**

MCP execute_blender_code:
```python
from mcp_bridge import mcp_compare_frames
mcp_compare_frames(
    pairs=[("DEF-thigh_L", "c_thigh_b.l"), ("DEF-toe_L", "c_foot_fk.l")],
    frames=[0, 12, 24, 36],
    action_name="walk"
)
```

Expected: `overall_max_err`가 **0.00000** (소수점 5자리 수준). 이전 F12 Task 6에서 확인된 수치와 일치해야 함. `success: true`.

- [ ] **Step 3: `mcp_inspect_preset_bones` 호출**

MCP execute_blender_code:
```python
from mcp_bridge import mcp_inspect_preset_bones
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_thigh_b")
```

Expected: `matched_bones`에 `c_thigh_b.l`, `c_thigh_b.r`, `c_thigh_b_dupli_001.l`, `c_thigh_b_dupli_001.r` 4개 포함. `total_bones: 468`. `success: true`.

- [ ] **Step 4: 세 함수의 예상 출력을 Task 10에서 재사용할 수 있도록 복사**

스모크 테스트 결과 JSON을 Task 10의 레시피 문서 예시 값으로 사용. 실제로 실행한 출력 그대로 붙여넣어 문서의 "예상 출력" 블록을 채운다 (허구 값 금지).

- [ ] **Step 5: 이 Task는 커밋 없음 (검증만)**

모든 3개 함수가 정상 작동하면 Task 10으로 진행. 하나라도 실패 시 해당 함수의 구현을 재점검 (fix 커밋 추가 가능).

---

## Task 10: `docs/MCP_Recipes.md` 작성

**Files:**
- Create: `docs/MCP_Recipes.md`

- [ ] **Step 1: 레시피 문서 작성**

Create file `docs/MCP_Recipes.md`:

```markdown
# MCP 브릿지 사용 레시피

BlenderMCP 브릿지(`scripts/mcp_bridge.py`)는 Claude가 Blender를 직접 제어·검증하기 위한 고수준 함수를 제공한다. 이 문서는 언제 브릿지를 쓰는지, 어떤 함수가 있는지, 그리고 자주 쓰이는 조합 레시피를 정리한다.

## 언제 MCP 브릿지를 쓰는가

- Blender GUI 클릭-수정-재시도 사이클의 비용이 크다고 느껴질 때
- Blender 상태를 즉석에서 조회·수정·검증하고 싶을 때
- 숫자 기반 검증(프레임별 위치 비교, 통계)을 원할 때
- 반복적 확인 작업을 자동화하고 싶을 때

## 호출 패턴

```python
import sys; sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
from mcp_bridge import mcp_scene_summary
mcp_scene_summary()
```

모든 함수는 JSON을 stdout으로 출력하며, `success: true|false` 키로 결과를 표시한다.

## 함수 인덱스

| 함수 | 용도 | 주요 파라미터 |
|------|------|-------------|
| `mcp_scene_summary()` | 씬 요약 (armatures, meshes, actions) | 없음 |
| `mcp_create_preview()` | Preview Armature 생성 | 없음 |
| `mcp_build_rig()` | ARP Build Rig 실행 | 없음 |
| `mcp_run_regression(fixture_path)` | Fixture 기반 회귀 테스트 | fixture 경로 |
| `mcp_get_bone_roles()` | Preview 본 역할 조회 | 없음 |
| `mcp_set_bone_role(bone, role)` | 개별 본 역할 변경 | 본명, 역할 |
| `mcp_validate_weights()` | 웨이트 커버리지 검증 | 없음 |
| `mcp_bake_animation()` | F12 COPY_TRANSFORMS 베이크 | 없음 |
| `mcp_inspect_bone_pairs(role_filter)` | bone_pairs 디코드 + 역할 필터 | `None` / str / list |
| `mcp_compare_frames(pairs, frames, action)` | 소스-ARP 월드 위치 비교 | 본 쌍, 프레임, 액션명 |
| `mcp_inspect_preset_bones(preset, pattern)` | ARP 프리셋 본 이름 조회 | 프리셋명, 정규식 |

## 단일 함수 예시

### mcp_inspect_bone_pairs

```python
from mcp_bridge import mcp_inspect_bone_pairs
mcp_inspect_bone_pairs(role_filter="back_leg_l")
```

[Task 9 Step 1의 실제 스모크 테스트 출력을 여기에 붙여넣는다]

### mcp_compare_frames

```python
from mcp_bridge import mcp_compare_frames
mcp_compare_frames(
    pairs=[("DEF-thigh_L", "c_thigh_b.l")],
    frames=[0, 12, 24],
    action_name="walk"
)
```

[Task 9 Step 2의 실제 스모크 테스트 출력을 여기에 붙여넣는다]

### mcp_inspect_preset_bones

```python
from mcp_bridge import mcp_inspect_preset_bones
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_thigh_b")
```

[Task 9 Step 3의 실제 스모크 테스트 출력을 여기에 붙여넣는다]

## 조합 레시피

### 레시피 A: Bake 결과 정확성 검증 (F12 Task 6 재현)

목적: Build Rig + Bake Animation 후 소스와 ARP 리그의 뒷다리가 정확히 매핑됐는지 수치로 확인.

단계:
1. `mcp_inspect_bone_pairs(role_filter="back_leg_l")` — 뒷다리 매핑이 `c_thigh_b.l/.r`로 가는지 확인
2. pairs 리스트를 추출해 `mcp_compare_frames`에 전달
3. `overall_max_err`가 ~0.00000 인지 확인

```python
from mcp_bridge import mcp_inspect_bone_pairs, mcp_compare_frames

# Step 1: 매핑 확인
mcp_inspect_bone_pairs(role_filter=["back_leg_l", "back_leg_r", "back_foot_l", "back_foot_r"])

# Step 2: 프레임별 위치 비교 (위 결과에서 얻은 쌍 사용)
mcp_compare_frames(
    pairs=[
        ("DEF-thigh_L", "c_thigh_b.l"),
        ("DEF-thigh_R", "c_thigh_b.r"),
        ("DEF-toe_L", "c_foot_fk.l"),
        ("DEF-toe_R", "c_foot_fk.r"),
    ],
    frames=[0, 12, 24, 36, 48, 60, 72],
    action_name="walk"
)
```

F12 작업에서 이 레시피로 leg 오차 0.186m → 0.00000m를 확인했다.

### 레시피 B: 새 버그 패턴 발견 시 프리셋 실존 확인 (F12 c_toes_fk 발견 재현)

목적: 코드에 있는 본 이름 리터럴(`c_toes.l`, `c_foot_fk.l` 등)이 실제 ARP 프리셋에 존재하는지 확인.

```python
from mcp_bridge import mcp_inspect_preset_bones

# 모든 c_toes* 본 조회
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_toes")

# 모든 c_foot* 본 조회
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_foot")
```

이 레시피로 `c_toes.l`은 dog 프리셋에 없고 `c_toes_fk.l`만 있다는 사실을 확인했다(F12 Task 5).

### 레시피 C: 코드 수정 후 빠른 재검증

목적: `skeleton_analyzer.py` 또는 `arp_convert_addon.py`를 수정한 뒤 파이썬 레벨은 pytest로, Blender 레벨은 MCP로 즉시 확인.

```python
import sys, importlib
sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
for m in ["skeleton_analyzer", "arp_utils", "weight_transfer_rules", "mcp_verify", "mcp_bridge"]:
    if m in sys.modules:
        importlib.reload(sys.modules[m])

from mcp_bridge import mcp_build_rig, mcp_inspect_bone_pairs
mcp_build_rig()
mcp_inspect_bone_pairs()
```

`_reload()`는 각 브릿지 함수 호출 시 자동 실행되지만, 애드온 자체를 재로드해야 할 때는 위와 같이 수동 `importlib.reload`가 필요하다.

## F12 사례 요약

2026-04-05 F12 back_leg shoulder 작업(`docs/superpowers/specs/2026-04-05-f12-back-leg-shoulder-fix-design.md`, 커밋 2a07d78/8dce2a0/5d6b301)에서 이 레시피들이 다음과 같이 쓰였다:

- **레시피 A**: Task 6에서 `walk` 액션의 7개 프레임에 대해 뒷다리 오차 0.186m → 0.00000m 확인. 앞다리 dupli 잔여 오차 3.64mm도 함께 측정.
- **레시피 B**: Task 5에서 `c_toes.l`이 존재하지 않고 `c_toes_fk.l`이 실제 이름임을 확인. `ARP_CTRL_MAP` 정정 계기.
- **레시피 C**: 이번 sub-project ② 자체가 이 사이클의 자동화를 목표로 함.

이전에는 매번 raw `execute_blender_code`로 즉석 루프를 작성했다. 이제는 함수 호출 1~2줄로 같은 검증이 가능하다.
```

- [ ] **Step 2: Task 9의 실제 스모크 출력을 "단일 함수 예시" 섹션의 placeholder 3곳에 삽입**

각 `[Task 9 Step N의 실제 스모크 테스트 출력을 여기에 붙여넣는다]` placeholder를 Task 9에서 수집한 실제 JSON 출력으로 교체. 허구 값 삽입 금지.

- [ ] **Step 3: 문서 렌더링 확인**

Read `docs/MCP_Recipes.md` 전체를 훑어 마크다운 구조(`#`/`##`/`###`), 코드 블록, 테이블이 깨지지 않는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add docs/MCP_Recipes.md
git commit -m "$(cat <<'EOF'
docs(mcp): MCP_Recipes.md 작성 — 사용 레시피와 F12 사례 정리

11개 브릿지 함수 인덱스 + 3개 단일 함수 예시(실제 스모크 출력
포함) + 3개 조합 레시피(Bake 검증, 프리셋 본 확인, 수정 후 재검증)
+ F12 작업 사례 요약.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

---

## Task 11: 최종 검증 + ProjectPlan.md 갱신

**Files:**
- Modify: `docs/ProjectPlan.md`

- [ ] **Step 1: 전체 검증 재실행**

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```

Expected:
- pytest: **120 passed**
- ruff: `All checks passed!`

- [ ] **Step 2: Read `docs/ProjectPlan.md`의 우선순위 섹션 (line 168 근처)**

Run: Read `docs/ProjectPlan.md` offset=160 limit=30

현재 우선순위 확인:
```
1. **F12 애니메이션 베이크 구현** — 설계 완료, `docs/F12_ExactMatch.md` 참조
2. **F8 실제 weight 검증** — 여우 리그 weight paint 검증
3. **자동 역할 추론 정확도 개선** — 새 동물 리그 대응
```

- [ ] **Step 3: ProjectPlan.md 하단(후속 기능 또는 참고 문서 섹션)에 MCP 피드백 루프 완료 기록 추가**

실제 line 번호는 Step 2에서 확인. F12 섹션 근처 또는 "참고 문서" 테이블 아래에 다음 블록을 삽입:

```markdown

### MCP 피드백 루프 확장 완료 (2026-04-05)

`scripts/mcp_bridge.py`에 3개 함수 추가 + 순수 헬퍼 모듈 + 사용 레시피.

- 신규 함수: `mcp_inspect_bone_pairs`, `mcp_compare_frames`, `mcp_inspect_preset_bones`
- 순수 로직: `scripts/mcp_verify.py` (pytest 17개 커버)
- 레시피: `docs/MCP_Recipes.md` — 3개 조합 레시피 + F12 사례 요약
- 총 테스트 수: 103 → 120 (신규 +17)

이 함수들은 Sub-project ③(addon.py 분할) 실행 중 체크포인트 도구로 사용된다.
```

적절한 위치(F12 완료 기록 뒤 또는 후속 기능 섹션)에 삽입. Edit 호출 시 정확한 old_string을 Step 2의 Read 결과에서 복사하여 사용.

- [ ] **Step 4: 최종 커밋**

```bash
git add docs/ProjectPlan.md
git commit -m "$(cat <<'EOF'
docs(mcp): ProjectPlan.md에 MCP 피드백 루프 완료 기록

3개 브릿지 함수, mcp_verify 헬퍼, MCP_Recipes.md 추가 완료. 테스트
103 → 120. Sub-project ③ 실행의 체크포인트 도구로 사용 예정.

3개 통합 개선 sub-project ②/③ 구현 완료.

Spec: docs/superpowers/specs/2026-04-05-mcp-feedback-loop-design.md
EOF
)"
```

- [ ] **Step 5: git log로 최종 커밋 시퀀스 확인**

Run:
```
git log --oneline -10
```

Expected 순서:
```
<sha> docs(mcp): ProjectPlan.md에 MCP 피드백 루프 완료 기록
<sha> docs(mcp): MCP_Recipes.md 작성 — 사용 레시피와 F12 사례 정리
<sha> feat(mcp): mcp_inspect_preset_bones 함수 추가
<sha> feat(mcp): mcp_compare_frames 함수 추가
<sha> feat(mcp): mcp_inspect_bone_pairs 함수 추가
<sha> feat(mcp): mcp_verify 순수 헬퍼 4개 구현 (TDD Green)
<sha> test(mcp): mcp_verify 헬퍼 4개 + pytest 17개 작성 (TDD Red)
...
```

---

## 완료 기준

- [ ] `scripts/mcp_verify.py` 생성, 4개 헬퍼 구현
- [ ] `tests/test_mcp_verify.py` 생성, 17개 테스트 모두 통과
- [ ] `scripts/mcp_bridge.py`에 3개 함수 추가, `_reload()` 갱신
- [ ] `docs/MCP_Recipes.md` 생성, 실제 MCP 스모크 출력 포함
- [ ] `docs/ProjectPlan.md` 완료 기록 추가
- [ ] `pytest tests/ -v` → **120 passed**
- [ ] `ruff check scripts/ tests/` → clean
- [ ] MCP 스모크 테스트 3개 함수 모두 성공
- [ ] 커밋 7개: test(Red) / feat(Green helpers) / feat×3(bridge 함수) / docs(recipes) / docs(ProjectPlan)
- [ ] 피처 브랜치 `feat/mcp-feedback-loop`가 master에 fast-forward 머지됨

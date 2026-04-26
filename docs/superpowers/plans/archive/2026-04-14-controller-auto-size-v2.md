# Controller Auto-Size v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모든 ARP 컨트롤러를 spine 체인 전체 길이 기반의 균일한 절대 크기로 자동 설정한다.

**Architecture:** `_compute_body_reference()`로 spine 합계를 구하고, `target = body_ref × BODY_FRACTION`을 계산한 뒤, 각 컨트롤러의 `scale = target / arp_ctrl_bone_length`로 `custom_shape_scale_xyz`를 설정한다. `arp_ops_build.py` 호출 코드는 변경 없음.

**Tech Stack:** Python 3.11, Blender 4.5 Python API, pytest, ruff

---

## 파일 맵

| 파일 | 변경 유형 | 내용 |
|------|---------|------|
| `scripts/arp_build_helpers.py` | Modify | 상수 변경, `_compute_body_reference()` 추가, `_build_controller_size_targets_per_bone()` 로직 교체 |
| `tests/test_controller_auto_size.py` | Modify | 기존 테스트 교체, 신규 테스트 추가 |
| `scripts/arp_ops_build.py` | 변경 없음 | 함수 시그니처 유지 |
| `tests/test_arp_invariants.py` | 변경 없음 | 함수명 동일하므로 그대로 통과 |

---

## Task 1: `_compute_body_reference()` 추가 (TDD)

**Files:**
- Modify: `.worktrees/feat-controller-auto-size-impl/tests/test_controller_auto_size.py`
- Modify: `.worktrees/feat-controller-auto-size-impl/scripts/arp_build_helpers.py`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_controller_auto_size.py` 맨 아래에 추가:

```python
def test_compute_body_reference_uses_spine():
    """spine 역할이 있으면 spine 합계를 반환."""
    roles = {"spine": ["spine01", "spine02"], "head": ["head"]}
    ref = ab._compute_body_reference(roles, PREVIEW_POSITIONS)
    expected = _bone_len("spine01") + _bone_len("spine02")
    assert ref == pytest.approx(expected, rel=1e-6)


def test_compute_body_reference_fallback_avg_when_no_spine():
    """spine 역할 없으면 할당된 모든 본의 평균 길이를 반환."""
    roles = {"head": ["head"], "neck": ["neck01"]}
    ref = ab._compute_body_reference(roles, PREVIEW_POSITIONS)
    expected = (_bone_len("head") + _bone_len("neck01")) / 2
    assert ref == pytest.approx(expected, rel=1e-6)


def test_compute_body_reference_fallback_constant_when_empty():
    """할당된 본이 아예 없으면 AUTO_SIZE_FALLBACK 반환."""
    ref = ab._compute_body_reference({}, PREVIEW_POSITIONS)
    assert ref == pytest.approx(ab.AUTO_SIZE_FALLBACK, rel=1e-6)
```

- [ ] **Step 2: 실패 확인**

```bash
cd C:\Users\manag\Desktop\BlenderRigConvert\.worktrees\feat-controller-auto-size-impl
python -m pytest tests/test_controller_auto_size.py::test_compute_body_reference_uses_spine -v
```

Expected: `AttributeError: module 'arp_build_helpers' has no attribute '_compute_body_reference'`

- [ ] **Step 3: 상수 + 함수 구현**

`scripts/arp_build_helpers.py`에서 상수를 다음과 같이 변경:

```python
# 기존
AUTO_SIZE_MIN = 0.03
AUTO_SIZE_MAX = 0.6
AUTO_SIZE_FALLBACK = 0.12

# 변경 후
BODY_FRACTION = 0.10
AUTO_SIZE_MIN = 0.05
AUTO_SIZE_MAX = 2.0
AUTO_SIZE_FALLBACK = 0.12
```

그 다음 `_clamp_controller_size()` 바로 아래에 추가:

```python
def _compute_body_reference(roles, preview_positions):
    """spine 체인 전체 길이를 body scale reference로 반환.

    - spine 역할이 있으면 spine 본들의 길이 합계
    - spine 없으면 할당된 모든 본의 평균 길이
    - 본이 아예 없으면 AUTO_SIZE_FALLBACK
    """
    spine_bones = (roles or {}).get("spine", [])
    if spine_bones:
        total = sum(_preview_bone_length(preview_positions, b) for b in spine_bones)
        if total > 1e-6:
            return total

    all_bones = [b for bones in (roles or {}).values() for b in bones]
    if all_bones:
        lengths = [_preview_bone_length(preview_positions, b) for b in all_bones]
        valid = [length for length in lengths if length > 1e-6]
        if valid:
            return sum(valid) / len(valid)

    return AUTO_SIZE_FALLBACK
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_controller_auto_size.py::test_compute_body_reference_uses_spine tests/test_controller_auto_size.py::test_compute_body_reference_fallback_avg_when_no_spine tests/test_controller_auto_size.py::test_compute_body_reference_fallback_constant_when_empty -v
```

Expected: 3 passed

- [ ] **Step 5: 커밋**

```bash
git -C .worktrees/feat-controller-auto-size-impl add scripts/arp_build_helpers.py tests/test_controller_auto_size.py
git -C .worktrees/feat-controller-auto-size-impl commit -m "feat(addon): _compute_body_reference 추가 — spine 합계 기반 body scale"
```

---

## Task 2: `_build_controller_size_targets_per_bone()` 로직 교체

**Files:**
- Modify: `.worktrees/feat-controller-auto-size-impl/tests/test_controller_auto_size.py`
- Modify: `.worktrees/feat-controller-auto-size-impl/scripts/arp_build_helpers.py`

- [ ] **Step 1: 실패하는 테스트 작성**

기존 `test_per_bone_ratio_scale`, `test_per_bone_index_pairing`, `test_ik_ctrl_uses_first_preview_bone` 함수를 **삭제**하고, 다음으로 교체:

```python
def test_body_reference_uniform_absolute_size():
    """모든 컨트롤러가 동일한 절대 표시 크기(target)를 가진다.
    표시 크기 = ctrl_bone_length × scale = ctrl_bone_length × (target / ctrl_bone_length) = target
    """
    spine_total = _bone_len("spine01") + _bone_len("spine02")
    target = spine_total * ab.BODY_FRACTION

    arp_bone_lengths = {
        "c_spine_01.x": 0.5,
        "c_spine_02.x": 0.2,
        "c_head.x": 0.8,
        "c_ear_01.l": 0.1,
    }
    roles = {"spine": ["spine01", "spine02"]}
    ctrl_map = {
        "spine": ["c_spine_01.x", "c_spine_02.x"],
        "head": ["c_head.x"],
        "ear_l": ["c_ear_01.l"],
    }

    targets = ab._build_controller_size_targets_per_bone(
        roles, ctrl_map, PREVIEW_POSITIONS, arp_bone_lengths
    )

    assert targets["c_spine_01.x"] == pytest.approx(target / 0.5, rel=1e-6)
    assert targets["c_spine_02.x"] == pytest.approx(target / 0.2, rel=1e-6)
    assert targets["c_head.x"] == pytest.approx(target / 0.8, rel=1e-6)
    assert targets["c_ear_01.l"] == pytest.approx(target / 0.1, rel=1e-6)


def test_fallback_when_no_arp_length():
    """arp_bone_lengths 없을 때 target_size를 scale로 직접 사용."""
    roles = {"spine": ["spine01"], "head": ["head"]}
    ctrl_map = {"head": ["c_head.x"]}

    spine_total = _bone_len("spine01")
    target = spine_total * ab.BODY_FRACTION

    targets = ab._build_controller_size_targets_per_bone(
        roles, ctrl_map, PREVIEW_POSITIONS, {}
    )

    assert targets["c_head.x"] == pytest.approx(target, rel=1e-6)
```

- [ ] **Step 2: 실패 확인**

```bash
python -m pytest tests/test_controller_auto_size.py::test_body_reference_uniform_absolute_size -v
```

Expected: FAIL (현재 구현은 preview/ctrl ratio 방식)

- [ ] **Step 3: `_build_controller_size_targets_per_bone()` 로직 교체**

`scripts/arp_build_helpers.py`에서 `_build_controller_size_targets_per_bone()` 전체를:

```python
def _build_controller_size_targets_per_bone(roles, ctrl_map, preview_positions, arp_bone_lengths):
    """target = body_ref × BODY_FRACTION, scale = target / arp_ctrl_bone_length.

    body_ref는 spine 체인 전체 길이 (없으면 평균).
    모든 컨트롤러가 동일한 절대 표시 크기(target)로 수렴한다.

    Returns:
        {ctrl_name: scale}
    """
    body_ref = _compute_body_reference(roles, preview_positions)
    target_size = body_ref * BODY_FRACTION

    targets = {}
    for role_key in AUTO_SIZE_SUPPORTED_ROLES:
        ctrl_names = (ctrl_map or {}).get(role_key, [])
        if not ctrl_names:
            continue

        for ctrl_name in ctrl_names:
            ctrl_len = (arp_bone_lengths or {}).get(ctrl_name)
            if ctrl_len:
                scale = target_size / ctrl_len
            else:
                scale = target_size  # fallback: world unit 직접 사용

            targets[ctrl_name] = _clamp_controller_size(scale)

    return targets
```

- [ ] **Step 4: 통과 확인**

```bash
python -m pytest tests/test_controller_auto_size.py -v
```

Expected: 모든 테스트 PASS

- [ ] **Step 5: 전체 테스트 스위트 확인**

```bash
python -m pytest tests/ -v
```

Expected: 기존 통과하던 테스트 모두 유지

- [ ] **Step 6: ruff 확인**

```bash
python -m ruff check scripts/ tests/
```

Expected: All checks passed

- [ ] **Step 7: 커밋**

```bash
git -C .worktrees/feat-controller-auto-size-impl add scripts/arp_build_helpers.py tests/test_controller_auto_size.py
git -C .worktrees/feat-controller-auto-size-impl commit -m "fix(addon): controller auto-size v2 — spine 기반 균일 절대 크기 방식으로 전환"
```

---

## Task 3: addons 싱크 및 Blender 검증

**Files:**
- Copy to: `C:\Users\manag\AppData\Roaming\Blender Foundation\Blender\4.5\scripts\addons\`

- [ ] **Step 1: addons 폴더에 복사**

```bash
ADDONS="/c/Users/manag/AppData/Roaming/Blender Foundation/Blender/4.5/scripts/addons"
WT="/c/Users/manag/Desktop/BlenderRigConvert/.worktrees/feat-controller-auto-size-impl/scripts"
cp "$WT/arp_build_helpers.py" "$ADDONS/"
```

- [ ] **Step 2: 해시 검증**

```bash
sha256sum "$WT/arp_build_helpers.py" "$ADDONS/arp_build_helpers.py"
```

Expected: 두 줄의 해시가 동일

- [ ] **Step 3: Blender에서 reload**

Blender Python Console 또는 MCP:

```python
import sys
sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_reload_addon
mcp_reload_addon()
```

- [ ] **Step 4: Blender 수동 확인 체크리스트**

Build Rig 실행 후 확인:

1. head / spine / neck / ear / foot 컨트롤러가 비슷한 절대 크기인지
2. 여우 → 사슴 순서로 각각 Build Rig → 동물 크기에 비례해 자동 조정되는지
3. 같은 소스로 Build Rig 재실행 시 동일 크기가 적용되는지
4. BODY_FRACTION을 0.08 / 0.12로 변경해 반응 확인 (선택)

크기가 너무 크거나 작으면 `arp_build_helpers.py`의 `BODY_FRACTION` 값만 조정 후 Step 1-3 반복.

---

## Self-Review

**스펙 커버리지 점검:**
- [x] spine 합계 → body_ref: Task 1
- [x] target = body_ref × BODY_FRACTION: Task 2
- [x] scale = target / ctrl_bone_length: Task 2
- [x] AUTO_SIZE_MAX = 2.0: Task 1 (상수 변경)
- [x] fallback (spine 없음): Task 1 `_compute_body_reference` + Task 2 test
- [x] fallback (ctrl 길이 없음): Task 2 test
- [x] IK 특별 취급 없음: 새 구현에서 루프 단순화로 자연히 처리됨
- [x] arp_ops_build.py 변경 없음: 함수 시그니처 동일 유지

**타입/시그니처 일관성:**
- `_compute_body_reference(roles, preview_positions) → float`: Task 1 정의, Task 2에서 내부 호출
- `_build_controller_size_targets_per_bone(roles, ctrl_map, preview_positions, arp_bone_lengths) → dict`: 기존 시그니처 유지
- `BODY_FRACTION`: Task 1에서 정의, Task 2에서 참조 (`ab.BODY_FRACTION`)

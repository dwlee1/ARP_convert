# ARP 컨트롤러 자동 크기 보정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ARP Build Rig가 `match_to_rig` 직후 `spine/neck/head/ear/foot` 컨트롤러의 custom shape 표시 크기를 역할 체인 길이 기반으로 자동 보정하게 만든다.

**Architecture:** 순수 계산은 `scripts/arp_build_helpers.py`에 모으고, Build Rig는 계산 결과를 받아 `PoseBone.custom_shape_scale_xyz`만 적용한다. `pipeline_runner.py`와 `03_batch_convert.py`는 이미 `bpy.ops.arp_convert.build_rig()`를 호출하므로 별도 경로를 만들지 않고 동일 후처리를 공유한다.

**Tech Stack:** Python 3.11, Blender 4.5 LTS API (`PoseBone.custom_shape_scale_xyz`), Auto-Rig Pro dog preset, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-04-13-controller-auto-size-design.md`

**브랜치:** `feat/controller-auto-size`

---

## File Structure

- Modify: `scripts/arp_build_helpers.py`
  - 역할 체인 길이 계산, 컨트롤러 그룹 분류, clamp 계산, `custom_shape_scale_xyz` 적용 헬퍼를 추가한다.
- Modify: `scripts/arp_ops_build.py`
  - `match_to_rig` 직후 auto-size 헬퍼를 호출하고 로그/에러 fallback을 연결한다.
- Create: `tests/test_controller_auto_size.py`
  - 순수 길이 계산, 역할별 multiplier/clamp, target 분류 로직을 Blender 없이 검증한다.
- Modify: `tests/test_arp_invariants.py`
  - 금지된 구현 경로(`Object.scale`, `Apply Transforms`, `Set Custom Shape`)가 들어오지 않도록 정적 가드레일을 추가한다.
- Modify: `docs/ProjectPlan.md`
  - 구현 완료 후 controller auto-size 상태를 반영한다.

`scripts/pipeline_runner.py`와 `scripts/03_batch_convert.py`는 코드 수정 대상이 아니다. 두 경로는 이미 `bpy.ops.arp_convert.build_rig()`를 타므로 최종 검증만 수행한다.

---

### Task 1: 순수 auto-size 규칙을 테스트로 고정

**Files:**
- Create: `tests/test_controller_auto_size.py`
- Modify: `tests/test_arp_invariants.py`

- [ ] **Step 1: failing test 파일 작성**

Create `tests/test_controller_auto_size.py`:

```python
"""컨트롤러 자동 크기 보정 규칙 테스트."""

import math

from arp_build_helpers import (
    _build_controller_auto_size_context,
    _build_controller_auto_size_targets,
    _clamp_controller_size,
)


PREVIEW_POSITIONS = {
    "spine01": ((0.0, 0.0, 0.0), (0.0, 0.30, 0.0), 0.0),
    "spine02": ((0.0, 0.30, 0.0), (0.0, 0.55, 0.0), 0.0),
    "neck01": ((0.0, 0.55, 0.0), (0.0, 0.68, 0.0), 0.0),
    "neck02": ((0.0, 0.68, 0.0), (0.0, 0.80, 0.0), 0.0),
    "head": ((0.0, 0.80, 0.0), (0.0, 1.00, 0.0), 0.0),
    "ear.L.01": ((0.02, 0.92, 0.0), (0.04, 1.04, 0.0), 0.0),
    "ear.L.02": ((0.04, 1.04, 0.0), (0.05, 1.14, 0.0), 0.0),
    "foot_back_l": ((0.12, -0.20, 0.0), (0.16, -0.34, 0.0), 0.0),
    "toe_back_l": ((0.16, -0.34, 0.0), (0.22, -0.42, 0.0), 0.0),
}


def test_build_context_uses_chain_lengths():
    roles = {
        "spine": ["spine01", "spine02"],
        "neck": ["neck01", "neck02"],
        "head": ["head"],
        "ear_l": ["ear.L.01", "ear.L.02"],
        "back_foot_l": ["foot_back_l", "toe_back_l"],
    }
    ctx = _build_controller_auto_size_context(roles, PREVIEW_POSITIONS)

    assert math.isclose(ctx["spine"], 0.55, rel_tol=1e-6)
    assert math.isclose(ctx["neck"], 0.25, rel_tol=1e-6)
    assert math.isclose(ctx["head"], 0.20, rel_tol=1e-6)
    assert ctx["ear_l"] > 0.20
    assert ctx["back_foot_l"] > 0.20


def test_target_builder_applies_role_specific_multipliers():
    ctx = {
        "spine": 0.55,
        "neck": 0.25,
        "head": 0.20,
        "ear_l": 0.22,
        "back_foot_l": 0.24,
    }
    ctrl_map = {
        "spine": ["c_spine_01.x", "c_spine_02.x"],
        "neck": ["c_subneck_01.x", "c_neck.x"],
        "head": ["c_head.x"],
        "ear_l": ["c_ear_01.l", "c_ear_02.l"],
        "back_foot_l": ["c_foot_fk.l", "c_toes_fk.l"],
    }

    targets = _build_controller_auto_size_targets(ctrl_map, ctx)

    assert math.isclose(targets["c_spine_01.x"], 0.33, rel_tol=1e-6)
    assert math.isclose(targets["c_neck.x"], 0.1875, rel_tol=1e-6)
    assert math.isclose(targets["c_head.x"], 0.20, rel_tol=1e-6)
    assert math.isclose(targets["c_ear_01.l"], 0.176, rel_tol=1e-6)
    assert math.isclose(targets["c_toes_fk.l"], 0.18, rel_tol=1e-6)


def test_clamp_controller_size_enforces_bounds():
    assert _clamp_controller_size(0.001, 0.03, 0.6) == 0.03
    assert _clamp_controller_size(0.25, 0.03, 0.6) == 0.25
    assert _clamp_controller_size(1.20, 0.03, 0.6) == 0.6
```

- [ ] **Step 2: invariant test 추가**

Append to `tests/test_arp_invariants.py`:

```python

class TestControllerAutoSizeGuardrails:
    """controller auto-size 구현이 금지된 custom-shape 경로를 쓰지 않도록 보장."""

    def test_no_shape_object_scale_mutation(self):
        source = (SCRIPTS_DIR / "arp_build_helpers.py").read_text(encoding="utf-8")
        assert ".scale =" not in source
        assert "Object.scale" not in source

    def test_no_apply_transforms_or_set_custom_shape_operator(self):
        combined = (
            (SCRIPTS_DIR / "arp_build_helpers.py").read_text(encoding="utf-8")
            + "\n"
            + (SCRIPTS_DIR / "arp_ops_build.py").read_text(encoding="utf-8")
        )
        assert "Apply Transforms" not in combined
        assert "Set Custom Shape" not in combined
        assert "bpy.ops.pose.custom_shape" not in combined
```

- [ ] **Step 3: 새 테스트가 실제로 실패하는지 확인**

Run:

```bash
pytest tests/test_controller_auto_size.py -v
```

Expected:
- `ImportError` 또는 `cannot import name '_build_controller_auto_size_context'`
- 아직 helper가 없으므로 실패해야 정상

- [ ] **Step 4: 정적 invariant도 통과 baseline 확인**

Run:

```bash
pytest tests/test_arp_invariants.py::TestControllerAutoSizeGuardrails -v
```

Expected:
- 새 테스트가 현재 코드에서 PASS/FAIL 중 어느 쪽이든 상관없다
- 핵심은 이후 구현에서 금지된 경로를 쓰지 않도록 이 테스트가 살아 있어야 한다

- [ ] **Step 5: 커밋**

```bash
git add tests/test_controller_auto_size.py tests/test_arp_invariants.py
git commit -m "test(addon): controller auto-size 규칙과 guardrail 테스트 추가"
```

---

### Task 2: `arp_build_helpers.py`에 auto-size 순수 계산과 적용 헬퍼 추가

**Files:**
- Modify: `scripts/arp_build_helpers.py`
- Test: `tests/test_controller_auto_size.py`

- [ ] **Step 1: helper import 정리**

Edit `scripts/arp_build_helpers.py` imports:

```python
import bpy
from mathutils import Vector
```

Expected:
- 기존 `import bpy`만 있던 파일에 `Vector` 추가

- [ ] **Step 2: multiplier/clamp 상수 추가**

Append near top of `scripts/arp_build_helpers.py`:

```python
AUTO_SIZE_MULTIPLIERS = {
    "spine": 0.6,
    "neck": 0.75,
    "head": 1.0,
    "ear": 0.8,
    "foot_fk": 1.0,
    "foot_ik": 1.3,
    "toes": 0.75,
}

AUTO_SIZE_MIN = 0.03
AUTO_SIZE_MAX = 0.6
AUTO_SIZE_FALLBACK = 0.12
```

- [ ] **Step 3: 길이 계산 헬퍼 구현**

Append these functions to `scripts/arp_build_helpers.py`:

```python
def _preview_bone_length(preview_positions, bone_name):
    data = preview_positions.get(bone_name)
    if not data:
        return 0.0
    head, tail, _roll = data
    return (Vector(tail) - Vector(head)).length


def _sum_preview_chain_length(preview_positions, bone_names):
    return sum(_preview_bone_length(preview_positions, name) for name in bone_names)


def _clamp_controller_size(value, min_size=AUTO_SIZE_MIN, max_size=AUTO_SIZE_MAX):
    return max(min_size, min(max_size, float(value)))
```

- [ ] **Step 4: 역할 기준 길이 context 헬퍼 구현**

Append to `scripts/arp_build_helpers.py`:

```python
def _build_controller_auto_size_context(roles, preview_positions):
    ctx = {}

    spine_bones = roles.get("spine", [])
    if spine_bones:
        ctx["spine"] = _sum_preview_chain_length(preview_positions, spine_bones)

    neck_bones = roles.get("neck", [])
    if neck_bones:
        ctx["neck"] = _sum_preview_chain_length(preview_positions, neck_bones)

    head_bones = roles.get("head", [])
    if head_bones:
        ctx["head"] = _preview_bone_length(preview_positions, head_bones[0])

    for side_key in ("ear_l", "ear_r"):
        if roles.get(side_key):
            ctx[side_key] = _sum_preview_chain_length(preview_positions, roles[side_key])

    for role_key in (
        "back_foot_l",
        "back_foot_r",
        "front_foot_l",
        "front_foot_r",
    ):
        if roles.get(role_key):
            ctx[role_key] = _sum_preview_chain_length(preview_positions, roles[role_key])

    return {
        key: (value if value > 1e-6 else AUTO_SIZE_FALLBACK)
        for key, value in ctx.items()
    }
```

- [ ] **Step 5: controller target 분류/계산 헬퍼 구현**

Append to `scripts/arp_build_helpers.py`:

```python
def _controller_scale_multiplier(role_key, ctrl_name):
    if role_key == "spine":
        return AUTO_SIZE_MULTIPLIERS["spine"]
    if role_key == "neck":
        return AUTO_SIZE_MULTIPLIERS["neck"]
    if role_key == "head":
        return AUTO_SIZE_MULTIPLIERS["head"]
    if role_key.startswith("ear_"):
        return AUTO_SIZE_MULTIPLIERS["ear"]
    if "toes" in ctrl_name:
        return AUTO_SIZE_MULTIPLIERS["toes"]
    if "foot_ik" in ctrl_name or "hand_ik" in ctrl_name:
        return AUTO_SIZE_MULTIPLIERS["foot_ik"]
    return AUTO_SIZE_MULTIPLIERS["foot_fk"]


def _build_controller_auto_size_targets(ctrl_map, size_context):
    targets = {}
    for role_key, ctrl_names in ctrl_map.items():
        if role_key not in size_context:
            continue
        base_length = size_context[role_key]
        for ctrl_name in ctrl_names:
            multiplier = _controller_scale_multiplier(role_key, ctrl_name)
            targets[ctrl_name] = _clamp_controller_size(base_length * multiplier)
    return targets
```

- [ ] **Step 6: 실제 적용 헬퍼 구현**

Append to `scripts/arp_build_helpers.py`:

```python
def _apply_controller_auto_size(arp_obj, size_targets, log):
    applied = 0
    for ctrl_name, target_size in size_targets.items():
        pose_bone = arp_obj.pose.bones.get(ctrl_name)
        if pose_bone is None:
            log(f"  controller auto-size skip: {ctrl_name} 없음", "WARN")
            continue
        if not hasattr(pose_bone, "custom_shape_scale_xyz"):
            log(f"  controller auto-size skip: {ctrl_name} scale 속성 없음", "WARN")
            continue

        pose_bone.custom_shape_scale_xyz = (target_size, target_size, target_size)
        applied += 1
        log(f"  controller auto-size: {ctrl_name} -> {target_size:.4f}", "DEBUG")
    return applied
```

- [ ] **Step 7: 단위 테스트로 구현 검증**

Run:

```bash
pytest tests/test_controller_auto_size.py -v
```

Expected:
- 3 tests PASS

- [ ] **Step 8: 커밋**

```bash
git add scripts/arp_build_helpers.py tests/test_controller_auto_size.py
git commit -m "feat(addon): controller auto-size 계산 헬퍼 추가"
```

---

### Task 3: Build Rig에 auto-size 후처리를 연결

**Files:**
- Modify: `scripts/arp_ops_build.py`
- Modify: `tests/test_arp_invariants.py`

- [ ] **Step 1: helper import 추가**

Edit import block in `scripts/arp_ops_build.py`:

```python
from arp_build_helpers import (
    _adjust_chain_counts,
    _apply_controller_auto_size,
    _build_controller_auto_size_context,
    _build_controller_auto_size_targets,
)
```

Expected:
- 기존 `_adjust_chain_counts`만 가져오던 import에 3개 helper 추가

- [ ] **Step 2: `match_to_rig` 직후 auto-size 호출 삽입**

Insert immediately after the `run_arp_operator(bpy.ops.arp.match_to_rig)` success block in `scripts/arp_ops_build.py`:

```python
        try:
            from skeleton_analyzer import discover_arp_ctrl_map

            ctrl_map = discover_arp_ctrl_map(arp_obj)
            size_context = _build_controller_auto_size_context(roles, preview_positions)
            size_targets = _build_controller_auto_size_targets(ctrl_map, size_context)
            if size_targets:
                applied = _apply_controller_auto_size(arp_obj, size_targets, log)
                log(f"controller auto-size 적용: {applied}개")
            else:
                log("controller auto-size 대상 없음", "WARN")
        except Exception as e:
            log(f"controller auto-size 실패 (무시): {e}", "WARN")
```

Rules:
- `match_to_rig` 성공 직후여야 한다
- 실패해도 Build Rig 전체는 취소하지 않는다
- `custom_shape_scale_xyz` 외 속성이나 operator는 호출하지 않는다

- [ ] **Step 3: 중복 import 정리**

`scripts/arp_ops_build.py`에는 이미 아래 import가 후반부에 있다.

```python
from skeleton_analyzer import discover_arp_ctrl_map
from skeleton_analyzer import _apply_ik_to_foot_ctrl, discover_arp_ctrl_map
```

Refactor to:

```python
from skeleton_analyzer import _apply_ik_to_foot_ctrl, discover_arp_ctrl_map
```

and remove the earlier one-off local import if no longer needed.

- [ ] **Step 4: guardrail 테스트 재실행**

Run:

```bash
pytest tests/test_arp_invariants.py::TestControllerAutoSizeGuardrails -v
```

Expected:
- PASS
- 소스에 `Object.scale`, `Apply Transforms`, `Set Custom Shape` 경로가 없어야 한다

- [ ] **Step 5: targeted build-related tests 실행**

Run:

```bash
pytest tests/test_controller_auto_size.py tests/test_arp_invariants.py -v
```

Expected:
- 새 테스트 전부 PASS

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_ops_build.py tests/test_arp_invariants.py
git commit -m "feat(addon): Build Rig에 controller auto-size 후처리 연결"
```

---

### Task 4: 전체 검증과 문서 마감

**Files:**
- Modify: `docs/ProjectPlan.md`

- [ ] **Step 1: ProjectPlan 상태 갱신**

Append to the relevant completed-status section in `docs/ProjectPlan.md`:

```markdown
- [x] Build Rig 후처리: `spine/neck/head/ear/foot` controller auto-size 적용
  - 기준: 역할 체인 길이 기반 + controller별 multiplier + clamp
  - 적용 범위: `custom_shape_scale_xyz`만 조정
  - 금지: custom shape object scale, Apply Transforms, Set Custom Shape 자동화
```

- [ ] **Step 2: 전체 테스트 실행**

Run:

```bash
pytest tests/ -v
ruff check scripts/ tests/
```

Expected:
- 전체 pytest PASS
- ruff clean

- [ ] **Step 3: pipeline/batch 경로 smoke 확인**

Run:

```bash
python - <<'PY'
from pathlib import Path
src = Path("scripts/pipeline_runner.py").read_text(encoding="utf-8")
assert 'bpy.ops.arp_convert.build_rig()' in src
print("pipeline uses build_rig operator")
PY
```

Expected:
- `pipeline uses build_rig operator`

Manual note:
- `scripts/03_batch_convert.py`는 `pipeline_runner.py` wrapper이므로 별도 코드 수정 없음

- [ ] **Step 4: Blender 수동 검증**

Manual checklist:

```text
1. 여우 샘플에서 Build Rig 실행
2. spine/neck/head/ear/foot 컨트롤러가 과대/과소가 아닌지 확인
3. 같은 소스에서 Build Rig를 한 번 더 실행
4. 두 번째 빌드에서도 크기가 결정적으로 재적용되는지 확인
5. custom shape 오브젝트 자체 scale이 바뀌지 않았는지 임의 1개 shape object 확인
```

- [ ] **Step 5: 최종 커밋**

```bash
git add docs/ProjectPlan.md
git commit -m "docs(addon): controller auto-size 구현 상태를 ProjectPlan에 반영"
```

---

## 완료 기준

- [ ] `scripts/arp_build_helpers.py`에 auto-size 길이 계산/target 생성/적용 헬퍼가 존재한다
- [ ] `scripts/arp_ops_build.py`가 `match_to_rig` 직후 auto-size를 호출한다
- [ ] 적용 속성은 `PoseBone.custom_shape_scale_xyz`만 사용한다
- [ ] `tests/test_controller_auto_size.py`가 PASS 한다
- [ ] `tests/test_arp_invariants.py::TestControllerAutoSizeGuardrails`가 PASS 한다
- [ ] `pytest tests/ -v` 전체 통과
- [ ] `ruff check scripts/ tests/` 통과
- [ ] Blender 수동 검증에서 `spine/neck/head/ear/foot` 크기가 개선되고, 재빌드 시 재적용된다
- [ ] `docs/ProjectPlan.md`에 기능 상태가 반영된다

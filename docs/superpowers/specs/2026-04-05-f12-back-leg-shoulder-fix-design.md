# F12 뒷다리 shoulder 매핑 블로커 수정 설계

> 작성일: 2026-04-05
> 상태: 설계 확정 대기
> 연관: `docs/ProjectPlan.md:150-154`, `docs/F12_ExactMatch.md`, `docs/plans/2026-04-03-f12-animation-bake.md`

## 문제 요약

F12 COPY_TRANSFORMS 베이크 경로에서 뒷다리 shoulder(`c_thigh_b`)가 bone_pairs에 누락되어, 소스의 뒷다리 첫 번째 본(hip/shoulder)이 엉뚱한 FK 컨트롤러(`c_thigh_fk`)에 베이크되는 문제. 이전 실험에서 관찰된 leg 0.186m 오차의 유력한 원인으로 추정된다.

ProjectPlan은 이 증상을 "`discover_arp_ctrl_map()`이 FK 컨트롤러만 반환하여 shoulder를 못 잡음"으로 기록하고 있으며, 해결 방향으로 "bone_pairs 생성 시 leg 역할을 ctrl_map 의존 대신 직접 IK 이름 구성"을 제안했다.

## 근본 원인

`scripts/skeleton_analyzer.py` 안에서 **`ARP_REF_MAP`과 `_CTRL_SEARCH_PATTERNS`가 서로 불일치**하는 것이 실제 원인이다. ProjectPlan의 제안은 우회책에 해당한다.

### 증거

`ARP_REF_MAP` (line 47-48):
```python
"back_leg_l": ["thigh_b_ref.l", "thigh_ref.l", "leg_ref.l"],
"back_leg_r": ["thigh_b_ref.r", "thigh_ref.r", "leg_ref.r"],
```
→ 3본 체인, 첫 본이 `thigh_b` (dog 프리셋 3-bone leg의 shoulder/hip 위치).

`_CTRL_SEARCH_PATTERNS` (line 1595-1596):
```python
"back_leg_l": [r"^c_thigh_fk\.l", r"^c_leg_fk\.l", r"^c_foot_fk\.l"],
"back_leg_r": [r"^c_thigh_fk\.r", r"^c_leg_fk\.r", r"^c_foot_fk\.r"],
```
→ 3 패턴이지만 `c_thigh_b`가 없고, `c_foot_fk`는 별도 역할(`back_foot_l/r`)의 소관.

`ARP_CTRL_MAP` (line 66-67)도 동일한 잘못된 구성.

### 데이터 흐름으로 본 실패 경로

1. Build Rig 단계: `deform_to_ref`가 소스 뒷다리 3본을 `[thigh_b_ref, thigh_ref, leg_ref]`에 1:1 매핑 (정상).
2. Bake 준비 단계(`arp_convert_addon.py:2499`): `ctrl_map = discover_arp_ctrl_map(arp_obj)` 호출.
3. 잘못된 패턴 때문에 `ctrl_map["back_leg_l"] = ["c_thigh_fk.l", "c_leg_fk.l", "c_foot_fk.l"]` 반환.
4. `ref_to_role_idx["thigh_b_ref.l"] = ("back_leg_l", 0)` → idx 0 → `ctrl_map["back_leg_l"][0] = c_thigh_fk.l`.
5. 결과: 소스 shoulder → `c_thigh_fk.l` (두 번째 본)에 COPY_TRANSFORMS. 한 본씩 밀려서 오차 발생.

참고: 앞다리 `front_leg_l/r`은 `c_thigh_b_dupli_\d+\.l`이 첫 패턴에 있어 정상 동작한다. 뒷다리에만 버그가 있다.

## 목표

- `back_leg_l/r`의 shoulder(`c_thigh_b`)가 ctrl_map에 올바르게 포함되도록 패턴을 바로잡는다.
- 같은 종류의 ref/ctrl 불일치가 재발하지 않도록 Python 레벨 회귀 테스트를 추가한다.
- ProjectPlan이 제안한 "bone_pairs에서 IK 이름 직접 조립" 우회는 불필요하므로 채택하지 않는다.
- Addon `BuildRig` bone_pairs 구성 로직(line 2494~2549)은 **수정하지 않는다** — ctrl_map이 올바르면 현재 로직 그대로 정상 동작한다.

Non-goals:
- `skeleton_analyzer.py`의 대대적인 리팩터링.
- 다른 역할(`spine`, `neck`, `tail`, `ear` 등) 패턴 재검토는 이 스펙 범위 밖. 단, 신규 테스트는 비-multi 역할 전체를 커버하므로 다른 불일치도 감지된다.

## 변경 사항

### 1. `_CTRL_SEARCH_PATTERNS` 수정

파일: `scripts/skeleton_analyzer.py`, 대략 line 1595-1596

```python
# Before
"back_leg_l": [r"^c_thigh_fk\.l", r"^c_leg_fk\.l", r"^c_foot_fk\.l"],
"back_leg_r": [r"^c_thigh_fk\.r", r"^c_leg_fk\.r", r"^c_foot_fk\.r"],

# After
"back_leg_l": [r"^c_thigh_b\.l", r"^c_thigh_fk\.l", r"^c_leg_fk\.l"],
"back_leg_r": [r"^c_thigh_b\.r", r"^c_thigh_fk\.r", r"^c_leg_fk\.r"],
```

### 2. `ARP_CTRL_MAP` 일관성 수정

파일: `scripts/skeleton_analyzer.py`, 대략 line 66-67

```python
# Before
"back_leg_l": ["c_thigh_fk.l", "c_leg_fk.l", "c_foot_fk.l"],
"back_leg_r": ["c_thigh_fk.r", "c_leg_fk.r", "c_foot_fk.r"],

# After
"back_leg_l": ["c_thigh_b.l", "c_thigh_fk.l", "c_leg_fk.l"],
"back_leg_r": ["c_thigh_b.r", "c_thigh_fk.r", "c_leg_fk.r"],
```

`ARP_CTRL_MAP`은 현재 활성 코드 경로에서 직접 참조되지 않을 가능성이 있지만(레거시 `.bmap` 경로), 같은 의미 영역의 상수이므로 일관성 차원에서 함께 수정한다. 수정 후 사용처를 `Grep`으로 확인해 부작용이 있으면 별도 노트에 기록한다.

### 3. 회귀 테스트 추가

파일: `tests/test_skeleton_analyzer.py` (기존 파일에 신규 테스트 클래스 추가)

```python
class TestRoleMapConsistency:
    """ARP_REF_MAP과 _CTRL_SEARCH_PATTERNS의 역할별 일관성을 보장한다."""

    def test_ref_map_and_ctrl_patterns_cover_same_roles(self):
        """단일 본 역할은 ref_map과 ctrl_patterns에 모두 등장해야 한다."""
        from skeleton_analyzer import (
            ARP_REF_MAP,
            _CTRL_SEARCH_PATTERNS,
            _MULTI_BONE_ROLES,
        )
        single_roles = set(ARP_REF_MAP) - _MULTI_BONE_ROLES
        for role in single_roles:
            assert role in _CTRL_SEARCH_PATTERNS, f"{role} missing in _CTRL_SEARCH_PATTERNS"

    def test_single_bone_ctrl_patterns_cover_all_refs(self):
        """단일 본 역할에서 ctrl 패턴 수는 ref 수 이상이어야 한다
        (humanoid fallback 패턴을 포함하므로 >=)."""
        from skeleton_analyzer import (
            ARP_REF_MAP,
            _CTRL_SEARCH_PATTERNS,
            _MULTI_BONE_ROLES,
        )
        for role, refs in ARP_REF_MAP.items():
            if role in _MULTI_BONE_ROLES:
                continue
            patterns = _CTRL_SEARCH_PATTERNS.get(role, [])
            assert len(patterns) >= len(refs), (
                f"{role}: refs={len(refs)} > ctrl_patterns={len(patterns)}"
            )

    def test_back_leg_patterns_start_with_thigh_b(self):
        """dog 3-bone 뒷다리의 shoulder(c_thigh_b)는 첫 패턴이어야 한다."""
        from skeleton_analyzer import _CTRL_SEARCH_PATTERNS
        assert _CTRL_SEARCH_PATTERNS["back_leg_l"][0] == r"^c_thigh_b\.l"
        assert _CTRL_SEARCH_PATTERNS["back_leg_r"][0] == r"^c_thigh_b\.r"

    def test_front_leg_patterns_start_with_thigh_b_dupli(self):
        """dog 3-bone 앞다리의 shoulder(c_thigh_b_dupli)는 첫 패턴이어야 한다."""
        from skeleton_analyzer import _CTRL_SEARCH_PATTERNS
        assert _CTRL_SEARCH_PATTERNS["front_leg_l"][0] == r"^c_thigh_b_dupli_\d+\.l"
        assert _CTRL_SEARCH_PATTERNS["front_leg_r"][0] == r"^c_thigh_b_dupli_\d+\.r"
```

테스트 배치는 기존 `test_skeleton_analyzer.py`의 클래스 스타일(TestXxx)을 따른다.

## 검증 절차

각 단계는 순서대로 실행하며, 실패 시 다음 단계로 진행하지 않는다.

1. **TDD 재현**: 테스트만 먼저 추가하고 `pytest tests/test_skeleton_analyzer.py::TestRoleMapConsistency -v` 실행 → `test_back_leg_patterns_start_with_thigh_b`가 **실패**해야 한다(기존 패턴이 `c_thigh_fk`로 시작하므로). 길이 검사 `test_single_bone_ctrl_patterns_cover_all_refs`는 기존 코드에서 3==3이라 통과할 수 있음 — 이는 정상이며, 향후 재발 방어 목적이다. 예상한 실패가 안 나오면 진단이 틀린 것이므로 중단하고 재조사.
2. **패턴 수정**: 변경 사항 1, 2 적용.
3. **테스트 통과**: `pytest tests/test_skeleton_analyzer.py::TestRoleMapConsistency -v` → 전부 통과.
4. **전체 회귀**: `pytest tests/ -v` → 99개 이상 전부 통과.
5. **린트**: `ruff check scripts/` → 에러 0.
6. **Blender 실제 검증**: dog 프리셋 ARP 리그에서 `c_thigh_b.l`, `c_thigh_b.r` 본이 실제로 존재하는지 MCP로 확인. 방법: `mcp_bridge.execute_blender_code`로 `bpy.data.objects[arp_name].data.bones.keys()`에 두 이름이 포함되는지 검사.
7. **여우 리그 F12 베이크**: Build Rig → Step 4 Bake 실행. 이전에 관찰된 **leg 0.186m 오차가 해소**되는지 확인. (이 단계는 사용자 GUI 수동 검증.)

## 위험 및 주의

- **Blender에서 `c_thigh_b.l` 실존 확인 필요**: dog 프리셋의 실제 명명 규칙이 `c_thigh_b.l`인지 다른 접미사/숫자가 붙는지 확인해야 한다. `_dupli` 복제 앞다리와 달리 뒷다리는 복제본이 아니므로 단순 `.l/.r`일 가능성이 높지만, 검증 절차 6단계(MCP 본 이름 조회)가 통과하기 전까지는 가정 상태다. 검증 실패 시 패턴을 실제 이름에 맞춰 조정한다.
- **`ARP_CTRL_MAP` 사용처 확인**: 수정 전에 `Grep`으로 호출 경로를 확인한다. 레거시 경로에서만 쓰이면 영향 없음, 활성 경로에서 쓰이면 해당 호출부 재검토.
- **기존 테스트가 잘못된 상태를 고착화했을 가능성**: 현재 99개 테스트 중 기존 ctrl map 구조를 검증하는 것이 있으면 같이 갱신해야 한다. 2단계 전에 `Grep "c_foot_fk" tests/`로 확인.
- **Blender GUI 검증 비용**: F12 전체 베이크는 사용자 수동 실행이 필요하다. 이 스펙으로 자동화할 수는 없고, 코드 수정 후 한 번 요청해야 한다.

## 기대 효과

- F12 FK→IK 전환에서 뒷다리 매핑이 정확해져 leg 0.186m 오차 해소.
- ProjectPlan에서 제안했던 우회책(bone_pairs 직접 조립)이 불필요해짐 → addon 코드 증가 없이 블로커 해결.
- 역할 맵 불일치류 버그가 Python 단위 테스트로 잡힘 → 향후 회귀 방어.

## 스펙 범위 밖

- 앞다리 패턴 리팩터링, spine/neck/tail/ear 패턴 개선.
- `arp_convert_addon.py`의 2969줄 분할, 레거시 스크립트 정리, 개발 피드백 루프 개선.
- 이들은 F12 블로커가 해소되고 베이크 품질이 확인된 뒤 별도 브레인스토밍/스펙으로 다룬다 (2026-04-05 사용자 결정: "F12 먼저 끝내고 나머지").

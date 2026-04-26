# F12 뒷다리 shoulder 매핑 버그 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `_CTRL_SEARCH_PATTERNS` / `ARP_CTRL_MAP`의 `back_leg_l/r` 패턴을 `ARP_REF_MAP`과 일치하도록 수정하여 F12 COPY_TRANSFORMS 베이크에서 뒷다리 shoulder(`c_thigh_b`)가 올바르게 매핑되도록 한다.

**Architecture:** TDD. 먼저 회귀 테스트 4개를 추가해 현재 버그를 Python 레벨에서 재현 → 패턴 2군데 수정 → 전체 회귀 + 린트 → Blender MCP로 `c_thigh_b.l/.r` 실존 확인 → 사용자 GUI 베이크 검증.

**Tech Stack:** Python 3.11, pytest, ruff, Blender 4.5 + Auto-Rig Pro (dog preset), BlenderMCP 브릿지.

**Spec:** `docs/superpowers/specs/2026-04-05-f12-back-leg-shoulder-fix-design.md`

**Pre-flight 확인 (이미 완료)**:
- `ARP_CTRL_MAP` 활성 사용처 없음 (정의부 + 문서만)
- 기존 테스트에 `c_foot_fk` 참조 없음 → 기존 테스트 갱신 불필요
- `tests/test_skeleton_analyzer.py`는 `import skeleton_analyzer as sa` 스타일 사용

---

## Task 1: 회귀 테스트 추가 (TDD — 실패 재현)

**Files:**
- Modify: `tests/test_skeleton_analyzer.py` (파일 끝에 신규 클래스 추가)

- [ ] **Step 1: 기존 테스트 파일 끝의 빈 줄 상태를 Read로 확인**

Run: `Read tests/test_skeleton_analyzer.py` (last 20 lines)
목적: 추가할 위치와 기존 import 스타일 확인. 기존 파일은 `import skeleton_analyzer as sa`를 이미 top에서 import 하므로 신규 테스트에서 재사용한다.

- [ ] **Step 2: `TestRoleMapConsistency` 클래스를 파일 끝에 추가**

`tests/test_skeleton_analyzer.py` 끝에 아래 코드를 덧붙인다. 기존 top-level `import skeleton_analyzer as sa`를 사용한다.

```python


class TestRoleMapConsistency:
    """ARP_REF_MAP과 _CTRL_SEARCH_PATTERNS의 역할별 일관성을 보장한다.

    단일 본 역할(non-multi)에 대해 ref 맵과 ctrl 검색 패턴이 서로
    동기화되어 있는지 Python 레벨에서 검증한다. F12 베이크에서 발생한
    back_leg shoulder 누락 같은 불일치 버그를 조기에 잡기 위한 회귀 테스트.
    """

    def test_ref_map_and_ctrl_patterns_cover_same_roles(self):
        """단일 본 역할은 ref_map과 ctrl_patterns에 모두 등장해야 한다."""
        single_roles = set(sa.ARP_REF_MAP) - sa._MULTI_BONE_ROLES
        for role in single_roles:
            assert role in sa._CTRL_SEARCH_PATTERNS, (
                f"{role} missing in _CTRL_SEARCH_PATTERNS"
            )

    def test_single_bone_ctrl_patterns_cover_all_refs(self):
        """단일 본 역할에서 ctrl 패턴 수는 ref 수 이상이어야 한다.

        humanoid fallback 패턴이 함께 나열되는 경우가 있으므로 >=로 검사.
        """
        for role, refs in sa.ARP_REF_MAP.items():
            if role in sa._MULTI_BONE_ROLES:
                continue
            patterns = sa._CTRL_SEARCH_PATTERNS.get(role, [])
            assert len(patterns) >= len(refs), (
                f"{role}: refs={len(refs)} > ctrl_patterns={len(patterns)}"
            )

    def test_back_leg_patterns_start_with_thigh_b(self):
        """dog 3-bone 뒷다리의 shoulder(c_thigh_b)는 첫 패턴이어야 한다."""
        assert sa._CTRL_SEARCH_PATTERNS["back_leg_l"][0] == r"^c_thigh_b\.l"
        assert sa._CTRL_SEARCH_PATTERNS["back_leg_r"][0] == r"^c_thigh_b\.r"

    def test_front_leg_patterns_start_with_thigh_b_dupli(self):
        """dog 3-bone 앞다리의 shoulder(c_thigh_b_dupli)는 첫 패턴이어야 한다."""
        assert sa._CTRL_SEARCH_PATTERNS["front_leg_l"][0] == r"^c_thigh_b_dupli_\d+\.l"
        assert sa._CTRL_SEARCH_PATTERNS["front_leg_r"][0] == r"^c_thigh_b_dupli_\d+\.r"
```

- [ ] **Step 3: 신규 테스트만 실행해서 예상한 실패 확인**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_skeleton_analyzer.py::TestRoleMapConsistency -v
```

Expected:
- `test_ref_map_and_ctrl_patterns_cover_same_roles` → **PASS** (역할 키 자체는 양쪽에 존재)
- `test_single_bone_ctrl_patterns_cover_all_refs` → **PASS** (기존 3 refs == 3 patterns이므로 `>=` 통과)
- `test_back_leg_patterns_start_with_thigh_b` → **FAIL** (현재 첫 패턴이 `^c_thigh_fk\.l`이므로)
- `test_front_leg_patterns_start_with_thigh_b_dupli` → **PASS**

→ 총 1 failed, 3 passed. 이 분포가 아니면 진단이 틀렸거나 테스트 작성이 잘못된 것이므로 중단하고 재조사.

- [ ] **Step 4: 테스트 파일만 커밋 (Red 상태)**

```bash
git add tests/test_skeleton_analyzer.py
git commit -m "test(F12): 역할 맵 일관성 회귀 테스트 추가 — back_leg shoulder 누락 재현"
```

---

## Task 2: `_CTRL_SEARCH_PATTERNS.back_leg_l/r` 수정 (Green 1차)

**Files:**
- Modify: `scripts/skeleton_analyzer.py:1595-1596`

- [ ] **Step 1: 해당 라인 Read로 확인**

Run: `Read scripts/skeleton_analyzer.py` offset=1590 limit=15

확인 대상:
```python
"back_leg_l": [r"^c_thigh_fk\.l", r"^c_leg_fk\.l", r"^c_foot_fk\.l"],
"back_leg_r": [r"^c_thigh_fk\.r", r"^c_leg_fk\.r", r"^c_foot_fk\.r"],
```

- [ ] **Step 2: Edit로 패턴 교체**

Edit `scripts/skeleton_analyzer.py`:
- old_string:
```python
    "back_leg_l": [r"^c_thigh_fk\.l", r"^c_leg_fk\.l", r"^c_foot_fk\.l"],
    "back_leg_r": [r"^c_thigh_fk\.r", r"^c_leg_fk\.r", r"^c_foot_fk\.r"],
```
- new_string:
```python
    "back_leg_l": [r"^c_thigh_b\.l", r"^c_thigh_fk\.l", r"^c_leg_fk\.l"],
    "back_leg_r": [r"^c_thigh_b\.r", r"^c_thigh_fk\.r", r"^c_leg_fk\.r"],
```

근거: `ARP_REF_MAP["back_leg_l"] = [thigh_b_ref.l, thigh_ref.l, leg_ref.l]`과 1:1 대응. `c_foot_fk`는 `back_foot_l` 역할 소관이므로 제거.

- [ ] **Step 3: 신규 테스트가 통과하는지 확인**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_skeleton_analyzer.py::TestRoleMapConsistency -v
```

Expected: 4 passed.

특히 `test_back_leg_patterns_start_with_thigh_b`가 PASS여야 한다. 실패하면 old_string/new_string에 오타가 있는지 확인.

---

## Task 3: `ARP_CTRL_MAP.back_leg_l/r` 일관성 수정

**Files:**
- Modify: `scripts/skeleton_analyzer.py:66-67`

- [ ] **Step 1: 해당 라인 Read로 확인**

Run: `Read scripts/skeleton_analyzer.py` offset=60 limit=20

확인 대상:
```python
    "back_leg_l": ["c_thigh_fk.l", "c_leg_fk.l", "c_foot_fk.l"],
    "back_leg_r": ["c_thigh_fk.r", "c_leg_fk.r", "c_foot_fk.r"],
```

- [ ] **Step 2: Edit로 값 교체**

Edit `scripts/skeleton_analyzer.py`:
- old_string:
```python
    "back_leg_l": ["c_thigh_fk.l", "c_leg_fk.l", "c_foot_fk.l"],
    "back_leg_r": ["c_thigh_fk.r", "c_leg_fk.r", "c_foot_fk.r"],
```
- new_string:
```python
    "back_leg_l": ["c_thigh_b.l", "c_thigh_fk.l", "c_leg_fk.l"],
    "back_leg_r": ["c_thigh_b.r", "c_thigh_fk.r", "c_leg_fk.r"],
```

근거: `ARP_REF_MAP`과 1:1, `_CTRL_SEARCH_PATTERNS`와도 일관. `ARP_CTRL_MAP`은 현재 활성 코드 경로에서 직접 참조되지 않지만(사전 조사 완료) 같은 의미 영역의 상수이므로 함께 맞춰둔다.

- [ ] **Step 3: 신규 테스트 재실행 — 여전히 통과**

Run:
```
.venv/Scripts/python.exe -m pytest tests/test_skeleton_analyzer.py::TestRoleMapConsistency -v
```

Expected: 4 passed.

(이 변경은 `ARP_CTRL_MAP`만 건드리므로 위 테스트 결과에는 영향 없음. 정상 동작 확인만.)

---

## Task 4: 전체 회귀 + 린트

**Files:**
- 없음 (검증만)

- [ ] **Step 1: 전체 pytest 실행**

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -v
```

Expected: **103 passed** (기존 99 + 신규 4), 0 failed.

실패가 하나라도 있으면 중단. 실패한 테스트가 본 변경과 관련 있으면 분석 후 조정. 무관하면 기존 환경 이슈 보고.

- [ ] **Step 2: ruff 린트**

Run:
```
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```

Expected: `All checks passed!`

에러 있으면 수정 후 재실행.

- [ ] **Step 3: 코드 수정 커밋 (Green 최종)**

```bash
git add scripts/skeleton_analyzer.py
git commit -m "fix(F12): 뒷다리 shoulder 매핑 복구 — _CTRL_SEARCH_PATTERNS + ARP_CTRL_MAP 동기화

ARP_REF_MAP[back_leg_l]의 첫 본은 thigh_b_ref인데 _CTRL_SEARCH_PATTERNS
는 c_thigh_fk부터 시작하고 대신 c_foot_fk(다른 역할 소관)가 들어가
있어, F12 COPY_TRANSFORMS 베이크에서 소스 shoulder가 c_thigh_fk에
잘못 매핑되었다(한 본씩 밀림, 0.186m leg 오차의 유력 원인).

패턴을 [c_thigh_b, c_thigh_fk, c_leg_fk]로 수정하고 ARP_CTRL_MAP도
동일하게 맞춘다. 회귀 방어 테스트는 이전 커밋(test: 역할 맵 일관성)
에서 추가됨.

Spec: docs/superpowers/specs/2026-04-05-f12-back-leg-shoulder-fix-design.md"
```

---

## Task 5: Blender MCP로 `c_thigh_b.l/.r` 실존 확인

**Files:**
- 없음 (Blender 런타임 검증)

이 단계는 BlenderMCP 브릿지가 활성 상태여야 한다. 비활성이면 "사용자에게 Blender 쪽에서 BlenderMCP Start 요청" 후 진행.

- [ ] **Step 1: 현재 씬에 dog 프리셋 ARP 리그가 있는지 확인**

`mcp__blender__get_scene_info` 호출 → armature 목록 확인. ARP 리그가 없으면 (a) 사용자가 기존 여우/dog 리그 파일을 여는 것을 기다리거나 (b) 이 Task를 스킵하고 사용자가 직접 GUI 검증 시 확인하도록 안내.

- [ ] **Step 2: MCP로 본 이름 조회**

`mcp__blender__execute_blender_code` 호출, 코드:
```python
import bpy
arp = next((o for o in bpy.data.objects if o.type == "ARMATURE" and "c_pos" in o.data.bones), None)
if arp is None:
    print("NO_ARP_RIG_FOUND")
else:
    bones = set(arp.data.bones.keys())
    targets = ["c_thigh_b.l", "c_thigh_b.r"]
    for t in targets:
        print(f"{t}: {'OK' if t in bones else 'MISSING'}")
    # 전체 c_thigh_b* 매칭 출력 (접미사 변형 확인용)
    matches = sorted([b for b in bones if b.startswith("c_thigh_b")])
    print(f"matches: {matches}")
```

Expected:
```
c_thigh_b.l: OK
c_thigh_b.r: OK
matches: ['c_thigh_b.l', 'c_thigh_b.r', 'c_thigh_b_dupli_001.l', 'c_thigh_b_dupli_001.r', ...]
```

- [ ] **Step 3: 분기 — 이름이 다르면 패턴 재조정**

결과가 `MISSING`이거나 `matches`에 다른 접미사(예: `c_thigh_b_fk.l`)가 나오면:
- 실제 이름을 확인한 뒤 Task 2의 패턴을 해당 이름에 맞게 재수정
- 신규 테스트의 기대값도 함께 갱신
- Task 4 다시 실행

`OK`면 다음 Task로.

- [ ] **Step 4: 확인 결과를 커밋 메시지에 남길지 판단**

실존 확인이 가정을 검증했을 뿐이므로 별도 커밋 없음. 다만 `c_thigh_b`의 실제 존재 여부가 가정과 달랐으면 Task 3에서 재수정 커밋이 발생하고, 이때 메시지에 "MCP 검증 결과 실제 본 이름 X → 패턴 조정" 명시.

---

## Task 6: 사용자 GUI 베이크 검증 요청

**Files:**
- 없음 (사용자 수동 검증)

이 Task는 에이전트가 직접 수행할 수 없다. 사용자에게 검증을 요청하고 결과를 기다린다.

- [ ] **Step 1: 사용자에게 검증 요청 메시지 전달**

메시지 내용:
> F12 베이크 검증을 요청합니다.
> 1. 여우(또는 다른 dog 프리셋 변환 대상) 소스 리그 파일 열기
> 2. ARP Convert 패널 → Step 1~3 수행 (Analyze → Preview → Build Rig)
> 3. Step 4 (애니메이션 베이크) 실행
> 4. 생성된 ARP 리그의 뒷다리 프레임별 위치가 원본과 일치하는지 확인
> 5. 이전에 관찰된 **leg 0.186m 오차가 해소**되었는지 확인
>
> 결과를 알려주시면 F12 블로커 해결 여부를 확정하고 ProjectPlan을 갱신합니다.

- [ ] **Step 2: 사용자 응답 대기**

결과에 따라:
- **성공**: Task 7로 진행
- **실패** (오차 여전함): 추가 조사 필요 — 본 매핑 외 다른 원인(IK solver, 포즈본 좌표계 등)일 가능성. 이 플랜 범위 밖이므로 별도 브레인스토밍 요청.

---

## Task 7: ProjectPlan.md 갱신 + 최종 커밋

**Files:**
- Modify: `docs/ProjectPlan.md` (F12 상태 섹션)

- [ ] **Step 1: ProjectPlan의 F12 현재 블로커 기록 제거/갱신**

`docs/ProjectPlan.md:150-154` 근처의 "남은 이슈: discover_arp_ctrl_map..." 문단을 다음으로 교체:

Edit 대상 문단 (현재):
```
- FK→IK 전환 진행 중: FK Z축 잠금 → leg 0.186m 오차 → IK 모드로 전환 결정
  - `_ensure_ik_mode()` 구현 완료 (ik_fk_switch = 0.0)
  - bone_pairs IK 매핑 로직 구현 완료 (다리 중간 본 제거, foot→IK foot)
  - 남은 이슈: `discover_arp_ctrl_map()`이 FK 컨트롤러만 반환하여 shoulder(c_thigh_b)를 못 잡음
  - 해결 방향: bone_pairs 생성 시 leg 역할을 ctrl_map 의존 대신 직접 IK 이름 구성
```

교체 (사용자 검증 결과를 반영):
```
- FK→IK 전환 완료 (2026-04-05):
  - `_ensure_ik_mode()` 구현 (ik_fk_switch = 0.0)
  - bone_pairs IK 매핑 로직 구현 (다리 중간 본 제거, foot→IK foot)
  - back_leg shoulder 매핑 복구: `_CTRL_SEARCH_PATTERNS["back_leg_l/r"]`가
    `ARP_REF_MAP`과 불일치(c_thigh_b 누락)했던 근본 원인 수정. 회귀 테스트 4개 추가.
  - 여우 리그 검증 결과: leg 0.186m 오차 해소 확인
```

**주의**: 사용자 검증 결과가 "해소됨"일 때만 이 문단으로 갱신한다. 결과가 다르면 해당 결과를 그대로 기록한다.

- [ ] **Step 2: ProjectPlan 커밋**

```bash
git add docs/ProjectPlan.md
git commit -m "docs(F12): 뒷다리 shoulder 블로커 해결 기록 — back_leg 패턴 수정 완료"
```

- [ ] **Step 3: 상태 최종 확인**

Run:
```
git log --oneline -10
git status
.venv/Scripts/python.exe -m pytest tests/ -v --tb=no -q
```

Expected:
- 최근 커밋 3개: `docs(F12)`, `fix(F12)`, `test(F12)` (+ 기존 스펙 커밋)
- `git status`: clean (또는 사전 변경 파일만 남음)
- 테스트: 103 passed

---

## 완료 기준

- [ ] 신규 회귀 테스트 4개 추가됨 (`TestRoleMapConsistency`)
- [ ] `_CTRL_SEARCH_PATTERNS["back_leg_l/r"]` 수정됨
- [ ] `ARP_CTRL_MAP["back_leg_l/r"]` 수정됨
- [ ] `pytest tests/ -v` 103 passed
- [ ] `ruff check scripts/ tests/` 통과
- [ ] Blender MCP로 `c_thigh_b.l/.r` 실존 확인됨 (또는 실제 이름에 맞춰 재조정)
- [ ] 사용자 GUI 베이크에서 leg 오차 해소 확인됨
- [ ] `docs/ProjectPlan.md` F12 섹션 갱신됨
- [ ] 커밋 3개 (test / fix / docs) — 또는 MCP 재조정 시 추가 커밋 포함

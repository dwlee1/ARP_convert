# 작업 프로세스 규칙 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `CLAUDE.md`에 `## Workflow` 섹션(6개 서브섹션)을 추가해 브랜치/커밋/문서 워크플로 규칙을 명문화한다.

**Architecture:** 단일 파일(`CLAUDE.md`)에 신규 섹션을 파일 끝에 추가하는 순수 문서 작업. Hook, CI, 코드 변경 없음. 기존 섹션은 수정하지 않음.

**Tech Stack:** Markdown only. 검증은 pytest + ruff를 안전망으로 돌려 코드 회귀 없음만 확인.

**Spec:** `docs/superpowers/specs/2026-04-05-workflow-rules-design.md`

**Pre-flight (이미 완료)**:
- CLAUDE.md 현재 구조 파악: 파일 끝에 `## 작업 원칙` 섹션이 존재 (line 105-111)
- 신규 `## Workflow` 섹션을 `## 작업 원칙` 뒤에 추가 (파일 최하단)

---

## Task 1: CLAUDE.md에 `## Workflow` 섹션 추가

**Files:**
- Modify: `CLAUDE.md` (파일 끝에 신규 섹션 추가)

### Step 1: 현재 CLAUDE.md 끝 상태 확인

Run: Read `CLAUDE.md` offset=100 limit=20

확인 대상:
- 파일이 line 111 `- fixture/회귀 도구를 늘리는 것보다 자동 역할 추론 정확도 개선을 우선한다` 뒤에서 끝나는지
- 마지막 줄 뒤에 빈 줄이 있는지 여부 (있으면 그대로 두고, 없으면 추가 시 포함)

### Step 2: 파일 끝에 `## Workflow` 섹션 추가

Edit `CLAUDE.md`:
- old_string:
```
- fixture/회귀 도구를 늘리는 것보다 자동 역할 추론 정확도 개선을 우선한다
```
- new_string:
````
- fixture/회귀 도구를 늘리는 것보다 자동 역할 추론 정확도 개선을 우선한다

## Workflow

개발 작업을 일관되게 진행하기 위한 규칙. 2026-04-05 F12 작업에서 superpowers 스킬 풀 사이클을 첫 적용한 경험을 토대로 합의됨.

### 브랜치 전략

- 새 기능/버그 수정은 `feat/<name>` 또는 `fix/<name>` 브랜치에서 작업한다
- `master`는 fast-forward 머지만 허용 (`git merge --ff-only`)
- 브랜치명 예시: `feat/f8-weight-verify`, `fix/f12-back-leg-shoulder`
- 예외: 오탈자/주석 등 1-3줄 문서 단독 수정은 master에 직행해도 된다

### 커밋 메시지 컨벤션

Conventional Commits 형식: `type(scope): subject`

- **type**: `feat` | `fix` | `docs` | `test` | `refactor` | `chore`
- **scope**: 기능 ID(`F12`, `F8`) 또는 하위 영역(`addon`, `mcp`, `analyzer`)
- **subject**: 한국어/영어 자유, 무엇을/왜 간결하게

좋은 예: `fix(F12): 뒷다리 shoulder 매핑 복구 — c_thigh_b 누락`
나쁜 예: `남은 파일 다 추가`, `WIP`, `fix`

본문(선택)에는 **왜** 바꿨는지와 참고할 커밋 SHA, 스펙 경로를 남긴다.

### 브레인스토밍 / 스펙이 필수인 작업

다음 중 **하나라도** 해당하면 `superpowers:brainstorming` → `writing-plans` → `subagent-driven-development` 풀 사이클로 진행한다:

- 3개 이상의 파일에 걸친 변경
- 아키텍처 결정이 필요한 작업 (라이브러리 선택, 파일 분할, 인터페이스 설계)
- 동작 변경이 기존 사용자에게 영향을 주는 작업
- 요구사항이 불명확하거나 여러 해석이 가능한 작업

**바로 구현해도 되는 작업**:

- 오탈자, 1-3줄 명확한 버그 수정
- 문서 업데이트
- 기존 패턴을 그대로 따르는 작은 추가 (함수 하나 추가, 테스트 하나 추가)

애매하면 브레인스토밍 쪽으로 기운다. 오버슛이 언더슛보다 싸다.

### ProjectPlan.md 업데이트

- 작업 완료 시점에 해당 머지/PR 흐름 안에서 함께 갱신한다
- 별도 "docs 업데이트" 커밋으로 미루지 않는다 (상태가 표류함)
- 우선순위 목록은 머지 직후 재정렬을 검토한다

### Spec / Plan 파일 위치

- Spec: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plan: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- 브랜치 단위로 쌍(스펙-플랜-구현)이 맞물린다. 이름의 topic은 브랜치명과 정렬시킨다

### 완료 기준

구현 작업은 다음을 모두 만족해야 "완료"로 본다:

- `pytest tests/ -v` 전부 통과
- `ruff check scripts/ tests/` 통과
- 관련 문서(ProjectPlan.md + 해당 feature 문서) 갱신됨
- 피처 브랜치가 master에 fast-forward 머지됨 (또는 명시적으로 "keep" 상태)
````

### Step 3: 추가된 섹션이 정상 렌더되는지 Read로 확인

Run: Read `CLAUDE.md` offset=110 limit=80

확인 대상:
- `## Workflow` 헤더가 존재
- 6개 서브섹션(`### 브랜치 전략`, `### 커밋 메시지 컨벤션`, `### 브레인스토밍 / 스펙이 필수인 작업`, `### ProjectPlan.md 업데이트`, `### Spec / Plan 파일 위치`, `### 완료 기준`)이 모두 존재
- 기존 `## 작업 원칙` 섹션이 훼손 없이 유지됨

### Step 4: 코드 회귀 없음 확인 (안전망)

Run:
```
.venv/Scripts/python.exe -m pytest tests/ -v --tb=no -q
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```

Expected:
- pytest: 103 passed (또는 현재 기준값 — 이 Task 시작 직전의 숫자와 동일)
- ruff: `All checks passed!`

문서만 건드렸으므로 회귀가 있으면 CLAUDE.md 외의 변경이 섞인 것. 즉시 중단하고 원인 조사.

### Step 5: 커밋

```bash
git add CLAUDE.md
git commit -m "$(cat <<'EOF'
docs(workflow): CLAUDE.md에 Workflow 섹션 추가

브랜치 전략, 커밋 컨벤션, 브레인스토밍 필수 조건, ProjectPlan 갱신
규칙, spec/plan 파일 위치, 완료 기준 6개 서브섹션 명문화. Hook/CI
없이 문서화만으로 진행.

3개 통합 개선 sub-project ①/③ 구현 완료.

Spec: docs/superpowers/specs/2026-04-05-workflow-rules-design.md
EOF
)"
```

### Step 6: 커밋 확인

Run:
```
git log --oneline -3
git diff HEAD~1 HEAD -- CLAUDE.md | head -20
```

Expected:
- 최신 커밋: `docs(workflow): CLAUDE.md에 Workflow 섹션 추가`
- diff가 CLAUDE.md 파일에 추가(+) 라인만 포함, 기존 라인 수정이 없어야 함

---

## 완료 기준

- [ ] CLAUDE.md에 `## Workflow` 섹션 추가됨 (파일 끝)
- [ ] 6개 서브섹션 모두 존재
- [ ] 기존 섹션(`## 작업 원칙` 포함 전체) 훼손 없음
- [ ] `pytest tests/ -v` 변화 없음 (Task 시작 직전의 숫자와 동일)
- [ ] `ruff check scripts/ tests/` clean
- [ ] 커밋 1개 생성, 메시지 형식 컨벤션 준수
- [ ] 스펙에 명시된 모든 규칙이 문서에 반영됨

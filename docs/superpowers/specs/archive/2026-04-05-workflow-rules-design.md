# 작업 프로세스 규칙 문서화 설계 (Sub-project ①)

> 작성일: 2026-04-05
> Sub-project: 3개 통합 개선의 1/3 (작업 프로세스 → MCP 피드백 루프 → 코드 건강)
> 연관: `CLAUDE.md`, 2026-04-05 F12 작업에서 superpowers 풀 사이클 첫 적용 경험

## 문제 요약

BlenderRigConvert 프로젝트의 git 브랜치/커밋/문서 워크플로가 암묵적 관행으로만 존재한다.

관찰된 현실(2026-04-05 기준):
- 이전까지 `master` 직행이 관행. F12 작업부터 피처 브랜치(`fix/f12-back-leg-shoulder`) 사용 시작
- 커밋 메시지 대부분 Conventional Commits에 근접(`feat(F12): ...`) 하지만 예외 존재(`0592c4e "남은 파일 다 추가"`)
- superpowers 스킬(brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch) 풀 사이클이 이번이 첫 적용
- ProjectPlan.md 갱신은 이뤄지지만 "언제/누가 갱신한다"는 규칙 없음
- CLAUDE.md에 코드 관련 HARD RULE은 있지만 프로세스 규칙은 없음

이 상태는 1인 개발 환경에서 **지금은** 동작하지만, 장기 프로젝트와 AI 협업에서 일관성을 잃기 쉽다. 동일한 작업을 매번 다른 방식으로 진행하게 되는 표류(drift)를 문서화로 방지한다.

## 목표

- `CLAUDE.md`에 `## Workflow` 섹션 추가. 브랜치 전략, 커밋 컨벤션, 브레인스토밍 필수 여부, ProjectPlan.md 갱신 규칙, spec/plan 파일 위치, 완료 기준을 명문화한다.
- 규칙은 **문서화**만 한다 — hook, CI, GitHub Actions를 추가하지 않는다.
- 기존 섹션은 수정하지 않는다.

Non-goals:
- Pre-commit hook / commit-msg hook 설치
- GitHub Actions 또는 로컬 CI 구성
- 기존 `## 작업 원칙` 섹션 개편 또는 통합 (이 섹션은 코드 레벨 원칙이고 Workflow는 프로세스 레벨이므로 분리 유지)
- CLAUDE.md line 100의 stale 경로(`C:\Users\manag\Desktop\...`) 수정 — 별도 이슈
- 기존 레거시 파일 정리, 아카이빙 — Sub-project ③ 범위

## 설계 결정: 강제 수준

### 검토한 옵션

1. **가이드라인만 (문서화)** — 선택
2. 가이드라인 + pre-commit hook으로 commit 메시지 형식 검증
3. 가이드라인 + superpowers 스킬 트리거 규칙을 별도로 명문화

### 선택 근거

- **1인 개발 + Claude Code 조합**: hook은 "팀원이 규칙을 잊을까 봐" 방지하는 장치. 사용자 1명 + AI 1명 구조에서 중복.
- **Hook의 실제 비용**: Windows + bash + Blender venv 환경에서 pre-commit 프레임워크를 더하면 한 레이어 더 깨질 수 있음 (세션 초반 세팅에서 이미 호환성 이슈 관찰). 매 커밋마다 수 초 딜레이.
- **Superpowers 스킬 자체가 이미 강제 규칙 보유**: `brainstorming`의 HARD-GATE, `writing-plans`의 "No Placeholders" 등. 프로젝트 레벨에서 중복 규칙을 쌓을 필요 없음.
- **F12 사이클에서 실증**: 이번 작업에서 CLAUDE.md HARD RULE을 AI가 잘 따랐고 superpowers 스킬 흐름도 정상 작동. 문서화만으로 이미 작동하는 증거 존재.
- **YAGNI**: 팀 확대 또는 규칙 위반 반복 같은 미래 조건이 발생하면 그때 hook 추가. 지금 선제 구축은 과잉.

## 변경 사항

### 파일: `CLAUDE.md`

**위치**: 파일 끝(`## 작업 원칙` 섹션 뒤)에 `## Workflow` 섹션 신규 추가.

**내용** (복사 가능 형태):

```markdown
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
```

### 기타 파일

없음. 이 sub-project는 `CLAUDE.md` 단일 파일 변경으로 완료된다.

## 검증 절차

1. **마크다운 구문**: `Read CLAUDE.md` 후 구조 확인. 새 섹션이 `## Workflow` 헤더로 시작하고 서브섹션이 `###`로 일관되는지.
2. **기존 섹션 영향 없음**: `git diff CLAUDE.md`가 추가분만 보여주고 기존 줄 수정이 없어야 한다.
3. **코드 회귀 없음**: `pytest tests/ -v` 103 passed, `ruff check scripts/ tests/` clean (CLAUDE.md만 건드리므로 코드 회귀는 없어야 함 — 안전망 확인).
4. **자체 일관성**: 추가한 규칙이 방금 완료한 F12 작업의 실제 흐름과 모순되지 않는지 확인. 예: 브랜치명 예시, 커밋 메시지 예시, 스펙 경로가 실제 F12 작업물과 일치해야 함.

## 위험 및 주의

- **과잉 규정화 위험**: 규칙이 너무 많거나 구체적이면 지켜지지 않는다. 이번 6개 서브섹션은 "반드시 알아야 할 것"만 담았음. 더 추가하고 싶은 충동이 있으면 별도 스펙으로.
- **예외 조항의 남용**: "1-3줄 문서 수정은 master 직행 OK" 같은 예외가 확장 해석되어 사실상 master 직행이 부활할 수 있음. 애매하면 브랜치 쪽으로 기운다.
- **완료 기준의 엄격성**: "문서 갱신"을 완료 기준에 넣었는데, 이번 F12 작업도 ProjectPlan이 linter/수동 수정으로 한 번 편집되어 돌아온 케이스 있었음. 완료 기준을 실제로 만족시키려면 작업 호흡이 조금 길어짐. 이는 의도된 비용.

## 기대 효과

- 다음 sub-project 2, 3부터는 이 규칙을 따라가므로 일관된 페이스 확립.
- AI 세션이 바뀌어도 `CLAUDE.md`를 읽고 같은 방식으로 작업 진행 가능.
- 나중에 F8 검증, 자동 추론 개선 같은 장기 작업에서 브랜치/커밋 추적성 향상.

## Sub-project 연결

이 sub-project 완료 후:
- **Sub-project ② MCP 피드백 루프 확장**: 이 규칙 위에서 설계 진행. 브랜치명 `feat/mcp-feedback-loop` (또는 유사), spec은 `docs/superpowers/specs/YYYY-MM-DD-mcp-feedback-loop-design.md`.
- **Sub-project ③ 코드 건강 (addon 분할 + 레거시 정리)**: ②가 완료되어 MCP 검증 레시피가 준비된 뒤 진행. 대규모 리팩터링이므로 이 Workflow 규칙 + MCP 루프가 안전망.

## 스펙 범위 밖

- Hook / CI / GitHub Actions 설정
- `CLAUDE.md` 기존 섹션 리라이팅 또는 stale 경로 수정
- 커밋 메시지 자동 생성 또는 템플릿
- Sub-project ② ③의 상세 내용 (이번 세션에서 이어서 별도 스펙 작성 예정)

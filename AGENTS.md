# BlenderRigConvert

동물 캐릭터 리그를 Auto-Rig Pro 기반으로 통일하고, 리그 생성을 자동화한다.
리타게팅은 ARP 네이티브 리타겟(`bpy.ops.arp.retarget`)에 위임하는 방식으로 2026-04-06 재설계 완료.

## 환경

- Blender 4.5 LTS + Auto-Rig Pro
- Python 3.11, Windows 11

## 위반 금지 규칙 (HARD RULES)

1. ARP ref 본 추가/삭제에 `edit_bones.new()` 사용 금지 → ARP 네이티브 `set_*` 함수 사용
2. ARP 프리셋은 `dog` 고정
3. face 역할은 unmapped에 통합, 커스텀 본으로 처리 (원본 이름 유지, `custom_bone` 프로퍼티 태깅)
4. `leg` 역할 본이 3개면 ARP도 3본 다리 체인 (`thigh_b_ref` 포함)
5. `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할
6. 코드 수정 시 addon / pipeline / batch 경로 모두 확인

## 기준 문서

- **`docs/ProjectPlan.md`** — 단일 기준 문서 (상태, 체크리스트, 남은 기능). 작업 전 반드시 읽을 것
- `docs/Architecture.md` — 데이터 구조 / 파이프라인 / ARP 내부 API 등 구현 레퍼런스
- `docs/FoxTestChecklist.md` — 여우 파일 테스트 기록
- `docs/RegressionRunner.md` — 대표 샘플 GUI 회귀 테스트 (대량 처리 전략 아님)

## 핵심 규칙

- ARP ref 본은 실제 리그에서 동적 탐색
- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- toe 본이 없으면 `virtual toe` 사용
- ear는 `ear_01_ref / ear_02_ref`에 직접 매핑
- Preview Armature는 원본 이름 유지, 역할은 색상과 커스텀 프로퍼티로 표시
- ARP 기본 face rig는 비활성화 — 얼굴 본(eye, jaw 등)은 cc_ 커스텀 본으로 처리 (ear는 전용 역할)
- 3본 다리 ref 이름은 `_b_` 포함 필수: `thigh_b_ref.l`, 앞다리는 `thigh_b_ref_dupli_001.l`

## 파일 맵

| 파일 | 역할 |
|------|------|
| `scripts/skeleton_analyzer.py` | 구조 분석, Preview Armature 생성, ref 체인 탐색 |
| `scripts/arp_convert_addon.py` | Blender 애드온 엔트리 (bl_info, register/unregister) |
| `scripts/arp_props.py` | PropertyGroup 정의 (Scene 레벨 addon state) |
| `scripts/arp_ui.py` | N-panel UI (7개 서브패널: MainPanel + Step1~5 + Tools) |
| `scripts/arp_role_icons.py` | 역할별 색상 아이콘 (bpy.utils.previews) |
| `scripts/arp_viewport_handler.py` | 뷰포트 부모 체인 하이라이트 핸들러 |
| `scripts/arp_ops_preview.py` | CreatePreview 오퍼레이터 + hierarchy 헬퍼 |
| `scripts/arp_ops_roles.py` | Role editing 오퍼레이터 (SelectBone/SetParent/SetRole) |
| `scripts/arp_ops_build.py` | BuildRig 오퍼레이터 (가장 큰 execute 본문) |
| `scripts/arp_ops_bake_regression.py` | SetupRetarget / ExecuteRetarget / CopyCustomScale / Cleanup + RunRegression 오퍼레이터 |
| `scripts/arp_build_helpers.py` | BuildRig 내부 헬퍼 (ref 메타데이터, deform 매핑) |
| `scripts/arp_def_separator.py` | DEF 본 분리 (역할 기반 계층 + Copy Transforms) |
| `scripts/arp_cc_bones.py` | cc bone 생성 + constraint 복사 |
| `scripts/arp_weight_xfer.py` | 웨이트 전송 로직 |
| `scripts/arp_foot_guides.py` | Foot guide 생성/감지/자동 배치 |
| `scripts/arp_fixture_io.py` | Regression fixture 로딩/적용 |
| `scripts/arp_utils.py` | Blender / ARP 공통 유틸 |
| `scripts/weight_transfer_rules.py` | 웨이트 전송 (Blender 없이 테스트 가능) |
| `scripts/mcp_bridge.py` | blender-mcp 브릿지 (AI → Blender 자동화) |
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 (Build Rig까지) |
| `scripts/03_batch_convert.py` | 배치 실행 경로 |
| `scripts/_oneoff_match_blend_inventory.py` | Unity MigrationInventory ↔ blend 인벤토리 자동 매칭 one-off 스크립트 |

## 작업별 참조 파일

| 작업 | 핵심 파일 | 보조 파일 |
|------|----------|----------|
| 구조 분석/역할 추론 | `skeleton_analyzer.py` | — |
| Preview 생성/편집 | `arp_ops_preview.py`, `arp_ops_roles.py` | `skeleton_analyzer.py` |
| Build Rig 파이프라인 | `arp_ops_build.py` | `skeleton_analyzer.py`, `arp_build_helpers.py`, `arp_def_separator.py`, `arp_cc_bones.py`, `arp_weight_xfer.py`, `arp_foot_guides.py` |
| MCP 자동화 | `mcp_bridge.py` | `arp_utils.py`, `skeleton_analyzer.py` |
| CLI/배치 실행 | `pipeline_runner.py`, `03_batch_convert.py` | `arp_utils.py`, `skeleton_analyzer.py` |
| 리타게팅 | `arp_ops_bake_regression.py`, `arp_retarget.py` | `arp_utils.py` |
| 회귀 테스트 | `arp_ops_bake_regression.py` | `arp_fixture_io.py` |

데이터 구조·파이프라인 흐름·ARP 내부 함수 디테일은 `docs/Architecture.md` 참조.

## 작업 원칙

- 별도 진단 스크립트 단계를 기본 경로로 가정하지 않는다
- 우선순위 기능은 현재 메인 구현 경로를 직접 읽고 수정한다
- ARP 내부 동작 확인이 꼭 필요한 항목만 최소 범위 실험으로 검증한다
- 실행 경로가 여러 갈래이므로 한 경로만 고치고 끝내지 않는다
- fixture/회귀 도구를 늘리는 것보다 자동 역할 추론 정확도 개선을 우선한다

## 검증

코드 수정 후 반드시 실행:
```
pytest tests/ -v
```
`.blend` 기준 검증 항목이 있으면 커밋 메시지에 명시한다.

Blender 연동 변경이 있으면 추가로 확인:
```
ruff check scripts/ tests/
```

애드온/리타겟/MCP 경로를 건드렸다면 가능하면 아래까지 이어서 검증한다:
- `mcp_reload_addon()`으로 전체 애드온 재등록 후 관련 MCP 스모크 실행
- 관련 변경 기준: `mcp_build_rig`, `mcp_setup_retarget`, `mcp_inspect_bone_pairs`, `mcp_compare_frames`

## AI 에이전트 변환 하네스

실제 단일 `.blend` 리깅 변환 작업은 공통 MCP 진입점
`mcp_agent_convert_current_file(include_retarget=True)`를 우선 사용한다.
Codex와 Claude 모두 같은 status 계약을 따른다.

- `complete`: 요약과 `report_path` 보고
- `partial`: 완료된 범위와 다음 행동 보고
- `blocked`: 사용자가 수정 가능한 문제이므로 `problem/evidence/recommended_fix/retry_from` 보고 후 중단
- `failed`: 환경/코드/ARP 실패이므로 `error`와 `report_path` 보고 후 중단

하네스가 `blocked`를 반환한 상태에서 임의로 다음 단계로 진행하지 않는다.
`retry_from`은 v1에서 부분 재시작 파라미터가 아니라 진단 라벨이다.

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

### 작업 규모별 워크플로 (3-Tier)

**Tier 1 — 즉시 구현** (브레인스토밍 불필요):
- 오탈자, 1-3줄 명확한 버그 수정
- 문서 업데이트
- 기존 패턴을 그대로 따르는 추가 (함수, 테스트 등)
- 패턴이 확립된 다중 파일 버그 수정 (같은 수정을 여러 파일에 적용)

**Tier 2 — 인라인 계획** (대화 내 TODO 리스트, spec/plan 파일 불필요):
- 3-10개 파일 변경이지만 기존 아키텍처 범위 내
- 동작 변경이 기존 아키텍처 안에서 진행되는 작업
- 요구사항이 약간 애매하지만 탐색 범위가 좁은 경우
- **애매하면 여기서 시작** (Tier 3이 아님)

**Tier 3 — 풀 사이클** (`superpowers:brainstorming` → `writing-plans` → `subagent-driven-development`):
- 새 서브시스템/모듈 신규 생성
- 아키텍처 결정 (새 인터페이스, 라이브러리 선택, 파일 분할)
- 외부 API/계약에 영향을 주는 변경
- 횡단 관심사 (역할 체계 전면 변경 등)

### ProjectPlan.md 업데이트

- 작업 완료 시점에 해당 머지/PR 흐름 안에서 함께 갱신한다
- 별도 "docs 업데이트" 커밋으로 미루지 않는다 (상태가 표류함)
- 우선순위 목록은 머지 직후 재정렬을 검토한다

### Spec / Plan 파일 위치

- Spec: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Plan: `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`
- 브랜치 단위로 쌍(스펙-플랜-구현)이 맞물린다. 이름의 topic은 브랜치명과 정렬시킨다
- **Spec/Plan 파일은 Tier 3 작업에서만 생성한다. Tier 2는 대화 내 인라인 계획으로 충분하다.**

### 완료 기준

구현 작업은 다음을 모두 만족해야 "완료"로 본다:

- `pytest tests/ -v` 전부 통과
- `ruff check scripts/ tests/` 통과
- 관련 문서(ProjectPlan.md + 해당 feature 문서) 갱신됨
- 피처 브랜치가 master에 fast-forward 머지됨 (또는 명시적으로 "keep" 상태)

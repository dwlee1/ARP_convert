# arp_convert_addon.py 분할 + 레거시 정리 설계 (Sub-project ③)

> 작성일: 2026-04-05
> Sub-project: 3개 통합 개선의 3/3 (작업 프로세스 → MCP 피드백 루프 → **코드 건강**)
> 연관: `scripts/arp_convert_addon.py` (2969줄), 레거시 스크립트 5개
> **전제**: Sub-project ①(Workflow 규칙), Sub-project ②(MCP 피드백 루프)가 모두 **구현 완료**된 상태에서 진행. 체크포인트 검증에 Sub-project ②의 `mcp_inspect_bone_pairs`, `mcp_compare_frames`를 직접 사용한다.

## 문제 요약

`scripts/arp_convert_addon.py`가 2969줄로 커져 있다. 한 파일에 bl_info, 오퍼레이터 5개, Panel UI, PropertyGroup 2개, 그리고 약 750줄의 내부 헬퍼가 섞여 있다. 2026-04-05 F12 작업에서 해당 파일의 특정 로직(line 2494-2549의 bone_pairs 생성부)을 찾는 데 반복적으로 탐색 비용이 발생했다.

추가로 5개 레거시 파일이 `scripts/` 아래에 남아 있지만 어떤 활성 코드 경로에도 import 되지 않는다. 리타게팅 코드 삭제(2026-04-02) 이후 고아 상태다.

| 파일 | 줄수 | Import 참조 |
|------|------|------------|
| `scripts/01_create_arp_rig.py` | 332 | 없음 (pipeline_runner.py:4 docstring 언급만) |
| `scripts/rigify_to_arp.py` | 738 | 없음 |
| `scripts/bone_mapping.py` | 160 | 없음 (리타게팅 삭제와 함께 고아) |
| `scripts/diagnose_arp_operators.py` | 179 | 없음 (일회성 조사 도구) |
| `scripts/inspect_rig.py` | 92 | 없음 (일회성 도구) |

합계 1501줄의 죽은 코드.

## 목표

- `arp_convert_addon.py`를 12개 파일로 분할한다. 엔트리 파일은 bl_info, scripts/ 경로 설정, 모듈 리로드, register/unregister만 담당한다(약 220줄).
- 각 분할 모듈은 한 가지 책임(properties, UI, operators, build helpers, cc bones, weight transfer, foot guides, fixture I/O)만 가진다.
- 레거시 5개 파일을 완전 삭제한다(git history에 보존).
- CLAUDE.md, AGENTS.md, pipeline_runner.py, ProjectPlan.md의 파일 맵/참조를 새 구조에 맞게 갱신한다.
- **행동 변화는 0**이다. 순수 구조 리팩터링이므로 F12 back_leg shoulder 오차 0.00000m가 유지되어야 한다.

Non-goals:
- `ARPCONV_OT_BuildRig.execute` 내부 로직 쪼개기 / 함수 추출 (execute 본문은 그대로 유지, helper 참조 경로만 import 변경)
- `skeleton_analyzer.py` (2303줄) 또는 `arp_utils.py` 분할
- 새 기능 추가, 버그 수정, F8 검증 / 자동 추론 개선
- Blender 애드온을 .zip 패키지 형식으로 변환
- `mcp_bridge.py` 리팩터링 (Sub-project ②는 신규 함수 추가만 담당)
- Class 이름 변경, PropertyGroup 구조 변경 (기존 `.blend` 호환성 때문에 금지)
- Windows 호환성 개선, CI 구성

## 변경 사항

### 1. 새 모듈 구조 (12개 파일)

| 파일 | 예상 줄수 | 내용 |
|------|----------|------|
| `scripts/arp_convert_addon.py` | ~220 | **Entry only**: bl_info, `_ensure_scripts_path`, `_reload_modules`, `register`, `unregister` |
| `scripts/arp_props.py` | ~80 | `ARPCONV_HierarchyBoneItem`, `ARPCONV_Props` |
| `scripts/arp_ui.py` | ~200 | `ARPCONV_PT_MainPanel` |
| `scripts/arp_ops_preview.py` | ~120 | `ARPCONV_OT_CreatePreview` |
| `scripts/arp_ops_roles.py` | ~180 | `ARPCONV_OT_SelectBone`, `ARPCONV_OT_SetParent`, `ARPCONV_OT_SetRole` |
| `scripts/arp_ops_build.py` | ~650 | `ARPCONV_OT_BuildRig` (execute 본문은 유지, helper import 경로만 변경) |
| `scripts/arp_ops_bake_regression.py` | ~200 | `ARPCONV_OT_BakeAnimation`, `ARPCONV_OT_RunRegression` |
| `scripts/arp_build_helpers.py` | ~550 | Ref 메타데이터, 체인 조정, deform 매핑, 프라이머리 ref 해결 (현재 lines 179-500 블록) |
| `scripts/arp_cc_bones.py` | ~250 | cc bone 생성 + 컨스트레인트 복사 (현재 lines 500-923 일부) |
| `scripts/arp_weight_xfer.py` | ~150 | `_build_position_weight_map`, `_transfer_all_weights`, `_map_source_bone_to_target_bone` |
| `scripts/arp_foot_guides.py` | ~200 | foot guide 생성/감지/자동 배치 + `_set_preview_pose_bone_role` |
| `scripts/arp_fixture_io.py` | ~130 | Regression fixture 로딩/적용 + 경로 해석 |

합: **12개 파일**, 약 2930줄 (기존 2969줄에서 import 오버헤드로 몇 십 줄 감소).

### 2. 의존 방향 (순환 없음)

```
arp_convert_addon (entry, register)
  ↓ imports
arp_ui, arp_ops_preview, arp_ops_roles, arp_ops_build, arp_ops_bake_regression
  ↓ imports
arp_props, arp_build_helpers, arp_cc_bones, arp_weight_xfer,
arp_foot_guides, arp_fixture_io
  ↓ imports
skeleton_analyzer, arp_utils, weight_transfer_rules (기존 모듈, 수정 없음)
```

**규칙**:
- 엔트리(`arp_convert_addon.py`)만이 모든 새 모듈을 import한다
- 오퍼레이터 파일은 helper 모듈을 import한다 (반대 방향 금지)
- Helper 모듈끼리는 서로 import하지 않는다 (공통 기능은 `arp_utils`로)
- 모든 모듈은 `skeleton_analyzer`, `arp_utils`, `weight_transfer_rules`만 기존 의존으로 사용

### 3. 레거시 파일 삭제

5개 파일 완전 삭제:

- `scripts/01_create_arp_rig.py`
- `scripts/rigify_to_arp.py`
- `scripts/bone_mapping.py`
- `scripts/diagnose_arp_operators.py`
- `scripts/inspect_rig.py`

총 1501줄 제거. git history에 보존되므로 복구 가능.

**부수 업데이트**:
- `CLAUDE.md` 파일 맵 섹션에서 레거시 항목 제거, 신규 12개 모듈 항목 추가
- `AGENTS.md` 파일 맵 섹션에서 레거시 항목 제거, 신규 12개 모듈 항목 추가
- `scripts/pipeline_runner.py:4` docstring에서 "01_create_arp_rig" 언급 제거
- `docs/ProjectPlan.md:122` "레거시 파일... 확인한 뒤 수정한다" 문장 삭제

## 실행 전략: Phase별 MCP 체크포인트

단일 커밋으로 진행하지 **않는다**. Phase 단위로 13개 커밋을 만들고, 매 커밋 후 Sub-project ②의 MCP 함수로 행동 무결성을 검증한다.

### Phase 0: 준비 + 레거시 삭제 (커밋 1개)

1. 브랜치 생성: `feat/addon-split`
2. **Baseline 캡처**:
   - Sub-project ② 완료 후이므로 `mcp_inspect_bone_pairs()`와 `mcp_compare_frames()`가 사용 가능
   - `mcp_inspect_bone_pairs()` → JSON을 `docs/_scratch/baseline_bone_pairs.json`에 저장 (`.gitignore`에 `docs/_scratch/` 추가)
   - `mcp_compare_frames(주요_쌍들, 샘플_프레임들)` → 통계를 `docs/_scratch/baseline_compare.json`에 저장
3. 레거시 5개 파일 삭제 (`git rm`)
4. 부수 업데이트: `CLAUDE.md`, `AGENTS.md`, `pipeline_runner.py`, `ProjectPlan.md`
5. **커밋 1**: `chore: 레거시 스크립트 5개 삭제 + 문서 파일 맵 정리`

### Phase 1: Leaves 추출 (커밋 5개)

의존성 없는 helper를 먼저 추출. 각 추출은 (1) 새 파일 생성 (2) `arp_convert_addon.py`에서 해당 섹션 제거 + import 추가 (3) 체크포인트 검증 (4) 커밋.

- **커밋 2**: `refactor(addon): arp_weight_xfer.py 추출` — 가장 작고 경계가 명확함
- **커밋 3**: `refactor(addon): arp_foot_guides.py 추출`
- **커밋 4**: `refactor(addon): arp_fixture_io.py 추출`
- **커밋 5**: `refactor(addon): arp_cc_bones.py 추출`
- **커밋 6**: `refactor(addon): arp_build_helpers.py 추출` (가장 큰 helper)

### Phase 2: Props / UI 분리 (커밋 2개)

- **커밋 7**: `refactor(addon): arp_props.py 추출 + register 경로 확인`
- **커밋 8**: `refactor(addon): arp_ui.py 추출`

PropertyGroup이 오퍼레이터보다 먼저 register되어야 하므로 `arp_convert_addon.py`의 `register()` 함수를 함께 갱신한다.

### Phase 3: 오퍼레이터 분리 (커밋 4개)

- **커밋 9**: `refactor(addon): arp_ops_preview.py 추출`
- **커밋 10**: `refactor(addon): arp_ops_roles.py 추출`
- **커밋 11**: `refactor(addon): arp_ops_bake_regression.py 추출`
- **커밋 12**: `refactor(addon): arp_ops_build.py 추출 (가장 큰 오퍼레이터)`

각 오퍼레이터 추출 시 `register()`의 class 리스트와 `unregister()`의 역순 제거 리스트를 함께 갱신한다.

### Phase 4: 최종 정리 (커밋 1개)

- `arp_convert_addon.py`가 ~220줄 이하로 축소되었는지 확인
- 모든 새 모듈에 모듈 docstring 추가
- `CLAUDE.md` 파일 맵 섹션을 최종 12개 모듈 구조로 갱신
- `docs/ProjectPlan.md` 상태 갱신
- **커밋 13**: `docs(addon): 분할 완료 기록 + CLAUDE.md 파일 맵 갱신`

**총 예상 커밋**: 13개 (Phase 0 ×1 + Phase 1 ×5 + Phase 2 ×2 + Phase 3 ×4 + Phase 4 ×1)

### Phase별 체크포인트 루틴 (매 커밋 후)

```
1. pytest tests/ -v                    → 120 passed (Sub-project ② 완료 후 기준)
2. ruff check scripts/ tests/          → clean
3. Blender 모듈 리로드 (bpy.ops.script.reload 또는 addon 재등록)
4. MCP: mcp_build_rig() 정상 완료
5. MCP: mcp_inspect_bone_pairs() 결과를 baseline_bone_pairs.json과 비교
       → bit-for-bit 일치 (정렬 후)
6. MCP: mcp_compare_frames(주요 쌍, 샘플 프레임) 실행
       → 통계가 baseline_compare.json 대비 ±0.1mm 이내
```

**어떤 단계에서든 체크포인트 실패 시**: 해당 커밋 revert 후 재시도. 순수 구조 리팩터링이므로 **행동 변화가 있으면 버그**.

## 검증 절차 (최종 머지 전)

1. `pytest tests/ -v` → 120 passed (기대값, Sub-project ② 완료 후 기준)
2. `ruff check scripts/ tests/` → clean
3. MCP Build Rig → 정상 완료, bone_pairs가 Phase 0 baseline과 일치
4. MCP Bake → 정상 완료, back-leg shoulder 오차 0.00000m 유지 (F12 회귀 없음)
5. Blender GUI 수동 테스트: Edit → Preferences → Add-ons 에서 ARP Convert 재활성화, N 패널에 탭 정상 표시, 각 Step 버튼 클릭 가능
6. `wc -l scripts/arp_convert_addon.py` → < 250
7. 레거시 5개 파일 부재 확인
8. `CLAUDE.md`, `AGENTS.md` 파일 맵이 새 구조 반영
9. git history 확인: 13개 커밋이 논리적 순서 유지

## 위험 및 주의

- **Register/Unregister 순서 의존성**: Blender는 class 등록 순서가 중요할 수 있다. 특히 PropertyGroup은 이를 참조하는 Operator/Panel보다 먼저 등록되어야 한다. `register()`에서 명시적으로 순서를 유지한다.

- **모듈 리로드 시 register 꼬임**: 개발 중 모듈만 리로드하면 이미 등록된 class와 새 class가 충돌할 수 있다. `_reload_modules`가 unregister → reload → register 순서를 지키도록 유지한다. Blender 재시작이 가장 안전하지만 비용이 크므로 리로드 오퍼레이터는 살려둔다.

- **`bpy.types.Scene.arp_convert_props` 같은 scene property**: register 시점에 정의되고 scene에 저장된다. 모듈 이동 시 class 이름 또는 PropertyGroup 구조가 바뀌면 기존 `.blend` 파일의 호환성이 깨진다. 리팩터링은 **class 이름과 PropertyGroup 필드를 그대로 유지**해야 한다.

- **순환 import 함정**: `arp_build_helpers.py`가 `arp_cc_bones.py`를 import하고 그 반대도 있으면 순환. "helpers끼리는 서로 import하지 않는다" 규칙을 엄격히 유지. 공통 기능이 필요하면 `arp_utils`로.

- **Baseline 비교의 false positive**: `arp_obj["arpconv_bone_pairs"]`는 dict/list 순서 이슈가 있을 수 있다. baseline JSON 저장 시 `sort_keys=True`, 비교 시도 sorted 후 비교.

- **`_apply_ik_to_foot_ctrl` 등 skeleton_analyzer 내부 함수 의존**: 현재 `arp_convert_addon.py:2496`에서 `from skeleton_analyzer import _apply_ik_to_foot_ctrl`로 가져온다. 모듈 분할 후에도 같은 import 경로를 유지한다 — `arp_ops_build.py` 안에서 호출.

- **Weight Transfer의 복잡한 내부 state**: `_build_position_weight_map`이 arp_obj, source_obj, 기존 bone 매핑을 참조. 단순 함수 이동이 아니라 파라미터 정리 필요할 수 있다. Plan 단계에서 시그니처를 확정.

- **테스트 커버리지 한계**: pytest는 Blender 무관 로직만 커버한다. Helper 모듈의 bpy 의존 부분은 **MCP 체크포인트만이 유일한 안전망**이다. Sub-project ② 구현이 먼저 완료되어야 하는 이유.

- **체크포인트 비용**: 13개 커밋 각각에 MCP 라운드트립이 필요. 한 사이클이 수 초~수십 초. 총 체크포인트 시간 ~10분. 이는 의도된 비용 (정확성 > 속도).

- **`docs/_scratch/`**: baseline 파일 저장용 임시 디렉토리. `.gitignore`에 추가하여 커밋되지 않도록 함.

## 기대 효과

- **파일 찾기 시간 단축**: 버그가 weight 관련인지 cc bone 관련인지 foot guide 관련인지 파일명만 보고 즉시 판단 가능.
- **Claude / AI 협업 개선**: 작은 파일은 한 번에 맥락 로딩 가능 → 수정 정확도 증가 (이번 F12 작업에서 2969줄 파일 탐색 비용이 반복적으로 발생했음).
- **향후 F8 검증 / 자동 추론 개선**이 훨씬 수월해짐 — 관련 모듈만 열어서 작업.
- **리팩터링 경로 증명**: 이 방식이 성공하면 다음에 `skeleton_analyzer.py` (2303줄) 분할도 같은 방식 적용 가능.
- **레거시 1501줄 제거**: 프로젝트 총 코드 라인이 순감. 탐색, grep, 인덱싱이 모두 빨라짐.

## Sub-project 연결 및 구현 순서

**구현 순서**: ① → ② → ③ (이 순서를 지켜야 한다)

- **①(Workflow)**: 가장 먼저 구현. 이후 ②③의 브랜치/커밋 규칙이 이를 따른다.
- **②(MCP)**: ③ 전에 반드시 구현 완료. ③의 Phase별 체크포인트가 ②의 `mcp_inspect_bone_pairs`, `mcp_compare_frames`를 직접 호출한다.
- **③(Addon 분할)**: 가장 큰 작업. ①②의 규칙과 도구 위에서 수행.

②가 없이 ③을 먼저 하면 체크포인트 자동화가 불가능하다 (매 커밋마다 raw execute_blender_code 수동 작성). ②의 산출물이 ③의 안전망.

## 스펙 범위 밖

- `ARPCONV_OT_BuildRig.execute` 본문 로직 리팩터링 (단계 분할, 함수 추출). 이 스펙은 "파일 이동"에 집중.
- `skeleton_analyzer.py`, `arp_utils.py` 분할 — 별도 후속 스펙
- 새 기능/버그 수정
- Blender 애드온 .zip 패키지화
- `mcp_bridge.py` 리팩터링 (Sub-project ②는 신규 함수 추가만)
- CI 구성, GitHub Actions
- Windows 호환성 개선
- Class 이름 변경 또는 PropertyGroup 필드 변경

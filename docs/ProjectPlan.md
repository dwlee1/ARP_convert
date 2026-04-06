# BlenderRigConvert 통합 문서

> 최종 수정: 2026-04-02 (리타게팅 코드 전면 삭제, Build Rig까지만 유지)

## 문서 목적

이 문서는 아래 4가지를 한 번에 확인하기 위한 작업 기준 문서다.

- 이 프로젝트가 무엇을 자동화하는지
- 현재 HEAD 코드가 실제로 어떤 경로를 사용하는지
- 승인된 목표 상태가 무엇인지
- 목표 상태까지 남은 격차와 검증 항목이 무엇인지

## 한눈에 보기

### 프로젝트 목표

동물 캐릭터 리그를 Auto-Rig Pro(`dog` preset) 기반으로 통일하고, 리그 생성을 자동화한다.
리타게팅은 2026-04-02 전면 삭제 후 재설계 예정.

### 기준 날짜

- 현재 구현 기준: 2026-04-02 HEAD
- 리타게팅 삭제 결정: 2026-04-02

### 현재 구현 흐름 (2026-04-02 HEAD)

```text
Addon 경로
1. 소스 deform 본 분석 (웨이트 0 본 필터링 + 제외 본 부모 관계 포함)
2. Preview Armature 생성 + Source Hierarchy 트리 데이터 생성
3. 역할 수정 (Source Hierarchy 트리에서 본 클릭 → 선택 → 역할 변경)
4. ARP 리그 생성 (append_arp → set_spine/neck/tail/ears → ref 정렬 → match_to_rig)
5. 앞다리 3 Bones IK 값 설정 + IK pole vector 위치 매칭
6. cc_ 커스텀 본 추가 (shape key 드라이버 컨트롤러 포함)
7. 전체 웨이트 전송 (deform + cc_ → ARP)
8. Shape key 드라이버 리맵
9. 애니메이션 베이크 (F12, 별도 버튼 — rest-delta offset bake)
```

```text
비대화형 경로
pipeline_runner.py: 소스 분석 → ARP 리그 생성 → ref 정렬 → match_to_rig
03_batch_convert.py: pipeline_runner.py 호출 래퍼
```

### 삭제된 기능 (2026-04-02)

아래 기능은 품질 문제로 전면 삭제되었다. 재설계 시 새로 구현한다.

- **F10: FBX clean armature 기반 리타게팅** — clean FBX source 생성, .bmap, ARP native retarget
- **F11: Clean armature 하이어라키 정규화** — normalize_clean_hierarchy, 리베이크
- **F9: Remap UI 통합** — bones_map_v2 UIList, RemapSetup, Retarget 오퍼레이터
- **addon Step 3.5 (Remap Setup)** 오퍼레이터 및 UI
- `arp_utils.py`의 clean source 관련 함수 전체 (export/import_clean_fbx, create/cleanup_clean_source 등)
- `skeleton_analyzer.py`의 generate_bmap_content, populate_bone_map

### 현재 상태 요약

- [x] Preview 기반 Build Rig 흐름이 현재 메인 구현 경로다
- [x] ARP 프리셋은 `dog`로 고정한다
- [x] 다리 `leg` 3본 매핑과 `foot` 분할 규칙은 반영되었다
- [x] Preview 가이드, `virtual neck`, `virtual toe`, `cc_` 커스텀 본 생성이 구현되었다
- [x] spine / neck / tail / ear 체인 개수 동적 매칭 구현
- [x] 자동 추론 개선: spine 추적 + neck 다중 본 + 다리/발 자동 분리 + 구조적 귀 감지
- [x] bank / heel ref 본 자동 배치: foot.head 기준 Z=0, foot+toe 합산 길이 비례
- [x] face/skull 비활성화: append_arp 후 set_facial(enable=False) 호출
- [x] pytest 기반 fixture 테스트 95개 통과
- [x] F1: 웨이트 0 본 프리뷰 제외 (완료)
- [x] F1+: Step 2에 Source Hierarchy 트리 UI 추가
- [x] F2: IK pole vector 위치 매칭 (완료)
- [x] F3: Shape key 드라이버 보존 (완료)
- [ ] F12: rest-delta offset 기반 애니메이션 베이크 검증 (`docs/F12_ExactMatch.md`)
- [ ] F8: 웨이트 전송 실제 검증

### 자동화 전략

- 핵심 자동화 목표는 새 동물 리그에서 `skeleton_analyzer.py`가 역할을 최대한 자동 추론하는 것
- 이상적인 흐름은 `자동 추론 → 예외 몇 개만 수정 → Build Rig`이다
- 실행 경로가 여러 갈래이므로 addon / pipeline / batch가 같은 목표 상태로 수렴해야 한다

## 핵심 규칙

- ARP 프리셋은 `dog` 고정 (face/skull 비활성화 상태)
- ARP ref 본 추가/삭제에 `edit_bones.new()` 사용 금지 → ARP 네이티브 `set_*` 함수 사용
- ARP ref 본은 실제 리그에서 동적 탐색
- `leg` 역할 본이 3개면 ARP도 3본 다리 체인 (`thigh_b_ref` 포함)
- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할
- toe 본이 없으면 `virtual toe` 사용
- ear는 `ear_01_ref / ear_02_ref`에 직접 매핑
- face와 unmapped 본은 `cc_` 커스텀 본 (face 역할은 unmapped에 통합)
- Preview Armature는 원본 이름 유지, 역할은 색상과 커스텀 프로퍼티로 표시

## Preview 역할

| 역할 | 의미 |
|------|------|
| `root` | 루트 |
| `spine` | 스파인 체인 |
| `neck` | 목 |
| `head` | 머리 |
| `back_leg_l/r` | 뒷다리 상부 3본 |
| `back_foot_l/r` | 뒷발 |
| `front_leg_l/r` | 앞다리 상부 3본 |
| `front_foot_l/r` | 앞발 |
| `ear_l/r` | 귀 체인 |
| `tail` | 꼬리 체인 |
| `unmapped` | 미매핑 (cc_ 커스텀 본 후보) |

## 구현 기준 파일

| 파일 | 역할 |
|------|------|
| `scripts/skeleton_analyzer.py` | 구조 분석, Preview 생성, ref 체인 탐색 |
| `scripts/arp_convert_addon.py` | Preview UI, BuildRig 오퍼레이터, 회귀 테스트 패널 |
| `scripts/arp_utils.py` | Blender / ARP 공통 유틸 |
| `scripts/weight_transfer_rules.py` | 웨이트 전송 (Blender 없이 테스트 가능) |
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 (Build Rig까지) |
| `scripts/03_batch_convert.py` | 배치 실행 경로 |

## 참고 문서

| 문서 | 역할 |
|------|------|
| `docs/FoxTestChecklist.md` | 여우 파일 Build Rig 검증 계획 + Preview bake 실험 기록 |
| `docs/RegressionRunner.md` | 대표 샘플 GUI 회귀 테스트 운영 |
| `docs/F12_ExactMatch.md` | rest-delta offset 기반 애니메이션 베이크 설계 (F12) |

## 후속 기능

### F12. 애니메이션 베이크 (rest-delta offset 방식)

2026-04-02 재설계 완료, 2026-04-03 grill-me 세션으로 보강. 상세 설계: `docs/F12_ExactMatch.md`.

**현재 방식**: `delta = source_rest^-1 * source_pose`, `target_pose = controller_rest * delta`

- Build Rig 시 `arp_obj["arpconv_bone_pairs"]`에 매핑 저장 (역할 본 + cc_ 커스텀 본, `is_custom` 플래그 포함)
- ARP 컨트롤러 본에 직접 keyframe insert (rotation mode 유지, Euler 연속성 보정)
- 액션 순회: 임시 NLA strip + 기존 NLA mute (Action Slot 호환, 직접 할당 금지)
- 오브젝트 transform preflight: hard check, 실패 시 중단
- 역할 본은 Loc/Rot만 유지 (Scale FCurve 삭제), cc_ 본은 Scale 포함
- MCP 비교는 위치 + 회전 오차를 함께 집계
- addon UI "Step 4: Bake Animation" 버튼, pipeline_runner는 `--bake` 플래그 제어

**구현 상태**:
- 초기 COPY_TRANSFORMS 기반 베이크는 front_foot 매핑, back_foot toe 누락, root 180도 뒤집힘, IK→FK 전환, NLA auto-push, PoseBone 순회 문제를 해결했음
- FK→IK 전환 완료 (2026-04-05):
  - `_ensure_ik_mode()` 구현 (ik_fk_switch = 0.0)
  - bone_pairs IK 매핑 로직 구현 (다리 중간 본 제거, foot→IK foot)
  - back_leg shoulder 매핑 블로커 해결: `_CTRL_SEARCH_PATTERNS["back_leg_l/r"]`와 `ARP_REF_MAP`이 불일치했던 근본 원인 수정. `c_foot_fk`가 `back_leg`에 잘못 들어가 있고 원래 있어야 할 `back_foot`에서 빠져 있던 이중 버그였음. 회귀 테스트 4개 추가(TestRoleMapConsistency).
  - 여우 리그 MCP 검증 결과 (walk 액션): leg 최대 오차 0.186m → **0.00000m** (뒷다리), 전체 최대 오차 3.64mm (앞다리 dupli 잔여). **F12 블로커 완전 해결.**
  - 관련 커밋: 2a07d78 (test), 8dce2a0 (fix patterns), 5d6b301 (fix toe name)
  - 참고: 앞다리 dupli 3-4mm 잔여 오차는 별개 이슈 (rest pose 정렬)로 추정, 이 스펙 범위 밖.
- 후속 수정 (2026-04-06):
  - `c_foot_ik` 계열의 rest 축 차이 때문에 source 회전을 그대로 복사하면 Y축 180° 뒤집힘이 발생하는 문제 확인
  - 베이크 엔진을 COPY_TRANSFORMS에서 **rest-delta offset bake**로 전환해 source/controller 축 차이를 bake 시점에 반영
  - `mcp_compare_frames()`에 회전 오차(deg) 집계 추가

### MCP 피드백 루프 확장 완료 (2026-04-05)

`scripts/mcp_bridge.py`에 3개 함수 추가 + 순수 헬퍼 모듈 + 사용 레시피.

- 신규 브릿지 함수: `mcp_inspect_bone_pairs`, `mcp_compare_frames`, `mcp_inspect_preset_bones`
- 순수 로직 모듈: `scripts/mcp_verify.py` (pytest 17개 커버)
- 레시피 문서: `docs/MCP_Recipes.md` — 11개 함수 인덱스 + 3개 조합 레시피 + F12 사례 요약
- 총 테스트 수: 103 → 120 (신규 +17)
- MCP 스모크 검증: 여우 walk 액션 기준 back_leg 오차 2.9e-07 m 재현 (F12 해결 상태 유지)

이 함수들은 Sub-project ③(addon.py 분할) 실행 중 체크포인트 도구로 사용된다.

### arp_convert_addon.py 분할 완료 (2026-04-05)

2969줄 단일 파일을 12개 모듈로 분할 + 레거시 스크립트 5개 삭제.

- 엔트리: `arp_convert_addon.py` (~148줄, bl_info + register/unregister만)
- PropertyGroup: `arp_props.py`
- UI: `arp_ui.py`
- 오퍼레이터 5개: `arp_ops_preview.py`, `arp_ops_roles.py`, `arp_ops_build.py`, `arp_ops_bake_regression.py`
- 헬퍼 5개: `arp_build_helpers.py`, `arp_cc_bones.py`, `arp_weight_xfer.py`, `arp_foot_guides.py`, `arp_fixture_io.py`
- 삭제된 레거시: `01_create_arp_rig.py`, `rigify_to_arp.py`, `bone_mapping.py`, `diagnose_arp_operators.py`, `inspect_rig.py` (1501줄)
- MCP 체크포인트: Phase별 11개 커밋 후 매번 bone_pairs + 프레임별 위치 비교 검증. F12 back_leg 오차 2.897e-07m 유지.

3개 통합 개선(Workflow / MCP / 코드 건강) 전체 완료.

이전 경로 실패 이유 (참고용):
- Preview bake 경로: 2026-03-30 실험에서 품질 불충분으로 폐기
- FBX clean armature 경로: Blender 4.5 Action Slot 문제 등 복잡성이 높아 삭제

### F8. 전체 웨이트 전송

구현은 완료됐다. 위치 기반 매칭 + 사이드 필터 + 본 길이 비율 분할을 실제 여우 리그 weight paint 모드에서 검증해야 한다.

### F6. bank / heel 자동 배치 보정

기본 위치 가이드는 foot 방향/길이 비율로 자동 보정하고, 사용자가 이동한 가이드는 유지한다.

## 우선순위

1. **F12 애니메이션 베이크 검증** — rest-delta offset bake 기준으로 재검증, `docs/F12_ExactMatch.md` 참조
2. **F8 실제 weight 검증** — 여우 리그 weight paint 검증
3. **자동 역할 추론 정확도 개선** — 새 동물 리그 대응

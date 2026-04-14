# BlenderRigConvert 통합 문서

> 최종 수정: 2026-04-13 (F12 root-slot 수정/검증 반영)

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
4. DEF 본 분리 (소스 아마추어에 역할 기반 DEF 계층 생성)
5. ARP 리그 생성 (append_arp → set_spine/neck/tail/ears → ref 정렬 → match_to_rig)
6. 앞다리 3 Bones IK 값 설정 + IK pole vector 위치 매칭
7. cc_ 커스텀 본 추가 (shape key 드라이버 컨트롤러 포함)
8. 전체 웨이트 전송 (deform + cc_ → ARP)
9. Shape key 드라이버 리맵
10. 애니메이션 베이크 (F12, 별도 버튼 — rest-delta offset bake)
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

### 보류된 작업

아래 작업은 구조적 risk가 확인되어 아키텍처 재검토 후 진행한다.

- **IK pole vector 위치 문제 — 보류 (2026-04-10)**
  - 증상: 사족보행 앞다리에서 `c_leg_pole_dupli_001.l/r`가 몸통 쪽으로 배치되는
    경우 발생 (너구리 리그 관찰)
  - 시도한 접근:
    1. `thigh_ref` roll 보정 + `leg_auto_ik_roll=0` (Step 3.5) → 앞다리에서 실패.
       코드는 master에 merge되지 않았고 reflog `5f9ac5e` 커밋에서만 참조 가능.
       이후 Capybara 재현 테스트(0ff67cf)에서 이 코드가 ARP `_align_leg_limbs`
       knee 재정렬을 유발한 원인으로 확정됨
    2. Preview `_pole` 가이드 본 + Build Rig Step 4c 직접 적용 → 설계 완료,
       저장소 선택 risk로 미구현
  - 검토한 저장소 옵션 4가지 (모두 trade-off 있음):
    Preview guide / ARP 커스텀 프로퍼티 / 하이브리드 / Source armature 저장
  - 상세 기록: `docs/superpowers/plans/2026-04-10-pole-vector-deferred.md`
  - 재검토 트리거: 사용자 재리포트 / 사례 누적 2건 / ARP API 개선 /
    리타게팅 재설계 시

### 현재 상태 요약

- [x] Preview 기반 Build Rig 흐름이 현재 메인 구현 경로다
- [x] ARP 프리셋은 `dog`로 고정한다
- [x] 다리 `leg` 3본 매핑과 `foot` 분할 규칙은 반영되었다
- [x] Preview 가이드, `virtual neck`, `virtual toe`, `cc_` 커스텀 본 생성이 구현되었다
- [x] spine / neck / tail / ear 체인 개수 동적 매칭 구현
- [x] 자동 추론 개선: spine 추적 + neck 다중 본 + 다리/발 자동 분리 + 구조적 귀 감지
- [x] 자동 추론 개선: all-downward 앞발 5본 체인에서 `hand + finger`를 2본 foot 역할로 분리 (deer)
- [x] non-deform 투과(collapse) 계층 재구성 — flat 계층 리그 대응
- [x] trajectory 역할 추가 — root 부모 본 자동 감지 → c_traj 매핑
- [x] bank / heel ref 본 자동 배치: foot.head 기준 Z=0, foot+toe 합산 길이 비례
- [x] face/skull 비활성화: append_arp 후 set_facial(enable=False) 호출
- [x] pytest 기반 fixture 테스트 95개 통과
- [x] F1: 웨이트 0 본 프리뷰 제외 (완료)
- [x] F1+: Step 2에 Source Hierarchy 트리 UI 추가
- [x] F2: IK pole vector 위치 매칭 (완료)
- [x] F3: Shape key 드라이버 보존 (완료)
- [x] DEF 본 분리: Build Rig 내부에서 역할 기반 DEF 계층 자동 생성 (`docs/DEF_BoneSeparator.md`)
- [x] F12: ARP 네이티브 리타겟 위임 (`docs/F12_ARP_NativeRetarget.md`)
  - [x] Setup Retarget + Cleanup + Copy Custom Scale 오퍼레이터 구현
  - [x] ik=True 월드 스페이스 매칭 — spine/neck/head/ear/shoulder/custom 전부 0.000mm, 0.0°
  - [x] tail_master COPY_ROTATION constraint mute — tail 오차 해결
  - [x] 커스텀 본 DEF 소스 통일 — bone_pairs 소스가 전부 DEF 본
  - [x] 커스텀 본 스케일 fcurve 복사 — ARP 리타겟이 무시하는 스케일 보존
  - [x] root 매핑 보정 — `c_root_master.x` → `c_root.x`, `set_as_root=True`
- [x] Build Rig post-process controller auto-size 적용 — spine 체인 전체 길이 기반 균일 절대 크기 방식 (v2): `target = spine_total × BODY_FRACTION(0.10)`, `scale = target / ctrl_bone_length`. head/neck/spine/ear 컨트롤러가 동일한 절대 표시 크기(~15cm)로 통일됨. ARP IK/FK driver가 있는 본(foot/leg)은 자동 제외.
- [x] trajectory 역할 추가 — root 부모 본 자동 감지 → c_traj 매핑, trajectory가 있으면 ARP 단일 root 슬롯을 이 행에 할당
- [x] F8: 웨이트 전송 실제 검증 — 여우/너구리 리그 weight paint 검증 문제없음

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
| `trajectory` | 궤적 본 (root 부모 → c_traj) |
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
| `docs/F12_ARP_NativeRetarget.md` | 현행 F12 설계: ARP 네이티브 리타겟 위임 방식 |
| `docs/F12_ExactMatch.md` | 폐기된 rest-delta offset bake 기록 (참고용) |

## 후속 기능

### F12. 애니메이션 베이크 (ARP 네이티브 리타겟 위임 방식)

2026-04-06 설계 확정. 현행 기준 문서는 `docs/F12_ARP_NativeRetarget.md`이며,
`docs/F12_ExactMatch.md`의 rest-delta offset bake 방식은 폐기되었다.

**현재 방식**: Build Rig까지만 우리 애드온이 담당하고, 애니메이션 베이크는 ARP 리타겟 UI에 위임한다.

- Build Rig 시 `arp_obj["arpconv_bone_pairs"]`에 매핑 저장 (역할 본 + cc_ 커스텀 본, `is_custom` 플래그 포함)
- `Setup Retarget`이 bone_pairs를 `bones_map_v2`로 변환하고 리타겟 씬 설정을 자동 구성
- 베이크 자체는 사용자가 ARP Remap 패널에서 확인 후 `Re-Retarget`으로 실행
- `Cleanup`은 소스/프리뷰 삭제 + `_remap` 액션 rename 담당
- `Copy Custom Scale`은 ARP 리타겟이 무시하는 커스텀 본 스케일 fcurve를 후처리로 복사
- pipeline_runner는 `--retarget` 플래그로 setup → ARP retarget → scale copy → cleanup 경로를 실행

**구현 상태**:
- [x] Setup Retarget + Cleanup + Copy Custom Scale 오퍼레이터 구현
- [x] root 매핑 보정: `c_root_master.x` 대신 `c_root.x`, `set_as_root=True`
- [x] root 외 매핑 본 `ik=True` 월드 스페이스 매칭 적용
- [x] tail master COPY_ROTATION constraint mute 적용
- [x] 커스텀 본 DEF 소스 통일 및 scale fcurve 후처리 구현
- [x] 여우 리그 수동 검증에서 FK/IK/root/pole/batch_retarget 정상 확인
- [x] ARP 단일 root 슬롯 대응 — trajectory가 있으면 `c_traj` 행만 `set_as_root=True`
- [x] 여우 Round 6 기준 전체 흐름 재검증 및 체크리스트 반영

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

구현과 실제 검증이 완료됐다. 위치 기반 매칭 + 사이드 필터 + 본 길이 비율 분할 + stretch/twist 정점별 proximity 분배까지 구현했고, 여우/너구리 리그 weight paint 검증에서 문제없음을 확인했다.

- stretch/twist 본은 proximity 기반으로 정점별 웨이트를 분배 (2026-04-09)
- 비-다리 역할 본(ear/spine/neck 등) deform_to_ref 직접 매핑 수정 완료

### F6. bank / heel 자동 배치 보정

기본 위치 가이드는 foot 방향/길이 비율로 자동 보정하고, 사용자가 이동한 가이드는 유지한다.

## 우선순위

1. **자동 역할 추론 정확도 개선** — 새 동물 리그 대응

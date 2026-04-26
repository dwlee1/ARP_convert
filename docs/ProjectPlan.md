# BlenderRigConvert 통합 문서

> 최종 수정: 2026-04-22 (blend-first Phase 3 진입 / 문서 정리 반영)
>
> 개발 워크플로(3-Tier, 브랜치 전략, 커밋 컨벤션, 완료 기준)는 `CLAUDE.md` 의 `## Workflow` 섹션이 단일 소스다.

## 문서 목적

이 문서는 아래 4가지를 한 번에 확인하기 위한 작업 기준 문서다.

- 이 프로젝트가 무엇을 자동화하는지
- 현재 HEAD 코드가 실제로 어떤 경로를 사용하는지
- 승인된 목표 상태가 무엇인지
- 목표 상태까지 남은 격차와 검증 항목이 무엇인지

## 한눈에 보기

### 프로젝트 목표

동물 캐릭터 리그를 Auto-Rig Pro(`dog` preset) 기반으로 통일하고, 리그 생성을 자동화한다.
리타게팅은 2026-04-02 전면 삭제 후 2026-04-06 ARP 네이티브 위임 방식으로 재설계 완료.
현행 설계: `docs/F12_ARP_NativeRetarget.md`.

### 기준 날짜

- 현재 구현 기준: 2026-04-22 HEAD
- 리타게팅 삭제 결정: 2026-04-02
- 리타게팅 재설계 완료: 2026-04-06

### 현재 구현 흐름 (2026-04-22 HEAD)

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
10. 리타게팅 (Setup Retarget → ARP `bpy.ops.arp.retarget` → Copy Custom Scale → Cleanup)
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
| `docs/archive/` | 폐기된 설계/계획 문서 보존 (예: `F12_ExactMatch.md`) |

## 후속 기능

> 완료된 후속 기능(F12 / MCP 피드백 / addon 분할 / F8 / F6 / UX overhaul)은 `docs/archive/completed-features.md` 참조.

## Unity 프로젝트 이주

사족보행 21마리 리그를 ARP로 통일하는 별도 트랙.

### 현재 상태 (2026-04-17 이후: FBX 경로 보류)

사용자가 Rabbit `.blend` GUI 확인 결과 A+B-1 전처리 후에도 품질이 여전히
미달이라고 판정. **FBX 입력 경로는 중단하고 원본 .blend 경로(후보 C)로 전환.**

- `bone_pairs` 메타데이터 수치(role 21 / custom 6)는 복구됐으나 실제 rest pose /
  애니메이션 품질은 실사용 수준이 아님 → 구조적 gap이 A+B-1로 완전 해결되지
  않음을 의미
- `tools/fbx_preprocess.py` + `tools/fbx_to_blend.py`의 `_apply_preprocess`는
  **코드로 보존** (master에 merge됨, 삭제 금지) — 원본 .blend를 구할 수 없는
  동물이 나오면 재활용

### 재개 조건 (FBX 경로)

아래 중 하나가 발생하면 FBX 경로 재검토:
- 아트 팀에서 일부 동물의 원본 .blend를 확보 불가로 확인됨
- 다른 동물(lopear 등)을 blend-first로 처리한 뒤 공통 패턴이 축적되어
  FBX 전처리 B-2~B-4를 구체화할 수 있는 근거가 생김

재개 시 참고 문서:
- `docs/superpowers/pilot/rabbit_diagnosis.md` — 구조적 gap 4가지 + A/B-1/B-2~B-4 후보
- `docs/superpowers/pilot/rabbit_report.md` — Phase 1 파일럿 종료 상태
- `tools/fbx_preprocess.py` — 현재 구현된 A-1/A-2/A-3/B-1
- `tests/test_fbx_preprocess.py` — 26 pytest 커버

### 완료된 작업 (보존)

- [x] 설계 (2026-04-16 `docs/superpowers/specs/2026-04-16-unity-migration-design.md`)
- [x] Phase 0 인벤토리 — `docs/MigrationInventory.csv`, in_scope=22
- [x] pre-pilot 도구 — `tools/build_migration_inventory.py`, `tools/fbx_to_blend.py`
- [x] Phase 1 Rabbit 파일럿 (FBX 경로) — **중단**
- [x] Phase 2 후보 A + B-1 구현 (FBX 전처리) — **코드 보존, 사용 보류**

### 다음 트랙: blend-first (후보 C)

- [x] 아트 팀에 21마리 원본 `.blend` 확보 가능 여부 확인 — `Asset/Blender/animal_blend_inventory.csv` (137행 수동 큐레이션)로 이미 확보됨
- [x] Unity in_scope 22마리 ↔ 원본 `.blend` 1차 매핑 — `docs/MigrationInventory.csv` `source_blend_hint` 컬럼 22/22 채움 (normalized 20 + path fallback 2, unresolved 0). 매칭 스크립트: `scripts/_oneoff_match_blend_inventory.py`
- [ ] 첫 blend-first 동물 선정 (Rabbit부터 재시도 or 다른 동물)
- [ ] 기존 여우/너구리 workflow(.blend → Build Rig) 그대로 적용 가능 여부 측정
- [ ] Phase 3 배치 20마리 (blend-first 기준)
- [ ] Phase 4 마무리

## 우선순위

1. **Agent Convert Harness** — Blender에 열린 단일 사족보행 `.blend`를 AI 에이전트가
   MCP 단일 진입점으로 Build Rig + Retarget까지 진행하고, 문제 발생 시 사용자가
   수정 가능한 진단을 반환하도록 한다.
2. **자동 역할 추론 정확도 개선** — 새 동물 리그에서 수동 수정 횟수 최소화
3. **Unity 이주 Phase 3 (blend-first)** — 현재 보류. 하네스 안정화 후 기존
   `.blend → Build Rig` 흐름을 in_scope 22마리에 순차 적용한다.
4. **기타 UX/툴 개선** — 회귀 테스트, MCP 레시피, 파일 정리 등 부수 작업

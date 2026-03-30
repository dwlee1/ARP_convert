# BlenderRigConvert 통합 문서

> 최종 수정: 2026-03-30 (FBX 클린 아마추어 방식 전환)

## 문서 목적

이 문서는 아래 4가지를 한 번에 확인하기 위한 작업 기준 문서다.

- 이 프로젝트가 무엇을 자동화하는지
- 현재 어떤 구현이 완료되었는지
- 무엇이 아직 미완료인지
- 다음 작업에서 무엇을 검증해야 하는지

## 한눈에 보기

### 프로젝트 목표

동물 캐릭터 리그를 Auto-Rig Pro(`dog` preset) 기반으로 통일하고, 리그 생성과 애니메이션 리타게팅을 자동화한다.

### 현재 기준 실행 흐름

```text
1. 소스 deform 본 분석 (웨이트 0 본 필터링 포함)
2. Preview Armature 생성
3. 역할 수정
4. ARP 리그 생성 (append_arp → set_spine/neck/tail/ears → ref 정렬 → match_to_rig)
5. 앞다리 3 Bones IK 값 설정 + IK pole vector 위치 매칭
6. cc_ 커스텀 본 추가 (shape key 드라이버 컨트롤러 포함)
7. 전체 웨이트 전송 (deform + cc_ → ARP)
8. Shape key 드라이버 리맵
9. FBX 익스포트 → 임포트 (클린 아마추어 생성)
10. Remap 설정 (.bmap 생성 → ARP build_bones_list → import_config)
11. ARP 네이티브 retarget
```

### 현재 상태 요약

- [x] Preview 기반 변환 흐름이 현재 메인 경로다
- [x] ARP 프리셋은 `dog`로 고정한다
- [x] 다리 `leg` 3본 매핑과 `foot` 분할 규칙은 반영되었다
- [x] Preview 가이드, `virtual neck`, `virtual toe`, `cc_` 커스텀 본 생성이 구현되었다
- [x] spine / neck / tail / ear 체인 개수 동적 매칭 구현
- [x] `.bmap` 규칙 `map_role_chain` 일관 사용, 동적 컨트롤러 이름 생성
- [x] 자동 추론 개선: spine 추적 + neck 다중 본 + 다리/발 자동 분리 + 구조적 귀 감지
- [x] bank / heel ref 본 자동 배치: foot.head 기준 Z=0, foot+toe 합산 길이 비례
- [x] face/skull 비활성화: append_arp 후 set_facial(enable=False) 호출
- [x] pytest 기반 fixture 테스트 (84개 테스트 통과)
- [x] 전체 웨이트 전송: role-aware 매핑
- [x] F1: 웨이트 0 본 프리뷰 제외 (완료)
- [x] F2: IK pole vector 위치 매칭 (완료)
- [x] F3: Shape key 드라이버 보존 (완료)
- [ ] **F10: FBX 클린 아마추어 기반 리타게팅** — 구현 중
- [ ] F4: 리타게팅 IK 모드 — 코드 완료, FBX 방식 전환 후 재검증 필요
- [ ] F9: Remap UI 통합 — 설계 완료, 구현 대기 (FeaturePlan_v5.md)

### 자동화 전략

- 핵심 자동화 목표는 새 동물 리그에서 `skeleton_analyzer.py`가 역할을 최대한 자동 추론하는 것
- 이상적인 흐름: `자동 추론 → 예외 몇 개만 수정 → BuildRig/Retarget`

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
| `scripts/skeleton_analyzer.py` | 구조 분석, Preview 생성, ref 체인 탐색, `.bmap` 생성 |
| `scripts/arp_convert_addon.py` | Preview UI, BuildRig, Remap, Retarget |
| `scripts/arp_utils.py` | Blender / ARP 공통 유틸 |
| `scripts/weight_transfer_rules.py` | 웨이트 전송 (Blender 없이 테스트 가능) |
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 |
| `scripts/03_batch_convert.py` | 배치 실행 경로 |

레거시 파일 (`01_create_arp_rig.py`, `02_retarget_animation.py`, `rigify_to_arp.py`)은 현재 메인 경로와 실제 사용 여부를 확인한 뒤 수정한다.

## 참고 문서

| 문서 | 역할 |
|------|------|
| `docs/FeaturePlan_v5.md` | F9 Remap UI 통합 설계 |
| `docs/FoxTestChecklist.md` | 여우 파일 테스트 기록 (Round 1~4) |
| `docs/RegressionRunner.md` | 대표 샘플 GUI 회귀 테스트 운영 |

## F10: FBX 클린 아마추어 기반 리타게팅 (현재 작업)

### 배경

Round 3-4에서 Preview 베이크 방식의 한계를 확인:
- 소스 → Preview 베이크 시 rest pose 미세 차이로 꼬임, 위치 어긋남, 노이즈 발생
- 행렬 보정으로도 근본 해결 불가

사용자 검증: 원본을 FBX(Deform Only + Anim)로 익스포트 → 재임포트하면 컨스트레인트/컨트롤러가 제거된 클린 아마추어가 생기고, ARP 네이티브 retarget이 정상 동작함.

### 핵심 변경

- **베이크 단계 완전히 제거** (`_bake_source_to_preview()` 삭제)
- **FBX 익스포트/임포트**로 클린 아마추어 자동 생성
- **ARP 네이티브 retarget**만 호출 (커스텀 베이크 없음)
- Preview는 역할 추론/UI용으로 유지

### 새 파이프라인 (Step 3.5 + Step 4)

```text
Step 3.5: Remap 설정
  a) 원본 → FBX 익스포트 (Deform Only + Anim, Armature만)
  b) FBX → 임포트 → fbx_obj (클린 아마추어 + 모든 액션)
  c) .bmap 생성 (기존 generate_bmap_content 사용)
  d) ensure_retarget_context(fbx_obj, arp_obj)
  e) build_bones_list → import_config → redefine_rest_pose → save_pose_rest

Step 4: Retarget
  a) ensure_retarget_context(fbx_obj, arp_obj)
  b) ARP 네이티브 retarget 호출
  c) FBX 임시 파일 + 임포트 오브젝트 정리
```

### 구현 체크리스트

- [ ] FBX 익스포트 자동화 (`bpy.ops.export_scene.fbx`, Deform Only + Anim + Armature Only)
- [ ] FBX 임포트 + fbx_obj 탐지
- [ ] `fbx_armature` 프로퍼티 추가 (ARPCONV_Props)
- [ ] RemapSetup에서 FBX 아마추어를 소스로 사용
- [ ] `_bake_source_to_preview()` 함수 제거
- [ ] Retarget 오퍼레이터 단순화 (베이크 루프 제거, ARP 네이티브만 호출)
- [ ] FBX 임시 파일/오브젝트 정리
- [ ] 여우 파일 전체 흐름 테스트

## 남은 기능

### F1. spine / neck / tail / ear 본 개수 매칭

ARP 네이티브 `set_spine/set_neck/set_tail/set_ears` 함수로 체인 개수를 소스에 맞춘다.

- 모듈: `bl_ext.user_default.auto_rig_pro.src.auto_rig`
- 호출 조건: ARP 아마추어 활성 + Edit Mode + 해당 ref 본 선택
- 호출 후 ref 본 위치 수정 가능, 이후 `match_to_rig` 호출

### F4. 리타게팅 IK 모드

FK 리타게팅 후 발/손 IK 컨트롤러에 위치를 베이크하고 IK 모드로 전환.
코드 완료, FBX 방식 전환 후 재검증 필요.

### F8. 전체 웨이트 전송

구현 완료. 위치 기반 매칭 + 사이드 필터 + 본 길이 비율 분할.
여우 리그 기준 weight paint 모드에서 검증 필요.

### F9. Remap UI 통합

`CollectionProperty` + `UIList`로 Source ↔ Target 매핑 리스트 표시.
상세 설계: `docs/FeaturePlan_v5.md`

### F6. bank / heel 자동 배치 보정

기본 위치 가이드는 foot 방향/길이 비율로 자동 보정, 사용자 이동한 가이드는 유지.

## 우선순위

1. **F10: FBX 클린 아마추어 기반 리타게팅** — 현재 작업 중
2. **F8: 웨이트 전송 실제 검증** — 여우 리그 weight paint 검증
3. **F4: IK 모드 Blender 테스트** — FBX 방식 전환 후 재검증
4. **F9: Remap UI 통합** — 매핑 확인/수정 UI
5. F6: bank / heel 자동 배치 보정

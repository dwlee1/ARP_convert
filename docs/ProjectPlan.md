# BlenderRigConvert 통합 문서

> 최종 수정: 2026-04-01 (F11 구현 완료, 다중 액션 미해결 — 인수인계: docs/F11_Handoff.md)

## 문서 목적

이 문서는 아래 4가지를 한 번에 확인하기 위한 작업 기준 문서다.

- 이 프로젝트가 무엇을 자동화하는지
- 현재 HEAD 코드가 실제로 어떤 경로를 사용하는지
- 승인된 목표 상태가 무엇인지
- 목표 상태까지 남은 격차와 검증 항목이 무엇인지

## 한눈에 보기

### 프로젝트 목표

동물 캐릭터 리그를 Auto-Rig Pro(`dog` preset) 기반으로 통일하고, 리그 생성과 애니메이션 리타게팅을 자동화한다.

### 기준 날짜

- 현재 구현 기준: 2026-03-31 HEAD
- 목표 방향 승인: 2026-03-30

### 현재 구현 흐름 (2026-03-31 HEAD)

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
9. Remap 설정: 원본 FBX 익스포트 → 재임포트 → clean armature 생성
10. ★ clean armature 하이어라키 정규화 (분석 결과 기반 리페어런팅 + 웨이트 0 본 삭제 + 애니메이션 리베이크)
11. clean armature를 source로 .bmap 생성 → build_bones_list → import_config
12. UIList에서 source_bone을 clean armature 본 목록 드롭다운으로 편집 가능
13. clean armature 기반 ARP 네이티브 retarget
14. clean armature는 Retarget 후에도 UI용으로 유지 (다음 Remap Setup 시 정리)
```

```text
비대화형 경로
pipeline_runner.py: clean FBX source 생성 → auto_scale → build_bones_list → import_config → ARP retarget → 정리
03_batch_convert.py: pipeline_runner.py 호출 래퍼
```

### 승인된 목표 흐름 (F10)

```text
공통 목표 경로 (addon / pipeline_runner / batch)
1. 소스 deform 본 분석
2. Preview Armature 생성 및 역할 수정
3. ARP 리그 생성 및 정렬
4. 웨이트/드라이버 처리
5. 원본을 FBX(Deform Only + Anim, Armature Only)로 익스포트
6. FBX를 재임포트해 clean armature 확보
7. clean armature를 source_rig로 사용해 Remap 설정
8. ARP 네이티브 retarget 실행
9. 임시 FBX 파일과 임포트 오브젝트 정리
```

### 현재 상태 요약

- [x] Preview 기반 Build Rig 흐름이 현재 메인 구현 경로다
- [x] addon Step 3.5는 `scene.bones_map_v2` 직접 사용 경로로 구현되어 있다
- [x] addon Retarget는 아직 Preview bake 기반이다
- [x] `pipeline_runner.py`는 아직 clean FBX source를 사용하지 않는다
- [x] `03_batch_convert.py`는 `pipeline_runner.py` 결과에 종속된다
- [x] ARP 프리셋은 `dog`로 고정한다
- [x] 다리 `leg` 3본 매핑과 `foot` 분할 규칙은 반영되었다
- [x] Preview 가이드, `virtual neck`, `virtual toe`, `cc_` 커스텀 본 생성이 구현되었다
- [x] spine / neck / tail / ear 체인 개수 동적 매칭 구현
- [x] `.bmap` 규칙 `map_role_chain` 일관 사용, 동적 컨트롤러 이름 생성
- [x] 자동 추론 개선: spine 추적 + neck 다중 본 + 다리/발 자동 분리 + 구조적 귀 감지
- [x] bank / heel ref 본 자동 배치: foot.head 기준 Z=0, foot+toe 합산 길이 비례
- [x] face/skull 비활성화: append_arp 후 set_facial(enable=False) 호출
- [x] pytest 기반 fixture 테스트 84개 통과
- [x] F1: 웨이트 0 본 프리뷰 제외 (완료)
- [x] F1+: Step 2에 Source Hierarchy 트리 UI 추가 (deform 본 + weight-0 제외 본, 클릭 시 본 선택, role 실시간 표시)
- [x] F2: IK pole vector 위치 매칭 (완료)
- [x] F3: Shape key 드라이버 보존 (완료)
- [x] **F10: FBX clean armature 기반 리타게팅** — 코드 반영 완료
- [x] addon 경로를 clean FBX source 경로로 전환 (RemapSetup + Retarget)
- [x] pipeline_runner 경로를 clean FBX source 경로로 전환
- [x] batch 경로는 pipeline_runner 종속 (자동 전환)
- [~] **F11: clean armature 하이어라키 정규화** — 구현 완료, 다중 액션 리베이크 미해결
- [ ] 여우 `.blend` 전체 흐름으로 F10+F11 실검증
- [ ] F4: IK 모드 리타게팅 재검증
- [ ] F8: 웨이트 전송 실제 검증
- [ ] F9: Remap UI 후속 개선

### 자동화 전략

- 핵심 자동화 목표는 새 동물 리그에서 `skeleton_analyzer.py`가 역할을 최대한 자동 추론하는 것
- 이상적인 흐름은 `자동 추론 → 예외 몇 개만 수정 → Build Rig → Remap → Retarget`이다
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
| `docs/FeaturePlan_v5.md` | F9 Remap UI 현황과 후속 개선 |
| `docs/FoxTestChecklist.md` | 여우 파일 활성 검증 계획 + Preview bake 실험 기록 |
| `docs/RegressionRunner.md` | 대표 샘플 GUI 회귀 테스트 운영 |

## F10: FBX clean armature 기반 리타게팅

### 승인된 방향

- Preview bake 방식은 2026-03-30 실험 결과로 폐기 결정됐다
- 승인된 목표 상태는 `FBX export/import → clean armature → ARP native retarget`이다
- Preview는 계속 분석/역할 수정/UI용으로 유지한다
- addon / pipeline_runner / batch 모두 같은 목표 상태를 향한다

### 전환 근거

- Preview bake 실험에서 rest pose 차이로 꼬임, 위치 어긋남, 발 미끄러짐, 노이즈가 남았다
- 행렬 보정으로도 품질 문제가 근본 해결되지 않았다
- 사용자 검증상 원본을 FBX(Deform Only + Anim)로 익스포트한 뒤 재임포트한 clean armature를 source로 쓰면 ARP 네이티브 retarget이 정상 동작했다

### 경로별 현재 상태와 격차

| 경로 | 현재 상태 | F10 목표 |
|------|-----------|-----------|
| addon | Remap 후 Preview bake → Preview source retarget | clean FBX source 기반 Remap + ARP native retarget |
| `pipeline_runner.py` | source_obj 기반 direct remap/retarget | addon과 동일한 clean FBX source 경로 |
| `03_batch_convert.py` | `pipeline_runner.py` 호출 래퍼 | pipeline 전환 후 동일 경로 검증 |

### 공통 구현 체크리스트

#### addon

- [x] FBX 익스포트 자동화 (`arp_utils.export_clean_fbx`, Deform Only + Anim)
- [x] FBX 임포트 + clean armature 탐지 (`arp_utils.import_clean_fbx`)
- [x] `ARPCONV_Props`에 clean source armature 참조 프로퍼티 추가
- [x] Remap Setup에서 clean FBX armature를 source로 사용
- [x] Preview bake 루프 제거
- [x] Retarget를 ARP 네이티브 호출 중심으로 단순화
- [x] 임시 FBX 파일 / 임포트 오브젝트 정리 (`arp_utils.cleanup_clean_source`)
- [x] UIList source_bone을 `prop_search`로 변경 (clean armature 본 목록에서 선택)
- [x] Retarget 후 clean source 유지 (UI 드롭다운 활성 상태 유지)

#### pipeline_runner

- [x] source_obj direct remap/retarget 대신 clean FBX source 생성 경로 추가
- [x] Remap source를 clean FBX armature로 전환
- [x] 리포트에 clean source 생성/정리 결과 기록 (`clean_source_created`, `clean_source_cleaned` 스텝)

#### batch

- [x] `pipeline_runner.py` 전환 후 batch는 subprocess 래퍼이므로 자동 전환

#### 검증

- [ ] 여우 `.blend` 전체 흐름 테스트
- [ ] clean source 기준 bones_map_v2 로드 확인
- [ ] ARP 네이티브 retarget만 호출되는지 확인
- [ ] 임시 FBX 파일 / 임포트 오브젝트 정리 확인

## F11: Clean Armature 하이어라키 정규화

### 문제

비표준 하이어라키를 가진 원본 아마추어에서 FBX deform-only 익스포트 시:
- non-deform 중간 본이 제거되면서 deform 본의 부모 관계가 끊어짐 (루트 레벨로 이동)
- 웨이트 0 deform 본이 불필요하게 포함됨
- 로컬 회전 좌표계가 원본과 달라져 ARP retarget 품질 저하

실제 사례:
- 사례 1: thigh_L/R, head가 루트 레벨 (non-deform 부모 본 제거됨)
- 사례 2: FK 중복 체인 (spine01_fk → chest_fk → shoulder) 존재

### 해결 방향

`analyze_skeleton()` → `filter_deform_bones()` → `_reconstruct_spatial_hierarchy()`가 이미 올바른 deform 본 간 부모 관계를 계산함. 이 결과(`bone_data`)를 clean armature에 실제로 적용.

### 구현 계획

`arp_utils.py`에 `normalize_clean_hierarchy(clean_obj, bone_data)` 추가:

1. clean armature 본과 bone_data 본의 부모 관계 비교 → 리페어런팅 대상 식별
2. bone_data에 없는 clean 본 식별 → 삭제 대상 (웨이트 0 deform 본)
3. 모든 액션의 모든 프레임에서 대상 본의 월드 행렬 기록
4. Edit Mode에서 리페어런팅 + 불필요 본 삭제
5. Pose Mode에서 기록한 월드 행렬 재적용 → FCurve 키프레임 삽입

호출 위치: `create_clean_source()` 직후, `ensure_retarget_context()` 직전 (addon + pipeline_runner 공통)

### 체크리스트

- [x] `arp_utils.py`: `normalize_clean_hierarchy()` 구현 (플랫 하이어라키 + rest pose 교정 + NLA strip 평가)
- [x] `arp_convert_addon.py`: RemapSetup에서 정규화 호출
- [x] `pipeline_runner.py`: pipeline에서 정규화 호출
- [x] rest pose 교정 확인 (bone_data head/tail/roll 적용)
- [x] 기본 액션 리베이크 정상 확인
- [ ] **다중 액션 리베이크 미해결** — Blender 4.5 Action Slot 시스템 문제 (상세: `docs/F11_Handoff.md` 섹션 6)
- [x] Step 2 부모 편집 UI (ARPCONV_OT_SetParent + prop_search)
- [ ] Blender 수동 테스트: 사례 1, 2에서 정규화 후 retarget 품질 확인

## F9: Remap UI 통합

### 현재 구현 기준

- addon에는 Step 3.5 `Remap Setup`이 이미 존재한다
- `.bmap`를 생성한 뒤 ARP `scene.bones_map_v2`에 로드하는 경로가 현재 구현이다
- 패널은 `bones_map_v2`를 `UIList`로 직접 표시하고 수정한다
- Retarget는 사전에 채워진 `bones_map_v2`를 전제로 동작한다

### 남은 개선

- 매핑 통계와 가시성 개선
- 미매핑 / 폐기된 source bone 가시화
- ~~F10 clean source 전환 후 Remap source 일관성 점검~~ → source_bone `prop_search` 적용으로 해결

## 후속 기능

### F4. 리타게팅 IK 모드

코드는 이미 존재한다. F10 전환 후 Blender 실제 파일 기준으로 다시 검증한다.

### F8. 전체 웨이트 전송

구현은 완료됐다. 위치 기반 매칭 + 사이드 필터 + 본 길이 비율 분할을 실제 여우 리그 weight paint 모드에서 검증해야 한다.

### F6. bank / heel 자동 배치 보정

기본 위치 가이드는 foot 방향/길이 비율로 자동 보정하고, 사용자가 이동한 가이드는 유지한다.

## 우선순위

1. **F11 하이어라키 정규화** — clean armature 리페어런팅 + 웨이트 0 본 삭제 + 애니메이션 리베이크
2. **F10+F11 실검증** — 비표준 하이어라키 원본에서 retarget 품질 확인
3. **F4 재검증** — F10 전환 후 IK 모드 확인
4. **F8 실제 weight 검증** — 여우 리그 weight paint 검증
5. **F9 후속 개선** — 가시성/통계/UI 보강

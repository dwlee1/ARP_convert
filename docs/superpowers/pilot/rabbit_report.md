# Rabbit 파일럿 최종 리포트

**날짜**: 2026-04-17
**브랜치 (Blender 레포)**: `feat/unity-migration-p0-p1`
**브랜치 (Unity 레포)**: 미생성 (Task 16 스킵)
**결과**: **부분 통과 — 파이프라인 5단계는 완료, Unity 반입 이전 품질 기준 미달로 중단**

## 1. 소요 시간 breakdown

커밋 타임스탬프 기반 대략치 (단일 세션, 총 ~5시간).

| 단계 | 커밋 범위 | 소요 |
|------|----------|------|
| Task 1 스캐폴딩 | ddf438d | ~3분 |
| Task 2~7 build_migration_inventory TDD | 3ffa44d ~ 0011276 | ~25분 |
| Task 8 Phase 0 실행 + 수동 분류 | → de924b7 | ~80분 |
| Task 9~10 fbx_to_blend TDD + Blender 본문 | b68dc4e ~ abad824 | ~30분 |
| Task 11 구조 baseline | → 050dc43 | ~10분 |
| Task 12 fbx_to_blend 실행 + 검증 | (blend 커밋 안 함) | ~5분 |
| Task 13 BlenderRigConvert 5단계 (pipeline_runner --auto) | (blend 커밋 안 함) | ~17초 자동 + 검증 5분 |
| Task 14 ARP 익스포트 + sandbox | **스킵** (품질 기준 미달) | 0 |
| Task 15 diagnosis | → 0efe2c0 | ~30분 |
| Task 16 swap | **스킵** | 0 |
| Task 17 play mode 검증 | **스킵** | 0 |
| Task 18 이 리포트 | (진행 중) | ~15분 |
| **총계** | | **~3.5시간 활성 작업** |

## 2. Diagnosis 결과 요약

상세는 [rabbit_diagnosis.md](rabbit_diagnosis.md).

| 영역 | 결과 |
|------|------|
| FBX 내부 구조 | 부분 OK — source 37본 중 7본(다리 중간 본) bone_pairs 누락, 9본 cc_ 오분류 |
| Unity reference 보존 | **측정 불가** (Task 14 스킵, Unity 반입 없음) |
| 시각 품질 (절대 기준) | **FAIL** — rest pose 이상 (발/눈 leaf 본 length, FK 잔재 본 유입, root 오배정) |

**핵심 결함 4가지** (diagnosis 상세):
1. 소스 FBX에 남아있던 이전 FK 컨트롤러(`*_FK`, `chest_nomove`)가 cc_로 유입
2. Blender FBX importer의 leaf 본 tail 손실 → `eye_L/R`, `mouth` 길이 비정상
3. `DEF-root` + `DEF-pelvis` 공존으로 root 오배정 (pelvis가 c_root_master로 감)
4. 현재 파이프라인이 아티스트 .blend 원본을 가정한 설계 — FBX 입력 경로는 미검증

**제약**: Task 11에서 baseline 녹화를 생략해 before/after 영상 diff가 불가능. 품질 판정은 Blender GUI 육안 확인에 한정됨.

## 3. 수작업으로 고친 항목 + 타임스탬프

**없음**. 파일럿이 Build Rig 후 품질 실패로 조기 중단되어 Task 14(ARP 익스포트) 이후 단계에서 수행될 예정이었던 수동 수정(Preview 역할 재할당, prefab override 복구 등)이 실행되지 않음.

이는 역설적으로 Phase 2 판단의 중요 신호다: **"중단 시점까지의 기본 경로만 실행했을 때 리그 품질이 Unity 반입 불가 수준"** 이라는 사실 자체가 1마리 단위 자동화로는 부족하다는 증거.

## 4. 자동화 후보 리스트 (Phase 2 인풋)

| 후보 | 관찰 | 1마리 절감 | 20마리 절감 |
|------|------|-----------|-------------|
| **A. FBX 전처리 도구** (`tools/fbx_to_blend.py` 확장) — 컨트롤러 본 필터 + 고아 본 제거 + leaf tail 정규화 | 관찰 1, 2 정면 해결 | ~15분 수작업 → 0 | ~5시간 |
| **B. skeleton_analyzer FBX 대응** — root 이름 힌트 / DEF-prefix 인식 / 다리 체인 개수 유연화 | 관찰 3 + 다리 중간 본 누락 해결 | ~10분 수동 역할 수정 → 0 | ~3시간 |
| **C. blend-first fallback** — 아트 원본 .blend 확보 경로 | 관찰 1~4 전체 우회 | 신규 경로 (기존 여우 workflow 재사용) | 원본 확보에 따라 가변 |
| **D. migrate_batch.py orchestrator** | Task 11~17 수작업 오케스트레이션 | ~10분 → 자동 | ~3시간 |

A+B 도구화 투자: **3~5일**. 20마리 기준 절감 추정 ~8시간 + 품질 개선 (수치화 불가).
C는 원본 .blend 확보 가능 여부가 전제. 확보 못 하는 동물은 A+B 필수.

## 5. blend-fallback 필요 여부

| 체크 | 결과 |
|------|------|
| Unity FBX에서 역할 추론 신뢰도 ≥50%? | **부분 — 21본 매핑됐으나 root/eye/FK 잔재 문제로 실사용 불가 수준** |
| Shape key 손실 있음? | 미측정 (소스 FBX의 shape key 존재 여부 별도 확인 필요) |
| round-trip 품질 열화 심각? | **Y** (발/눈 leaf 본 길이, 다리 중간 본 누락) |

→ **하나 이상 Y**. blend-fallback 병행 검토 필요.

다만 완전한 fallback(C only)이 아니라 **"원본 .blend 확보 가능한 동물은 C, 불가한 동물은 A+B"** 혼합이 현실적.

## 6. 다음 동물(lopear)에 적용 가능한 공통 패턴

rabbit에서 발견한 패턴은 **lopear에도 거의 동일하게 나타날 가능성이 높다**:
- 같은 `Assets/5_Models/02. Animals/00.Rabbit/` 폴더에 lopear_animation.fbx가 함께 존재
- 같은 아티스트/같은 export 파이프라인 출신일 확률 큼 → `*_FK`, `chest_nomove` 등 컨트롤러 잔재 동일 존재 예상
- 즉 rabbit에서 도구화한 것(A)을 lopear에 그대로 재사용 가능

lopear를 두 번째 파일럿으로 삼는 것이 plan의 원 의도지만, Phase 2 결정(A 구현 여부)이 나온 뒤 진행하는 게 맞음.

## 7. Phase 2 권고

선택지 (diagnosis 상세 참조):

- (a) 파일럿 성공 + 도구화 추가 불필요 → Phase 3 즉시 **← 해당 없음 (실사용 불가)**
- (b) 파일럿 성공 + N개 도구 개발 → 각각 Tier 3 spec/plan 분기
- (c) 파일럿 실패 → blend-first 재설계

→ **선택: (b)와 (c)의 혼합**

**근거**:
1. 현 파이프라인은 Build Rig까지 자동 성공 — 완전 실패가 아니라 **"입력 정화(pre-processing)" 단계만 누락**된 구조
2. 관찰 1, 2(컨트롤러 필터 + leaf tail 정규화)는 **순수 FBX 파일 변환 문제** → `tools/fbx_to_blend.py` 확장으로 해결 가능 (후보 A, 1~2일)
3. 관찰 3(root 오배정), 다리 중간 본 누락은 skeleton_analyzer 룰 확장(후보 B, 2~3일)
4. 동시에 아트 팀 원본 .blend 확보 병행 — 확보되는 종은 C 경로로 우회

**Phase 2 제안 순서**:
1. **먼저**: 아트 팀에 21마리 원본 .blend 보유 여부 조사 (C 가능성 즉답)
2. **병행**: 후보 A(FBX 전처리) Tier 3 spec 작성 → 구현 → Rabbit 재실행으로 재측정
3. **A 결과 보고**: B(analyzer 확장)가 여전히 필요한지 판단

**Phase 2는 이 계획의 범위 밖** — 별도 Tier 3 spec/plan으로 분기한다.

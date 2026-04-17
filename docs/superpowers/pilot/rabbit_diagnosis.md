# Rabbit Diagnosis (Sandbox 이전 중단)

**날짜**: 2026-04-17
**Baseline**: `rabbit_baseline.md`
**Sandbox 경로**: *(Task 14~17 스킵 — 아래 "중단 사유" 참조)*
**BlenderRigConvert 커밋**: `050dc43`

## 요약

Phase 1b~1c는 정상 완료(Build Rig + 리타겟 + Cleanup, pipeline_runner 17초 성공).
그러나 GUI 육안 확인 시 **리그 품질이 Unity 반입 불가 수준**으로 확인되어
Task 14(ARP FBX 익스포트) 이후를 중단하고 diagnosis 단계로 넘어감.

핵심 관찰: **현재 파이프라인은 "아티스트 .blend 원본"을 가정하고 설계됨. Unity FBX 입력은 4가지 구조적 gap을 만들어 파이프라인이 cover하지 않는 케이스다.**

## 중단 사유 (GUI 관찰 4가지)

사용자가 `pilot/rabbit_arp.blend`를 Blender GUI로 열어 확인.

| # | 관찰 | 원인 추정 | 영향 |
|---|------|-----------|------|
| 1 | 이전 익스포트 컨트롤러(FK/nomove 잔재)가 ARP에 cc_ 커스텀 본으로 유입 | 소스 FBX에 리깅 컨트롤러 본이 남아있음. skeleton_analyzer의 "웨이트 0 본 필터(F1)"가 Unity FBX의 컨트롤러를 걸러내지 못함 | `chest_FK`, `chest_nomove`, `spine01_FK`, `Food` 등이 cc_로 생성 → 리그 구조 오염 |
| 2 | 발/눈 본 길이가 비정상적으로 긴 상태로 생성 | Blender FBX importer의 알려진 한계: leaf 본 tail 정보 손실 → tail을 head + default length로 자동 생성. `eye_L/R`, `mouth`의 length=0.3049(=`head` 본 length와 동일)로 확인됨 | 발/눈/입 등 leaf 본의 ref 배치 왜곡 |
| 3 | root 본이 커스텀 본으로 생성 | 소스에 `DEF-root` + `DEF-pelvis` 공존. skeleton_analyzer가 pelvis를 root_master로 잡고, 실제 root는 unmapped 처리 | `c_root_master.x ← DEF-pelvis` 매핑, `root` 본은 cc_로 전락 |
| 4 | ARP 컨버터가 .blend 원본을 가정한 설계 | 여우/너구리 검증은 전부 아티스트 .blend 기반. FBX import 경로는 이번이 첫 시도 | 위 1~3의 근본 원인. skeleton_analyzer / fbx_to_blend / BuildRig 전체 체인이 FBX 입력에 맞춰진 적 없음 |

## FBX 내부 구조

### 본 개수

| 항목 | old (source blend) | new (ARP blend) | 결과 |
|------|--------------------|-----------------|------|
| armature 개수 | 1 (`Armature_rabbit_unity_source`) | 1 (`rig`, is_arp=True) | OK |
| bone 개수 | 37 | 290 | ARP 프리셋 전개로 증가 (정상) |
| 매핑 커버리지 | — | bone_pairs 30개 중 역할=21 / 커스텀=9 | **소스 37본 중 7본은 bone_pairs에 포함되지 않음** (leg_L/R, foot_L/R, upperarm_L/R, arm_L/R — 다리 중간 본 누락) |
| AnimationClip 개수 | 82 (6 FBX × 중복 인스턴스) | 82 (`_remap` 제거 후 원본 이름) | OK |
| AnimationClip 이름 | `Armature\|Armature\|<name>[.NNN]` | 동일 (cleanup rename으로 원본 복원) | 기술적 일치. 단, Unity baseline 26 clip과는 이름 형식이 다름 (아래 참조) |

### Baseline 26 clip과 post 82 clip 이름 형식 비교

- Baseline(`rabbit_baseline.md`): `Armature|Rabbit_idle`, `Rabbit_idle` 등 (총 26개, `internalIDToNameTable` 기준)
- Post(`rabbit_arp.blend`): `Armature|Armature|Rabbit_idle`, `Armature|Armature|Rabbit_idle.001` 등 (총 82개)
- 차이 원인: `tools/fbx_to_blend.py`가 6개 FBX를 병합하며 중복 clip에 `.001~.004` suffix 부여. `Armature|Armature|` 이중 prefix는 FBX importer의 take name 이중 wrap.
- Unity 반입 시 실제 clip fileID 연결은 **검증 불가** (Task 14~17 스킵).

### Bone 이름 매핑표 (bone_pairs 전수)

역할 매핑 (21본, `is_custom=False`):

| source | ARP target | 비고 |
|--------|-----------|------|
| DEF-pelvis | c_root_master.x | root 오배정 (원래 root 본이 따로 있음 — 관찰 3) |
| DEF-spine01 | c_spine_01.x | OK |
| DEF-chest | c_spine_02.x | OK |
| __virtual_neck__ | c_neck.x | source에 neck 없음 → 자동 가상 neck |
| DEF-head | c_head.x | 위치 의심 (chest_nomove 자식 — 관찰 1) |
| DEF-shoulder_L/R | c_thigh_b_dupli_001.l/r | 앞다리 첫 본만 매핑 |
| DEF-hand_L/R | c_foot_ik_dupli_001.l/r | 앞다리 leaf만 매핑 |
| DEF-thigh_L/R | c_thigh_b.l/r | 뒷다리 첫 본만 매핑 |
| DEF-toe_L/R | c_foot_ik.l/r | 뒷다리 leaf만 매핑 |
| DEF-ear01~03_L/R | c_ear_01~03.l/r | OK (3본 귀 정상 매핑) |
| DEF-tail_01/02 | c_tail_00/01.x | OK |

커스텀 유입 (9본, `is_custom=True`):

| source bone | 원인 |
|-------------|------|
| root | skeleton_analyzer가 pelvis를 root로 오판 → 진짜 root가 cc_로 밀림 |
| Food | FBX에 parent=None length=1.0으로 존재. 이름이 "Foot"의 오타로 추정되는 고아 본 |
| center | pelvis 부모 본, 역할 추론 실패 |
| chest_FK / spine01_FK / chest_nomove | FK 컨트롤러 잔재 (관찰 1) |
| eye_L / eye_R / mouth | head 자식 leaf (CLAUDE.md 규칙에 따라 cc_로 처리되는 게 의도된 동작이나, length=0.3049로 head 길이를 승계 — 관찰 2) |

### 앞다리/뒷다리 체인 누락

source 앞다리: `shoulder_L → upperarm_L → arm_L → hand_L` (4본)
source 뒷다리: `thigh_L → leg_L → foot_L → toe_L` (4본)

bone_pairs에는 각 다리의 **첫 본 + 끝 본**만 등록됨. 중간 2본(`upperarm_L/arm_L`, `leg_L/foot_L`)은 unmapped.
skeleton_analyzer의 leg/foot 역할 감지 규칙이 "3본 다리 + 2본 발" 패턴을 기대하지만 실제는 "4본 + 0본" 구조 → 잘못 분할.

## Unity reference 보존

| 항목 | 예상 | 실측 | 결과 |
|------|------|------|------|
| `.meta` swap 시 GUID 유지 | 유지 | — | **측정 불가** (Task 14 스킵) |
| m_Motion 살아남은 비율 | 21/21 | — | 측정 불가 |
| NavMeshAgent override 유지 | 유지 | — | 측정 불가 |
| BoxCollider override 유지 | 유지 | — | 측정 불가 |
| MonoBehaviour override 유지 | 유지 | — | 측정 불가 |
| Animator.Controller override 유지 | 유지 | — | 측정 불가 |
| Transform(본) override Missing 수 | 미상 | — | 측정 불가 |

**스킵 사유**: 현 `rabbit_arp.blend`를 FBX로 익스포트해 Unity에 반입해도 위 4가지 문제가 남아 있어 프리팹이 정상 동작할 가능성이 없음. 반입 후 prefab을 Sandbox FBX에 강제 연결해 Missing을 측정하는 작업(Task 15 Step 2 원본 스펙)은 파이프라인 수정 후에 의미가 생김.

## 시각적 품질 (절대 기준)

Task 11에서 baseline 녹화 생략. 대신 Blender GUI 육안 기준.

| 항목 | 결과 |
|------|------|
| rest pose가 자연스러운가 | **FAIL** — 발/눈 본 길이 비정상, FK 잔재 본이 리그 구조에 섞여 있음 |
| skin binding 안정성 | 미확인 (Unity 미반입) |
| idle/walk/run 재생 | 미확인 (Unity 미반입) |

## 자동화 후보 메모 (Phase 2 인풋)

각 항목은 "파이프라인에 추가하면 FBX 입력 경로를 열 수 있는 수정 후보"이다.

### 후보 A: Unity FBX 전처리 도구 (`tools/fbx_to_blend.py` 확장)

목표: FBX import 직후 컨트롤러 본 / 고아 본 / 이상한 root 네이밍을 자동 정리.

- **A-1**. 컨트롤러 본 필터: `*_FK`, `*_IK`, `*_nomove`, `*_ctrl`, `*_pole` suffix 본 삭제 또는 숨김
  (rabbit의 `spine01_FK`, `chest_FK`, `chest_nomove` 등 대응)
- **A-2**. 고아 본(parent=None & not armature root) 제거
  (rabbit의 `Food` 대응)
- **A-3**. Leaf 본 tail 길이 정규화: leaf이면서 parent 본과 length 동일한 본을
  "아이콘 크기(예: parent length × 0.1)"로 축소
  (`eye_L/R`, `mouth`의 0.3049 → 적정 길이로 수정)
- 소요 시간 추정: 1~2일. 20마리 × 평균 5~10분 수작업 절감 가능.

### 후보 B: skeleton_analyzer의 FBX 네이밍 대응

목표: `DEF-*`, `*_L/_R` 양식 등 Unity FBX 네이밍을 1급 입력으로 인식.

- **B-1**. root 추론 규칙 확장: `root`, `Root`, `Hips`, `DEF-root` 등 이름 힌트 우선
  (현재는 "자식 많은 상위 본"만 보고 pelvis를 root_master로 오판)
- **B-2**. 앞다리/뒷다리 체인 개수 자동 감지: "4본 + 0본" 구조(shoulder 제외 3본)도 cover
- **B-3**. DEF-prefix 네이밍을 deform으로 명시 인식 (현재는 일반 이름으로 취급)
- 소요 시간 추정: 2~3일. 사례 누적 없이 설계만으로는 regression risk.

### 후보 C: blend-first fallback (플랜의 대안 경로)

목표: Unity FBX 이주를 포기하고 아트 팀 원본 .blend 파일을 요청.

- 장점: 검증된 경로(여우/너구리 완료). 추가 도구 개발 비용 0.
- 단점: 21마리 전부의 원본 .blend 확보가 전제. 누락된 종은 fallback 불가.
- 확인 필요: 아트 팀에 21마리 원본 .blend 보유 여부 문의.

### 후보 D: 현상 유지 (Unity 이주 포기)

- 기존 Unity 리그로 계속 운영. ARP 변환 이점 포기.
- 이 파일럿 자체가 이 결정의 근거를 만드는 목적이었음.

## 권고 (Task 18에서 최종화)

| 후보 | 투자 | 커버리지 | 권고 |
|------|------|---------|------|
| A (FBX 전처리) | 1~2일 | 관찰 1, 2 해결 | **1순위** — 가장 효율적 |
| B (analyzer 확장) | 2~3일 | 관찰 3, 체인 누락 해결 | 2순위 (A 후 재측정 결과 보고 결정) |
| C (blend fallback) | 원본 확보 시간 | 전체 문제 우회 | 원본 확보 가능하면 병행. 확보 불가면 A+B 조합 필수 |
| D (포기) | 0 | 문제 발생 없음 | 최후 옵션 |

**Phase 2 결정 인풋**:
1. 아트 팀 원본 .blend 확보 가능 여부 (C 가능성 판단)
2. A만으로 재시도 시 나머지 문제(B 영역)가 얼마나 남는지 — A 구현 후 Rabbit 재실행으로 측정
3. A+B 도구화 투자 3~5일 vs 21마리 수작업 ≒ ? (실측치 없어 Task 18 보류)

# Unity 프로젝트 ARP 이주 설계 (FBX-first)

**날짜**: 2026-04-16
**대상 프로젝트**: `C:\Users\manag\GitProject\LittleWitchForestMobile`
**범위**: Unity 프로젝트의 사족보행 동물 21마리를 BlenderRigConvert 애드온 기반 ARP 리그로 이주
**전략**: FBX-first (primary) + blend 소환 (fallback)
**Tier**: 3 (신규 서브시스템 다수, 21마리 × feat 브랜치 배치 관리)

## 배경 및 문제

### 현재 상태
BlenderRigConvert 애드온으로 동물 리그를 ARP 통일하는 파이프라인은 완성되었으나, 실제로 Unity 프로젝트에 적용한 이력이 없다. 이주를 시작하려니 다음 문제가 드러난다:

1. **원본 식별 문제** — `Asset/Blender/` 하위 1066개 blend 중 어느 파일이 Unity FBX의 실제 원본인지 추적 불가. 매핑 문서 없음.
2. **호환성 파기 리스크** — ARP 변환 시 본 이름/계층이 바뀌어 Unity 프리팹의 variant override 다수 invalid 예상
3. **애니메이션 이름 변경** — ARP 리타겟이 `_remap` 접미사 붙임. Unity AnimationController의 m_Motion 참조가 깨질 위험
4. **작업 규모 불확실** — Blender 레포의 "사용중 189개"가 Unity에서 실제 사용되는 수와 다름

### Unity 프로젝트 실측치
- Model FBX: 약 257개 (`Assets/5_Models/02. Animals/`)
- Animation FBX (master 리그+애니메이션): **42개**
- 프리팹: 315개 (`Assets/3_Prefabs/Animals/`)
- AnimatorController: 132개 (`Assets/6_Animations/Animals/Controllers/`)
- 애드온이 지원하는 사족보행 대상: **21마리** (나머지 19개는 조류/수생/무척추 등 out_of_scope)

### 이주 Rig 구조 (Rabbit 샘플 기준)
- `rabbit_animation.fbx` (master) = Rig + 26 AnimationClip
  - 이 FBX의 auto-generated 프리팹을 `Animal_0` ~ `Animal_12` 등이 **Prefab Variant**로 상속
  - 상속 프리팹은 NavMeshAgent/BoxCollider/MonoBehaviour/Animator.Controller 등을 override
- `Rabbit_DutchBrown.fbx`, `Animal_2002.fbx`, ... = skin variants (rig 공유)
- `AnimalController_0_Rabbit.controller` = 21 state, 모든 m_Motion이 master FBX의 `(GUID, fileID)` 참조
- `animationType: 2` (Generic rig, Humanoid 아님)

### 호환성 보존 조건
- **FBX GUID 보존**: `.meta` 파일 유지 → FBX 파일만 swap 시 GUID 안 바뀜 → 프리팹/컨트롤러의 FBX 참조 유지
- **AnimationClip 이름 보존**: 애드온 Cleanup이 `_remap` 제거 → 이름 유지 → fileID 유지 (Unity는 clip 이름에서 fileID를 derive) → AnimatorController 참조 유지
- **치명적 파기 대상**: 프리팹 variant의 Transform(본) 수준 override는 fileID가 달라지므로 "Missing" 처리 예상 → 파일럿에서 실제 영향 범위 측정 필요

### 핵심 가정 (파일럿에서 반드시 검증)

이 설계는 다음 가정 위에 서 있다. 파일럿 단계에서 하나라도 깨지면 설계 재고가 필요하다.

1. **Unity FBX fileID는 clip 이름에서 결정적(deterministic)으로 파생**된다. 즉 동일한 clip 이름을 유지하면 swap 후에도 같은 fileID가 생성되어 AnimatorController의 m_Motion 참조가 유지된다. (Unity 내부 구현 의존)
2. **`.meta` 파일을 보존하고 FBX 본문만 교체하면 GUID가 유지**된다. Unity가 메타 기반 GUID tracking을 하는 한 성립.
3. **BlenderRigConvert 애드온은 deform-only Armature (컨트롤러 본이 없는 상태)에서도 동작**한다. Unity FBX는 export 시 컨트롤러가 스트립되어 deform 본만 남아 있음.
4. **Prefab variant의 non-Transform override (NavMeshAgent, BoxCollider, MonoBehaviour, Animator.Controller 등)는 Transform과 독립**이다. 본 fileID가 바뀌어도 이들 override는 유지된다.

## 전략: FBX-first + Blend fallback

**Unity FBX를 source of truth로 사용한다**. 각 사족보행 동물마다:

1. Unity의 `{species}_animation.fbx` + 연관 model FBX들을 Blender로 import
2. 1개의 블렌더 armature + 여러 메시로 재구성
3. BlenderRigConvert 애드온으로 ARP 리그 변환 + 리타겟
4. ARP 네이티브 익스포터로 Unity에 반입 (`.meta` 보존)

**FBX-first인 이유**:
- 원본 식별 문제 소멸 (Unity FBX가 정의상 현재 프로덕션 상태)
- 재현 가능성 확보 (Unity 프로젝트 + 애드온만 있으면 누구나 재실행)
- 원본 blend가 outdated일 가능성 배제 (FBX만 수정됐을 위험)

**Blend fallback 조건**:
- Unity FBX에서 애드온 역할 추론 신뢰도가 너무 낮음 (< 50%)
- Shape key driver 등 FBX에 없는 데이터가 필요
- 파일럿에서 round-trip 품질 열화 확인됨

## 범위

### In-scope
- Unity 프로젝트의 **사족보행 21마리 animation FBX + 연관 model FBX**
- `tools/build_migration_inventory.py`, `tools/fbx_to_blend.py` 신규 스크립트 2개
- 기존 BlenderRigConvert 애드온은 변경 없이 사용 (필요 시 최소 확장만)

### Out-of-scope
- 이미 ARP 기반인 220개 blend 파일 (재변환 안 함)
- 조류/수생/무척추 동물 19개 (`duck`, `bald_eagle`, `flamingo`, `flamingo_v1`, `dolphin`, `orca`, `baby_orca`, `swan`, `baby_duck`, `baby_eagle`, `seal`, `eagle_owl`, `puffin`, `seagull`, `sparrow`, `clam`, `crab`, `shellsand`, `albatross`)
- 개구리 2종 (`frog`, `redfrog`) — 사족이나 구조 특이로 out_of_scope 확정
- Humanoid 전환 (Generic 유지)
- 애니메이션 신규 제작 (기존 액션만 리타겟)
- Unity 게임 코드 수정
- AnimatorController 상태머신 그래프 재설계

### 사족보행 in_scope 21마리 (초안)

```
rabbit, lopear, fox, bear, deer, stag, wolf, turtle,
llama, sheep, raccoon,
baby_rabbit, baby_wolf, baby_bear, baby_turtle,
blackcat, whitecat, babyfox,
mole, hedgehog, capybara
```

(Phase 0 수동 리뷰에서 확정. turtle/mole이 구조 특이 시 제외 가능)

## 성공 기준

1. 사족보행 21마리 animation FBX 전부 ARP 기반으로 교체됨
2. 해당 동물의 모든 프리팹(Rabbit 계열 13개 외 동물별 N개)이 Play mode에서 모든 motion state 정상 재생
3. Unity Console에 **baseline 대비 새로 생긴** Missing Transform / Missing Script / Missing Component 경고 없음
4. 구 blend 파일은 `Asset/Blender_archive/`로 이동 (2주 안정기 후 삭제 검토)
5. `docs/UserGuide.md`에 Unity 이주 플레이북 반영
6. `pytest tests/ -v` + `ruff check scripts/ tests/` 모두 통과

## 전체 Phase 구조

```
Phase 0. 인벤토리 (간소화)
  └ Unity FBX 42개 스캔 → 매핑 CSV 1장 (사족보행 21개 in_scope 분류)

Phase 1. 파일럿 — Rabbit 1마리 End-to-End
  ├ 1a. Pre-change 스냅샷
  ├ 1b. FBX → Blender 재구성
  ├ 1c. BlenderRigConvert 실행
  ├ 1d. ARP 익스포트 → Unity sandbox 반입
  ├ 1e. Diagnosis (깨진 항목 전수조사)
  ├ 1f. 실제 교체 (.meta 보존 swap)
  ├ 1g. Play mode 검증
  └ 1h. 파일럿 리포트

Phase 2. 도구화 결정 게이트 (파일럿 회고)
  └ ROI 기준 도구화 판단 → 필요 도구 개발 → Phase 3 준비

Phase 3. 배치 변환 (나머지 20마리)
  └ 동물별 feat 브랜치 1개, 체크리스트 진행

Phase 4. 마무리 정리
  └ archive, 문서 업데이트, 회귀 테스트
```

---

## Phase 0 — 인벤토리

### 산출물
`docs/MigrationInventory.csv` — 42개 animation FBX 전수 목록

### 컬럼

| 컬럼 | 설명 | 예 |
|------|------|----|
| `id` | 식별자 (species 폴더명 기반) | `rabbit`, `fox`, `cat_black` |
| `animation_fbx_path` | Unity 기준 상대 경로 | `00.Rabbit/rabbit_animation.fbx` |
| `animation_fbx_guid` | `.meta`의 GUID | `f01ef593d9cf73a4e94a2ab37b4745c1` |
| `model_fbx_paths` | 연관된 model FBX 리스트 | `[Rabbit_DutchBrown.fbx, Animal_2002.fbx, ...]` |
| `controller_paths` | 연관 AnimatorController 경로 | `[Landmark/AnimalController_0_Rabbit.controller]` |
| `prefab_count` | 이 animation FBX를 참조하는 프리팹 수 | `38` |
| `clip_count` | FBX 내 AnimationClip 수 | `21` |
| `clip_names` | 클립 이름 리스트 | `[Rabbit_idle, Rabbit_walk, ...]` |
| `locomotion` | `quadruped` / `biped_bird` / `aquatic` / `amphibian` / `other` | `quadruped` |
| `scope` | `in_scope` / `out_of_scope` / `pending` | `in_scope` |
| `source_blend_hint` | (있으면) 원본 blend 후보 경로 | `Asset/Blender/normal/rabbit/blender/rabbit_animation_all.blend` |
| `status` | `not_started` / `in_progress` / `converted` / `validated` / `shipped` | `not_started` |
| `notes` | 특이사항 | `skin variants 5개` |

### `tools/build_migration_inventory.py`

예상 80줄. 입력: Unity 프로젝트 루트 경로. 출력: CSV.

동작:
1. `Assets/5_Models/02. Animals/**/*animation*.fbx` glob → animation FBX 경로 목록
2. 각 FBX의 `.meta`에서 `guid` 추출
3. `.meta`의 `internalIDToNameTable`에서 `second:` 필드로 clip 이름/수 추출
4. 같은 폴더의 다른 `.fbx` = model FBX로 집계
5. `Assets/6_Animations/Animals/Controllers/**/*.controller` 스캔 → `m_Motion`의 guid가 매칭되는 controller 수집
6. `Assets/3_Prefabs/Animals/**/*.prefab` 스캔 → `m_SourcePrefab`의 guid가 매칭되는 prefab 수집
7. `locomotion` 컬럼은 기본값 `pending`으로 씀 (수동 확정 단계)
8. CSV 저장

**분류는 자동화 포기**: 폴더/파일명으로 100% 분류 안 됨. 42줄이라 수동 훑기 5분이면 충분. 스크립트는 `pending`으로 두고 사람이 `quadruped/out_of_scope` 확정.

### Phase 0 완료 조건
- CSV 42 row 생성됨
- `locomotion` 전수 확정 (pending 0)
- `scope = in_scope` row 21개 (±2, 최종 리뷰에 따라)

---

## Phase 1 — 파일럿 (Rabbit)

### 왜 Rabbit
- `Rabbit_AllAni_251112_ARP.blend` 기존 변환 샘플 존재 (비교 기준)
- skin variant 5개 (`Rabbit_DutchBrown`, `Animal_2002`, `Animal_2011`, `Animal_3161`, `rabbit_CherryBlossom`) → 재구성 스크립트 스트레스 테스트
- 26 clip → clip 이름 보존 검증 충분
- 덤으로 `lopear_animation.fbx`가 같은 폴더 → 후속 검증 대상 즉시 확보

### 1a. Pre-change 스냅샷

**목적**: 변경 전 정상 상태 기록 → 변경 후 diff 가능

작업 (간소 버전):
1. Unity Play mode에서 Rabbit 대표 프리팹 1개 (`Animal_0`) 선택
2. idle, walk, run 3개 state 1분 녹화 (화면 캡처 또는 Unity Recorder)
3. 다음을 `docs/superpowers/pilot/rabbit_baseline.md`에 기록:
   - FBX GUID 전수
   - AnimationClip 이름/fileID 매핑표 (`rabbit_animation.fbx.meta`에서 복사)
   - 프리팹 override 개수 (인스펙터 우상단 숫자)
   - Console 기존 경고 텍스트 복사

소요: 15~20분

### 1b. FBX → Blender 재구성

**목적**: Unity FBX들을 1개 blend 파일로 통합

`tools/fbx_to_blend.py` — 예상 60~80줄

입력: `--id rabbit` (CSV에서 해당 row 룩업)
출력: `pilot/rabbit_unity_source.blend`

동작:
1. CSV에서 row 로드
2. 새 blend 열기 (factory reset 씬)
3. `animation_fbx_path` import → 최초 armature + 모든 Action
4. 각 `model_fbx_paths` import → mesh 확보, 따라온 중복 armature 삭제
5. mesh 5개를 step 3 armature에 재parent (armature modifier 재설정)
6. save as

**검증**: armature 선택 → Pose mode에서 root 이동 → 모든 mesh가 따라오는지 눈 확인

### 1c. BlenderRigConvert 실행

기존 `docs/UserGuide.md` 그대로:
1. Step 1 Create Preview → 신뢰도 확인 (목표 >70%)
2. Step 2 역할 수정 (필요 시)
3. Step 3 Build Rig
4. Step 4 Setup Retarget → Re-Retarget → Copy Custom Scale
5. Step 5 Cleanup

저장: `pilot/rabbit_arp.blend`

**체크포인트**: 이 단계 실패 시 (Build Rig 에러, 신뢰도 극저 등) → blend-first fallback 강제. 설계 수정 필요.

### 1d. ARP 익스포트 → Unity sandbox

**목적**: 기존 파일 건드리지 않고 먼저 반입 결과 확인

작업:
1. ARP 익스포터로:
   - `pilot/exports/rabbit_animation.fbx`
   - `pilot/exports/Rabbit_DutchBrown.fbx` + 나머지 4 skin
2. Unity 프로젝트의 **sandbox 경로**로 복사:
   - `Assets/_Migration_Sandbox/Rabbit/` (새 폴더, 배포 제외)
3. Unity 재import 대기
4. 인스펙터 확인:
   - 각 FBX의 Avatar 생성 여부
   - clip 이름/개수 (baseline과 일치?)
   - bone hierarchy (bone 이름 전수 복사 → 비교용 텍스트)

### 1e. Diagnosis

**목적**: 파일럿에서 가장 중요한 학습 단계. Phase 2 도구화 결정의 근거 데이터.

체크 항목별 "OK" / "깨졌음: 설명" 기록 → `docs/superpowers/pilot/rabbit_diagnosis.md`

**FBX 내부 구조**
- [ ] bone 개수 (old vs new 수치 비교)
- [ ] bone 이름 매핑표 (old → new, 혹은 unchanged)
- [ ] AnimationClip 개수/이름이 baseline과 일치
- [ ] shape key (있다면) 보존

**Unity reference 보존**
- [ ] `.meta` 보존 swap 시 GUID 유지되는지
- [ ] AnimatorController m_Motion 21개 중 살아남는 개수 (fileID 매칭)
- [ ] Prefab variant override 중 Missing 개수
  - NavMeshAgent/BoxCollider/MonoBehaviour override: 유지 예상
  - Transform(본) override: 깨짐 예상 → 몇 개인가

**시각적 품질** (허용 범위 = **본 위치 수치(≤1cm) + 애니메이션 육안**)
- [ ] rest pose 동일성
- [ ] idle 재생 diff (1a 녹화 대비)
- [ ] walk/run 재생 diff
- [ ] skin binding (T-pose 안 뜸)

### 1f. 실제 교체

1. 브랜치: `migration/pilot-rabbit`
2. 기존 FBX 백업: `Assets/_Migration_Backup/Rabbit/` (`.gitignore` 추가)
3. **`.meta` 파일 유지**: 기존 `rabbit_animation.fbx.meta`는 덮어쓰지 않음, FBX만 교체
4. 각 model FBX도 동일
5. Unity 재import (`Reimport All` 또는 에디터 재시작)

### 1g. 검증 (Play mode)

1. 1a에서 녹화한 3 state(idle, walk, run) Play mode 재생
2. 육안 diff
3. Console 경고 전수 확인 (baseline 대비 새로 생긴 것만 기록)
4. 프리팹 인스펙터 Missing 마크 전수 확인

**통과 기준** (4가지 모두 충족):
- (1) Rabbit 대표 프리팹 `Animal_0` Play mode에서 idle, walk, run 3 state가 멈춤/T-pose 없이 재생된다
- (2) 1a 녹화 영상과 육안 비교 시 본 위치 오차 ≤1cm 수준, 애니메이션 어색함 없음
- (3) Unity Console에 baseline 대비 새로 추가된 Missing Transform / Missing Script / Missing Component 경고가 없다
- (4) 프리팹 variant의 Missing override 개수가 파일럿 리포트(1h)에서 명시된 수동 복구 가능 범위 이내 (Phase 2 도구화 결정 인풋)

### 1h. 파일럿 리포트

`docs/superpowers/pilot/rabbit_report.md` 섹션:
1. 소요 시간 breakdown (각 단계별)
2. 1e diagnosis 결과 요약표
3. 수작업으로 고친 항목 (타임스탬프 기록)
4. **자동화 후보 리스트** (Phase 2 인풋)
5. blend-fallback 필요 여부
6. 다음 동물(lopear)에 적용 가능한 공통 패턴

---

## Phase 2 — 도구화 결정 게이트

### 목적
파일럿 회고를 근거로 "자동화할 가치 있음 / 수작업 유지" 판단. 상상으로 도구 만들면 엉뚱한 것 만들 위험 방지.

### ROI 식

```
도구 가치 = (1마리 수작업 시간) × 20 (남은 배치 동물 수) - 도구 개발 비용
> 0 → 도구화
≤ 0 → 수작업 유지
```

### 후보 도구 (파일럿 전 추정)

| 후보 도구 | 1마리 수작업 시간 | 개발 비용 | 20마리 절감 | 판단 |
|----------|-----------------|---------|-----------|------|
| `tools/fbx_to_blend.py` | 30~60분 | 2~4시간 | 10~20시간 | ✅ **Phase 1b에서 선확정** |
| Unity prefab override 자동 재설정 Editor 스크립트 | 10~60분 | 4~8시간 | 가변적 | 파일럿 후 판단 |
| bone 이름 매핑 검증 스크립트 | 5~15분 | 2~3시간 | 절감 < 비용 | 수작업 유지 예상 |
| FBX clip diff 자동 | 5분 | 1~2시간 | 수작업에 가까움 | 수작업 유지 예상 |
| `tools/migrate_batch.py` orchestrator | orch overhead 20~30분 | 4~6시간 | 6~10시간 | 파일럿 후 판단 |

### Exit 조건

Phase 2는 다음 중 하나로 끝남:
- (a) 파일럿 성공 + 도구화 추가 불필요 → Phase 3 즉시 시작
- (b) 파일럿 성공 + N개 도구 개발 필요 → 각각 Tier 3 서브프로젝트로 분기 (spec → plan → implementation) → 완료 후 Phase 3
- (c) 파일럿 실패 (애드온이 Unity FBX 소스에서 안 돌아감) → blend-first fallback으로 재설계 (신규 브레인스토밍)

### 산출물
`docs/superpowers/pilot/phase2_decisions.md` — 각 도구 "build / skip" + 근거

---

## Phase 3 — 배치 변환 (20마리)

### 단위
1 동물 = 1 feat 브랜치 = 1 PR (`master`는 fast-forward만 허용, CLAUDE.md 워크플로 규칙)

브랜치명: `migration/animal-<id>`

### 동물별 체크리스트 (기본 틀, Phase 1 경험 반영하여 확정)

```
[ ] Phase 0 CSV에서 scope = in_scope 확인
[ ] feat 브랜치 생성: migration/animal-<id>
[ ] tools/fbx_to_blend.py --id <id> 실행
[ ] Blender에서 BlenderRigConvert 5단계 진행
[ ] ARP 익스포트 → Unity sandbox
[ ] 깨짐 진단 체크리스트 실행 (수동 또는 도구)
[ ] Sandbox 통과 시 .meta swap 교체
[ ] Play mode 검증 통과
[ ] CSV status: not_started → converted → validated → shipped
[ ] Commit + ff merge to master
```

### 동물 순서 (쉬운 것부터)

1. **lopear** — rabbit 계보, 파일럿 직후 검증
2. **fox** — `Fox_AllAni_251112_ARP.blend` 샘플 존재
3. **bear** — 샘플 존재, skin variant 적음
4. **wolf, deer, stag** — 샘플 존재
5. **baby 시리즈** (baby_rabbit, baby_fox, baby_wolf, baby_bear, baby_turtle)
6. **cat (2종), raccoon, llama, sheep** — 신규 변환
7. **hedgehog, mole, capybara, turtle** — 크기/구조 특이, 마지막

### 진행 관리
`docs/MigrationInventory.csv`의 `status` 컬럼을 매 동물마다 업데이트.

### 동물간 안정기
각 동물 merge 후 **최소 3일 + 1회 Play session 정상 확인** 전까지 다음 동물 시작 금지.

---

## Phase 4 — 마무리 정리

### 체크포인트
- [ ] 모든 in_scope 동물 `status = shipped`
- [ ] Unity Console 전역 경고 0 (baseline 대비)
- [ ] `ruff check scripts/ tests/` + `pytest tests/ -v` 모두 통과
- [ ] `docs/UserGuide.md`에 Unity 이주 플레이북 섹션 추가
- [ ] `docs/ProjectPlan.md` 이주 완료 상태 반영
- [ ] 변환된 동물의 구 blend → `Asset/Blender_archive/` 이동
- [ ] 2주 안정기 후 archive 최종 삭제 여부 재검토

### Rollback 전략

각 동물 브랜치 단위:
- **before**: 브랜치 cut 시점에 기존 FBX + `.meta`를 `Assets/_Migration_Backup/<id>/` 복사
- **after 문제 발생**: `git revert <merge_commit>` + `Assets/_Migration_Backup/<id>/` 복원 + Unity 재import

### 공개 인터페이스 변경 없음
이번 이주는 게임 코드 / 프리팹 MonoBehaviour 참조 / AnimatorController 상태머신 그래프를 건드리지 않는다. 코드 레이어 regression은 이론상 없음. 검증은 에셋 레이어에서만.

---

## 산출물 목록

### 코드
- `tools/build_migration_inventory.py` (Phase 0)
- `tools/fbx_to_blend.py` (Phase 1b, Phase 3)
- Phase 2에서 결정되는 추가 도구들 (조건부)

### 문서
- `docs/MigrationInventory.csv` — 진행 트래커
- `docs/superpowers/specs/2026-04-16-unity-migration-design.md` — 이 설계
- `docs/superpowers/pilot/rabbit_baseline.md` — Pre-change 기록
- `docs/superpowers/pilot/rabbit_diagnosis.md` — 깨짐 항목
- `docs/superpowers/pilot/rabbit_report.md` — 파일럿 최종 리포트
- `docs/superpowers/pilot/phase2_decisions.md` — 도구화 결정
- `docs/MigrationPlaybook.md` — 동물별 체크리스트 템플릿 (Phase 3 시작 시 파일럿 경험 반영)
- `docs/UserGuide.md` 업데이트 — Unity 이주 섹션 추가

### Unity 프로젝트 변경
- `Assets/5_Models/02. Animals/**/animation.fbx` 내용 교체 (`.meta` 유지)
- `Assets/5_Models/02. Animals/**/model.fbx` 내용 교체 (`.meta` 유지)
- `Assets/_Migration_Sandbox/` (임시 폴더, 배포 제외)
- `Assets/_Migration_Backup/` (`.gitignore`)

---

## 결정 요약

| 결정 | 값 | 근거 |
|------|-----|------|
| Migration 방향 | Full migration (호환성 파기 수용) | 장기적 통일 목표 우선, 이미 FBX-first 접근으로 Unity rework 최소화 |
| Source | Unity FBX primary, blend fallback | 원본 식별 리스크 소멸, 재현성 확보 |
| 파일럿 대상 | Rabbit | 기존 ARP 샘플 존재, skin variant 5개로 스트레스 테스트 |
| 범위 한정 | 사족보행 21마리만 | 애드온 `dog` 프리셋 지원 범위 |
| 접근 단위 | 1 동물 = 1 feat 브랜치 = 1 PR | `master` ff-only 워크플로 규칙 |
| 시각 diff 허용 | 본 위치 ≤1cm + 애니메이션 육안 OK | pixel-perfect 비현실, 육안만은 주관적 |
| Pre-change 기록 | idle/walk/run 3개 1분 녹화 + 메타 캡처 | 전수 녹화 과함, 대표 샘플로 충분 |
| Tool 개발 시점 | fbx_to_blend.py만 파일럿 전, 나머지는 Phase 2 게이트 이후 | 상상 기반 도구 개발 방지 |

# Fox 전체 흐름 테스트 체크리스트

> 파일: `Asset/latest_blends_by_animal/fox_AllAni_240311.blend`
> 현재 활성 라운드: Round 6 — Build Rig 검증 완료 (2026-04-13)

---

## Round 6 — Build Rig 검증 (완료, 2026-04-13)

> 목적: 리타게팅 코드 전면 삭제(2026-04-02) 후 Build Rig까지의 흐름이 정상 동작하는지 확인한다.

**.blend 파일을 새로 열고 Step 1부터 전체 흐름을 다시 실행** (Blender 재시작 권장)

### 사전 준비

- [x] **Blender 재시작** — 애드온 교체 후 캐시 영향을 줄이기 위해 새 세션에서 시작
- [x] **.blend 파일 새로 열기** — `fox_AllAni_240311.blend`
- [x] **콘솔 창 열기** — 로그 확인용

### Step 1: 분석 (Analyze)

- [x] **소스 아마추어 선택**
- [x] **"1. 분석" 버튼 클릭**
- [x] **분석 완료 메시지 확인** — Python traceback 없이 완료

### Step 2: 역할 확인 (Preview)

- [x] **Preview 아마추어 생성됨**
- [x] **역할 색상 표시 정상**
- [x] **자동 추론 결과 확인** — 추가 수정 없이 진행 가능

### Step 3: ARP 리그 생성 (Build Rig)

- [x] **"3. Build Rig" 버튼 클릭**
- [x] **ARP 리그 생성 완료**
- [x] **소스와 ARP 리그 크기 정상**
- [x] **에러 없음** — Python traceback 없음

### 결과

| 항목 | Pass / Fail | 메모 |
|------|-------------|------|
| Step 1 분석 | Pass | Python traceback 없음 |
| Step 2 역할 | Pass | 자동 추론/역할 색상 정상 |
| Step 3 Build Rig | Pass | ARP 리그 생성 및 스케일 정상 |

**발견된 이슈:**

없음

---

## 이전 기록

> 아래 Round 1~5는 리타게팅 삭제 전 기록이다. 참고용으로 보관한다.

### Round 5 — FBX clean armature 전환 검증 (미실행, F10 삭제로 무효)

Round 5는 F10 경로(FBX clean armature 리타게팅) 검증 계획이었으나, 2026-04-02에 리타게팅 코드가 전면 삭제되어 무효 처리되었다.

### Round 2 — 수정 검증 (2026-03-30)

> Fix 1: tail/spine/ear 다중 본 매핑 누락 수정
> Fix 2: auto_scale 소스 스케일 변형 방지

- [V] **tail 전체 매핑** — `bones_map_v2`에 tail 본 4개가 모두 표시됨
- [V] **spine 전체 매핑** — spine 본 3개가 프리뷰와 동일한 순서로 매핑됨
- [V] **ear 매핑** — ear L/R 각 2본이 매핑됨
- [V] **소스 아마추어 스케일 유지**
- [x] **다리 움직임 자연스러움**
- [x] **전체 애니메이션 품질**

### Round 1 결과 요약 (2026-03-30)

| 단계 | 결과 | 비고 |
|------|------|------|
| Step 1 분석 | Pass | |
| Step 2 역할 | Pass | |
| Step 3 Build Rig | Pass | |

### 전환 근거 — Preview bake 실험 기록

Round 3~4(2026-03-30)에서 Preview bake 경로 실험 후 품질 부족으로 폐기했다.
이후 F10(FBX clean armature) 방향으로 전환했으나, 복잡성 문제로 2026-04-02에 전면 삭제.

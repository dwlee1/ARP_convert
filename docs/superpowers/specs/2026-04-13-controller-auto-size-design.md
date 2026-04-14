# ARP 컨트롤러 자동 크기 보정 설계

> 작성일: 2026-04-13
> 상태: 사용자 승인 완료
> 연관: `docs/ProjectPlan.md`, `scripts/arp_ops_build.py`, `scripts/arp_mapping.py`, `scripts/pipeline_runner.py`, `scripts/03_batch_convert.py`

## 문제 요약

ARP 리깅 변환 결과에서 일부 컨트롤러, 특히 `foot`, `ear`, `head`,
`spine`, `neck` 계열이
캐릭터 대비 지나치게 크거나 작게 생성되는 경우가 반복된다.

현재 Build Rig 경로는 아래까지만 자동화한다.

1. Preview 역할 읽기
2. ARP ref 본 개수/위치 정렬
3. `match_to_rig`
4. custom bone 생성, weight transfer, bone_pairs 저장

즉, **컨트롤러 표시 크기를 역할별로 후처리하는 단계가 없다.**
그 결과 ARP 기본 dog 프리셋이 가진 컨트롤러 크기 편차가 동물별 비례 차이를
흡수하지 못한다.

## 목표

- `head`, `ear`, `foot`, `spine`, `neck` 계열 컨트롤러 크기를 자동으로 적정 범위에 맞춘다.
- 전체 리그 스케일이 아니라 **역할별 상대 크기**를 보정한다.
- addon / pipeline / batch 경로가 같은 규칙을 공유한다.
- 뷰포트 상태나 카메라 위치에 의존하지 않는 결정적 규칙으로 동작한다.

Non-goals:

- ARP ref 체인 개수 조정 방식 변경
- ARP preset 변경 (`dog` 고정 유지)
- 사용자 수동 슬라이더 UI를 먼저 도입하는 것
- face/custom bone 컨트롤러 전체에 대한 1차 범위 확대

## 선택한 접근

### 후보 비교

1. **개별 소스 본 길이 기준**
   - 장점: 구현이 단순하다.
   - 단점: helper 본, 비정상적으로 짧거나 긴 소스 본 길이 노이즈를 그대로 먹는다.

2. **역할 체인 길이 기준**
   - 장점: 개별 본 이상치에 덜 흔들리고 동물별 비례 차이를 안정적으로 흡수한다.
   - 단점: 개별 컨트롤러 성격 차이(예: foot IK와 toe)를 세밀하게 못 나눈다.

3. **역할 체인 길이 + 컨트롤러별 배수 + clamp**
   - 장점: 안정성과 세밀 조정을 같이 가져간다.
   - 단점: 역할별 튜닝 테이블이 필요하다.

### 결정

**3번을 채택한다.**

기본 길이는 역할 체인 길이로 잡고, 실제 컨트롤러별로 배수를 곱한 뒤
최소/최대 clamp를 적용한다.

세부 기준:

- `head`: `head` 본 길이만 사용
- `ear`: ear 체인 총길이 사용
- `foot`: foot + toe 구간 길이 사용
- `spine`: spine 체인 총길이 사용
- `neck`: neck 체인 총길이 사용

뷰포트 기준 자동 크기 맞춤은 카메라/줌/직교 상태에 따라 결과가 흔들리므로
채택하지 않는다.

## 설계

### 1. 자동 크기 계산 단계 추가

`scripts/arp_ops_build.py`의 Build Rig 파이프라인에서 `match_to_rig` 이후,
custom bone 생성 이전 또는 직후에 별도 후처리 단계 하나를 추가한다.

권장 순서:

1. `match_to_rig`
2. `apply_controller_auto_size`
3. custom bone 생성/constraint 복제
4. weight transfer
5. bone_pairs 저장

이 단계는 ARP가 생성한 pose bone/controller 이름을 기준으로 동작하므로
반드시 `match_to_rig` 이후여야 한다.

### 2. 역할 기준 길이 계산

입력 데이터:

- `roles`: Preview 역할별 본 목록
- `preview_positions`: Preview 본 world head/tail
- `arp_chains`: 역할별 ref 체인
- `ctrl_map`: `discover_arp_ctrl_map(arp_obj)` 결과

기준 길이 계산 규칙:

- `head_length`
  - `roles["head"]`의 첫 본 길이
- `spine_length`
  - `roles["spine"]` 체인 본 길이 합
- `neck_length`
  - `roles["neck"]` 체인 본 길이 합
- `ear_l_length`, `ear_r_length`
  - 각 ear 체인의 본 길이 합
- `back_foot_l/r_length`, `front_foot_l/r_length`
  - 각 foot 역할 본 길이 합
  - toe가 virtual toe로 분할된 경우에도 Preview 기준 길이 합으로 처리

보조 규칙:

- 길이가 0 또는 극소값이면 fallback 길이 사용
- 극단값은 clamp 전 단계에서도 한 번 방어 가능하게 한다

### 3. 컨트롤러 그룹 매핑

컨트롤러 이름은 이미 `discover_arp_ctrl_map()`에서 역할별로 찾는다.
이 결과를 이용해 “어떤 컨트롤러가 어떤 기준 길이를 따라야 하는지”를 정한다.

1차 범위:

- `spine`
  - spine FK/master 계열 컨트롤러
- `neck`
  - neck FK/master 계열 컨트롤러
- `head`
  - `c_head.x`
- `ear_l/r`
  - `c_ear_01`, `c_ear_02` 계열
- `back_foot_l/r`, `front_foot_l/r`
  - `c_foot_ik`, `c_foot_fk`, `c_toes`, 필요 시 `c_hand_ik` fallback 포함

다리 pole, tail은 1차 범위에서 제외한다.
spine/neck은 이번 범위에 포함하되, multiplier를 보수적으로 시작한다.

### 4. 목표 스케일 계산

공식:

`target_scale = clamp(base_length * multiplier, min_size, max_size)`

초기 multiplier 예시:

- `spine`: `0.6`
- `neck`: `0.75`
- `head`: `1.0`
- `ear`: `0.8`
- `foot_fk`: `1.0`
- `foot_ik`: `1.3`
- `toes`: `0.75`

초기 clamp 예시:

- `min_size = 0.03`
- `max_size = 0.6`

정확한 숫자는 구현 시 fixture와 실제 여우/너구리/사슴 샘플로 조정한다.
이번 설계의 핵심은 “배수 + clamp 구조”이며, 숫자는 회귀 검증을 통해 다듬는다.

### 5. 적용 방식

구현은 ARP controller pose bone의 표시 스케일 속성을 직접 수정하는 헬퍼로 묶는다.

예상 책임 분리:

- `scripts/arp_build_helpers.py` 또는 신규 헬퍼 모듈
  - 기준 길이 계산
  - 컨트롤러 그룹 분류
  - 목표 스케일 계산
- `scripts/arp_ops_build.py`
  - Build Rig 파이프라인에서 헬퍼 호출

실제 적용은 **pose bone의 `custom_shape_scale_xyz` 조정**을 기본으로 한다.
`use_custom_shape_bone_size`는 기존 값을 유지하거나 필요 시 곱연산 기준으로만
다루며, custom shape 오브젝트 자체는 수정하지 않는다.

HARD RULES:

- custom shape 오브젝트(`Object.scale`) 직접 수정 금지
- Blender `Apply Transforms` 자동 실행 금지
- Blender `Set Custom Shape...` 자동 재지정 금지
- ARP custom shape transform/override transform 체계 자동 수정 금지

이 설계는 “shape 자산 변경”이 아니라 “각 컨트롤러 본의 표시 배율 후처리”만
수행한다.

### 6. 실행 경로 일관성

자동 크기 보정은 아래 경로 모두에서 같은 헬퍼를 호출해야 한다.

- addon: `scripts/arp_ops_build.py`
- pipeline: `scripts/pipeline_runner.py`
- batch: `scripts/03_batch_convert.py`

핵심 규칙은 Build Rig 내부 공용 헬퍼에 두고,
pipeline/batch는 기존처럼 Build Rig 호출 결과를 그대로 공유하게 만든다.
별도 복제 구현은 허용하지 않는다.

재빌드 시에는 이전 수동 조정값을 보존하려 하지 않고, `match_to_rig` 직후
자동 크기 계산을 **항상 다시 적용**하는 방식으로 일관성을 유지한다.

## 에러 처리와 fallback

- 컨트롤러를 찾지 못하면 warning 로그만 남기고 계속 진행한다.
- 역할 길이 계산 실패 시 전역 기본 크기를 사용한다.
- 좌/우 한쪽만 계산 가능해도 가능한 쪽만 적용한다.
- ARP 명명 차이(`c_foot_ik` vs `c_hand_ik` fallback)는 기존 ctrl 검색 규칙을 우선 재사용한다.
- 사용자가 이전 리그에서 수동으로 custom shape 크기를 바꿨더라도, 새 Build Rig에서는
  auto-size 결과가 기준값이 된다.

이 기능은 리깅 완료를 막는 hard blocker가 아니므로, 실패 시 Build Rig 전체를 취소하지 않는다.

## 검증

Python 레벨:

1. 역할 기준 길이 계산 함수 단위 테스트
2. 컨트롤러 그룹 분류 테스트
3. multiplier/clamp 적용 테스트
4. 적용 대상이 `custom_shape_scale_xyz`만 수정하고 금지된 경로를 사용하지 않는지 검증

저장소 기본 검증:

1. `pytest tests/ -v`
2. `ruff check scripts/ tests/`

Blender 수동 검증:

1. 여우 샘플: spine/neck/head/ear/foot 컨트롤러 육안 크기 확인
2. 너구리 샘플: 앞발/뒷발 IK 및 neck 컨트롤러 과대 여부 확인
3. 사슴 샘플: 긴 귀 체인, 긴 neck 체인, 앞발 hand/toe 분리 케이스 확인
4. 같은 소스에서 Build Rig를 두 번 연속 실행해도 컨트롤러 크기가 결정적으로 재적용되는지 확인

검증 기준:

- `spine`은 몸통 조작이 쉽되 갈비/허리 영역을 과도하게 덮지 않을 것
- `neck`은 목 조작이 쉽되 head 컨트롤러와 시각적으로 과하게 겹치지 않을 것
- `head`는 머리 크기를 가리지 않을 것
- `ear`는 귀 체인보다 과도하게 커 보이지 않을 것
- `foot IK`는 발 끝 조작이 쉬우면서 몸통 절반 이상을 덮지 않을 것

## 위험과 대응

- **Blender API 차이**
  - `custom_shape_scale_xyz`가 ARP dog 프리셋 주요 컨트롤러에 일관되게 먹는지 확인이 필요하다.
  - 구현 시작 전에 최소 범위 Blender 실험으로 적용 가능 본군을 확정한다.

- **재빌드 시 수동값 소실**
  - Build Rig는 새 ARP 리그를 만들기 때문에 과거 수동 편집을 보존하지 않는다.
  - 설계상 의도된 동작이며, auto-size를 `match_to_rig` 직후 항상 재적용해 해결한다.

- **ARP 프리셋 이름 변형**
  - `discover_arp_ctrl_map()` 결과를 재사용해 하드코딩 범위를 줄인다.

- **과보정**
  - multiplier와 clamp를 분리해 튜닝한다.
  - `spine/neck`은 여러 컨트롤러가 분산되므로 낮은 초기 배수로 시작한다.

- **경로 분기**
  - 공용 헬퍼를 만들고 Build Rig 중심으로 호출해 addon/pipeline/batch 차이를 줄인다.

## 구현 범위 밖

- tail/pole 컨트롤러 자동 크기 보정
- UI에서 역할별 multiplier를 직접 편집하는 기능
- custom bone 컨트롤러(shape key driver bone 포함)의 개별 자동 크기 정책
- face rig 재도입 시의 facial controller 크기 규칙

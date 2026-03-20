# BlenderRigConvert 통합 문서

> 최종 수정: 2026-03-20

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
1. 소스 deform 본 분석
2. Preview Armature 생성
3. 역할 수정
4. ARP 리그 생성
5. match_to_rig
6. Remap 설정
7. 액션별 retarget
```

### 현재 상태 요약

- [x] Preview 기반 변환 흐름이 현재 메인 경로다
- [x] ARP 프리셋은 `dog`로 고정한다
- [x] 다리 `leg` 3본 매핑과 `foot` 분할 규칙은 반영되었다
- [x] Preview 가이드, `virtual neck`, `virtual toe`, `cc_` 커스텀 본 생성이 구현되었다
- [ ] spine / neck / tail / ear 체인 개수 매칭은 아직 미구현이다
- [ ] `.bmap` 규칙은 핵심 분리 규칙 반영까지 되었고 실제 리타게팅 검증이 더 필요하다
- [ ] bank / heel 자동 배치 보정은 기본 케이스만 반영되었고 비율 검증이 더 필요하다
- [ ] 소스 컨스트레인트 복제는 일부 타입만 부분 구현된 상태다

## 저장소 점검 체크리스트

### 구조

- [x] 핵심 코드가 `scripts/`에 모여 있다
- [x] 기획 및 작업 문서는 `docs/`에 있다
- [x] 프로필 자산은 `mapping_profiles/`, `remap_presets/`에 있다
- [x] 일반적인 Python 패키지 구조는 아니다
- [ ] 자동 테스트 디렉터리나 테스트 스위트는 없다

### 현재 기준 진입점

- [x] 구조 분석과 Preview 생성 핵심 로직은 `scripts/skeleton_analyzer.py`
- [x] UI와 BuildRig / Retarget 진입점은 `scripts/arp_convert_addon.py`
- [x] Blender / ARP 공통 유틸은 `scripts/arp_utils.py`
- [x] 비대화형 단일 실행 경로는 `scripts/pipeline_runner.py`
- [x] 전체 배치 실행 경로는 `scripts/03_batch_convert.py`
- [ ] 구형 또는 병행 경로가 남아 있어 로직 드리프트 위험이 있다

### 운영 리스크

- [ ] Windows 경로와 Blender 설치 경로에 대한 가정이 코드에 남아 있다
- [ ] ARP operator 실행이 3D Viewport 컨텍스트에 의존한다
- [ ] 자동 테스트가 없어 회귀 확인이 수동 검증 중심이다
- [ ] 실행 경로가 여러 갈래라 수정 시 동기화 누락 위험이 있다

## 핵심 규칙

- ARP 프리셋은 `dog` 고정
- ARP ref 본은 실제 리그에서 동적 탐색
- `leg` 역할 본이 3개면 ARP도 3본 다리 체인으로 적용
- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할
- toe 본이 없으면 `virtual toe` 사용
- ear는 `ear_01_ref / ear_02_ref`에 직접 매핑
- face는 `cc_` 커스텀 본 후보
- Preview Armature는 원본 이름 유지, 역할은 색상과 커스텀 프로퍼티로 표시

## 진행 원칙

- 별도 진단 스크립트 단계를 기본 전제로 두지 않음
- `F5`, `F7`, `F6`, `F2`는 코드 읽기와 직접 구현으로 진행
- `F1`처럼 ARP 내부 동작 확인이 꼭 필요한 경우에만 최소 범위 실험 추가

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
| `face` | `cc_` 커스텀 본 후보 |
| `unmapped` | 미매핑 |

## ARP ref 체인 규칙

### 뒷다리

- `back_leg_l/r`
  - `thigh_b_ref`
  - `thigh_ref`
  - `leg_ref`
- `back_foot_l/r`
  - `foot_ref`
  - `toes_ref`

### 앞다리

- `front_leg_l/r`
  - `thigh_b_ref_dupli_001`
  - `thigh_ref_dupli_001`
  - `leg_ref_dupli_001`
- `front_foot_l/r`
  - `foot_ref_dupli_001`
  - `toes_ref_dupli_001`

### 기타

- `ear_l/r`
  - `ear_01_ref`
  - `ear_02_ref`
- `tail`
  - `tail_00_ref`부터 순차 체인

## 매핑 규칙

### `leg` 역할

- `leg` 역할 본이 3개면 ARP도 3본으로 매핑한다
- 예시
  - `thigh_L -> thigh_b_ref.l`
  - `leg_L -> thigh_ref.l`
  - `foot_L -> leg_ref.l`

### `foot` 역할

- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- `foot` 역할 본이 1개면 다음처럼 분할
  - `foot_ref.head = source_foot.head`
  - `foot_ref.tail = toes_ref.head = source_foot` 중간 분할점
  - `toes_ref.tail = source_foot.tail`

## 구현 기준 파일

| 파일 | 역할 |
|------|------|
| `scripts/skeleton_analyzer.py` | 구조 분석, Preview 생성, ref 체인 탐색, `.bmap` 생성 |
| `scripts/arp_convert_addon.py` | Preview UI, BuildRig, Retarget |
| `scripts/arp_utils.py` | Blender / ARP 공통 유틸 |
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 |
| `scripts/01_create_arp_rig.py` | 구형 프로필 기반 리그 생성 경로 |
| `scripts/02_retarget_animation.py` | 구형 리타게팅 경로 |
| `scripts/03_batch_convert.py` | 배치 실행 |

## 구현 상태 체크리스트

### 완료

- [x] Preview Armature 생성
- [x] Preview 역할 수정 UI
- [x] `root/spine/neck/head/leg/foot/ear/face/unmapped` 역할 체계 반영
- [x] ARP ref 본 동적 검색
- [x] `leg` 3본 고정 매핑
- [x] `foot` 1본을 `foot + toe`로 분할
- [x] toe가 없을 때 `virtual toe` 생성
- [x] `foot` 역할 지정 시 bank / heel Preview 가이드 생성
- [x] Preview 생성 시 `__virtual_neck__` 자동 생성
- [x] `face` 역할 본을 `cc_<source>` 본으로 생성
- [x] 가이드 본을 제외한 `unmapped` 본을 `cc_<source>`로 생성

### 부분 완료

- [ ] 소스 컨스트레인트 복제
  - 현재는 `face` / `unmapped`에서 생성된 custom bone에 대해서만 일부 constraint 타입 지원
- [ ] bank / heel 자동 오프셋 보정
  - 현재는 기본 위치 그대로인 가이드만 foot 방향 기준으로 자동 보정
- [ ] BuildRig와 Remap `.bmap` 규칙 정리
  - 현재는 `leg/foot` 분리 규칙과 `ear_l/r` 매핑이 반영되었지만 실제 결과 검증이 더 필요

### 미구현

- [ ] spine / neck / tail / ear 본 개수를 소스 체인에 맞춰 조정

## 남은 기능 상세

### F1. spine / neck / tail / ear 본 개수 매칭

#### 문제

- 현재는 ARP `dog` 프리셋 기본 개수에 맞춘 상태로 `match_to_rig()`를 사용한다
- 소스 spine, neck, tail, ear 개수가 달라도 ref 본 개수 자체는 조정하지 않는다

#### 목표

- `spine`, `neck`, `tail`, `ear_l`, `ear_r` 역할에 대해 소스 개수에 맞춰 ref 본 개수 조정
- 실패 시 fallback 규칙 정의

#### 완료 기준 체크리스트

- [ ] spine 체인이 소스 개수 기준으로 조정된다
- [ ] neck 체인이 소스 개수 기준으로 조정된다
- [ ] tail 체인이 소스 개수 기준으로 조정된다
- [ ] `ear_l`, `ear_r` 체인이 각각 소스 개수 기준으로 조정된다
- [ ] 조정 실패 시 fallback 규칙이 로그와 함께 동작한다
- [ ] 기본 `dog` 프리셋만 사용하는 케이스와 충돌하지 않는다

### F4. 소스 컨스트레인트 복제

#### 문제

- `cc_` 본을 만들더라도 소스 본의 제약 조건은 전부 따라오지 않는다

#### 목표

- 자주 쓰는 constraint만 먼저 안정적으로 복제
- target 본 이름은 ARP 본 이름으로 변환

#### 우선 지원 후보

- `COPY_ROTATION`
- `COPY_LOCATION`
- `COPY_SCALE`
- `DAMPED_TRACK`
- `LIMIT_ROTATION`

#### 현재 상태

- `face` / `unmapped` custom bone 대상에 한해 일부 constraint 복제
- target이 소스 아마추어면 ARP 아마추어로 교체
- 세부 옵션과 추가 constraint 타입은 후속 정리 필요

#### 완료 기준 체크리스트

- [ ] 지원 대상 constraint 타입이 명확히 문서화된다
- [ ] 지원 타입이 `cc_` 본에 안정적으로 복제된다
- [ ] target armature가 소스에서 ARP armature로 치환된다
- [ ] bone target 이름이 ARP 이름 체계로 안전하게 변환된다
- [ ] 미지원 constraint는 에러 없이 건너뛰고 로그를 남긴다

### F6. bank / heel 자동 배치 보정

#### 문제

- 현재 bank / heel은 Preview 가이드 위치를 그대로 ref에 복사한다
- 사용자가 가이드를 안 만졌을 때 기본 오프셋 정확도가 낮을 수 있다

#### 목표

- ARP 원본 foot / toe 비율 또는 toes tail 기준 오프셋으로 자동 보정
- 수동 가이드 위치와 충돌하지 않도록 우선순위 규칙 정의

#### 현재 상태

- 기본 위치 그대로인 heel / bank 가이드는 foot 방향 기준 자동 보정 적용
- 사용자가 이동한 가이드는 기존 위치를 유지
- 실제 Blender 결과 기준 비율 조정은 추가 검증 필요

#### 완료 기준 체크리스트

- [ ] 기본 위치 가이드는 자동 보정이 적용된다
- [ ] 사용자가 이동한 가이드는 덮어쓰지 않는다
- [ ] left / right, front / back foot에서 같은 규칙으로 동작한다
- [ ] foot / toe 길이 비율이 다른 리그에서도 크게 틀어지지 않는다
- [ ] 보정 전후 기준이 로그 또는 코드 상수로 분명하다

### F7. Remap `.bmap` 규칙 정리

#### 문제

- BuildRig는 `leg`와 `foot`를 분리해 쓰지만 Remap `.bmap` 생성은 아직 이 규칙과 완전히 같다고 보기 어렵다

#### 목표

- `back_leg/front_leg`와 `back_foot/front_foot` 역할이 BuildRig와 같은 의미로 Remap에서도 동작
- toe 없음 / `virtual toe` 케이스도 일관되게 처리

#### 현재 상태

- `back_leg/front_leg`와 `back_foot/front_foot` 컨트롤 매핑 분리는 반영됨
- `ear_l/r`도 `.bmap` 컨트롤 매핑에 포함됨
- 실제 Blender 리타게팅 결과 검증은 아직 필요

#### 완료 기준 체크리스트

- [ ] BuildRig의 역할 분리 규칙과 `.bmap` 생성 규칙이 동일하다
- [ ] `back_leg` / `front_leg` 매핑이 각각 올바른 컨트롤로 연결된다
- [ ] `back_foot` / `front_foot` 매핑이 각각 올바른 컨트롤로 연결된다
- [ ] toe가 없는 경우에도 `virtual toe` 규칙이 일관되게 적용된다
- [ ] `ear_l/r` 매핑이 실제 리타게팅에서도 유지된다
- [ ] 실제 액션 리타게팅 결과로 최종 검증한다

## 우선순위

1. F7: Remap `.bmap` 규칙 정리
2. F6: bank / heel 자동 배치 보정
3. F4: 소스 컨스트레인트 복제
4. F1: spine / neck / tail / ear 본 개수 매칭

## 현재 한계

- spine / neck / tail / ear는 소스 개수에 맞춰 ref 개수를 조절하지 않음
- `.bmap` 규칙은 핵심 분리 규칙 반영 완료, 실제 리타게팅 검증 추가 필요
- 자동 테스트가 없어 실제 `.blend` 기준 검증 비중이 큼
- Windows / Blender 경로 가정이 일부 남아 있음

## 검증 체크리스트

### BuildRig

- [ ] Fox: 뒷다리 `leg` 3본 + `foot` 1본으로 BuildRig 시 `thigh_b_ref -> thigh_ref -> leg_ref`, `foot_ref -> toes_ref` 확인
- [ ] Fox: 앞다리 `leg` 3본 + `foot` 1본으로 BuildRig 시 `_dupli_001` 체인 확인
- [ ] toe 없는 리그에서 로그에 `virtual toe tail 설정` 출력 확인
- [ ] ear 체인에서 `ear_01_ref -> ear_02_ref` 정렬 확인
- [ ] bank / heel 가이드를 안 움직인 경우 자동 보정 결과 확인
- [ ] bank / heel 가이드를 수동 이동한 경우 위치 유지 확인

### Remap / Retarget

- [ ] BuildRig와 `.bmap` 역할 규칙이 동일한지 확인
- [ ] `back_leg/front_leg`와 `back_foot/front_foot`가 기대 컨트롤에 연결되는지 확인
- [ ] toe 없음 / `virtual toe` 케이스에서도 리타게팅이 깨지지 않는지 확인
- [ ] `ear_l/r`가 실제 리타게팅에서도 반영되는지 확인

### 운영 / 유지보수

- [ ] 수정한 로직이 addon 경로와 batch 경로에서 모두 동일하게 반영되는지 확인
- [ ] Windows 경로 가정 코드가 필요한지 재검토
- [ ] 최소 1개 샘플 `.blend`에 대해 회귀 검증 로그를 남길 것

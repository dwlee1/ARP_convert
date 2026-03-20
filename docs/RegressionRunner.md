# Preview 회귀 테스트 러너

> GUI Blender 세션용 테스트 문서

## 목적

이 문서는 Preview 기반 ARP 변환 흐름을 반복 테스트하기 위한 회귀 테스트 러너 사용법을 설명한다.

러너는 아래 순서를 한 번에 실행한다.

1. 소스 아마추어 분석
2. Preview Armature 생성
3. Fixture JSON으로 역할 적용
4. bank / heel 가이드 생성
5. BuildRig 실행
6. 선택적으로 Retarget 실행
7. JSON 리포트 저장

## 현재 제약

- 이 러너는 Blender GUI 세션 기준이다
- 현재 ARP operator 실행은 `VIEW_3D` 컨텍스트를 요구하므로 `--background` 완전 무인 실행은 보장하지 않는다
- 따라서 회귀 테스트는 Blender를 연 상태에서 `ARP Convert` 패널의 `Regression` 섹션으로 실행한다

## 위치

- 메인 구현: `scripts/arp_convert_addon.py`
- 패널 위치: `View3D > Sidebar > ARP Convert > Regression`
- 예제 fixture: `regression_fixtures/example_roles.json`

## Fixture 형식

Fixture는 JSON 파일이며 기본 구조는 아래와 같다.

```json
{
  "description": "Fox preview regression example",
  "apply_mode": "replace",
  "run_retarget": true,
  "roles": {
    "root": ["root"],
    "spine": ["spine01", "spine02", "chest"],
    "neck": ["neck"],
    "head": ["head"],
    "back_leg_l": ["thigh_L", "leg_L", "foot_L"],
    "back_foot_l": ["toe_L"],
    "back_leg_r": ["thigh_R", "leg_R", "foot_R"],
    "back_foot_r": ["toe_R"],
    "ear_l": ["ear01_L", "ear02_L"],
    "ear_r": ["ear01_R", "ear02_R"],
    "face": ["eye_L", "eye_R", "jaw"]
  }
}
```

## 필드 설명

- `description`
  - 선택 항목
- `apply_mode`
  - `replace`: Preview의 기존 역할을 전부 `unmapped`로 초기화한 뒤 fixture 역할을 적용
  - `overlay`: 기존 Preview 역할 위에 fixture 역할만 덮어씀
- `run_retarget`
  - fixture가 retarget까지 요구하는지 표시
  - 패널의 `Retarget 포함` 옵션과 둘 다 `true`일 때만 실제 retarget 실행
- `roles`
  - key는 Preview 역할 이름
  - value는 해당 역할로 지정할 Preview 본 이름 리스트

## 역할 이름 규칙

지원 역할은 현재 아래 범위다.

- `root`
- `spine`
- `neck`
- `head`
- `back_leg_l`
- `back_leg_r`
- `back_foot_l`
- `back_foot_r`
- `front_leg_l`
- `front_leg_r`
- `front_foot_l`
- `front_foot_r`
- `tail`
- `ear_l`
- `ear_r`
- `face`
- `unmapped`

## 본 이름 기준

- fixture의 본 이름은 Preview 본 이름 기준으로 작성한다
- Preview는 기본적으로 원본 본 이름을 유지하므로 보통 소스 본 이름을 그대로 사용하면 된다
- 자동 생성되는 `__virtual_neck__` 같은 본도 필요하면 fixture에 직접 넣을 수 있다

## foot 역할 주의사항

- `back_foot_*`, `front_foot_*` 역할은 적용 시 bank / heel 가이드를 자동 생성한다
- fixture에는 guide 본 이름을 직접 넣지 않는다
- guide 본은 러너가 자동 생성하고 guide 역할도 자동 부여한다

## 실행 방법

1. Blender에서 대상 `.blend`를 연다
2. `ARP Convert` 패널을 연다
3. `Regression > Fixture`에 JSON 파일 경로를 넣는다
4. 필요하면 `Report Dir`를 지정한다
5. `Retarget 포함` 여부를 고른다
6. `회귀 테스트 실행` 버튼을 누른다

## 리포트

- 기본 저장 위치: `regression_reports/`
- 파일명 형식: `<blend_name>_<timestamp>.json`

리포트에는 최소한 아래 내용이 기록된다.

- fixture 경로
- source / preview armature 이름
- BuildRig 성공 여부
- Retarget 성공 여부
- 역할 적용 개수
- 생성된 guide 개수
- fixture에서 찾지 못한 본 목록
- 중복 역할 지정 본 목록
- 실행 시간

## 권장 사용 방식

- 리그별로 fixture JSON을 하나씩 만든다
- 샘플 `.blend`와 fixture를 짝으로 유지한다
- F7, F6 같은 리그 생성 규칙 변경 후 같은 fixture를 다시 돌려 회귀 여부를 본다
- 결과 확인은 JSON 리포트와 Blender 결과를 함께 본다

## Claude / Codex 작업 원칙

- 회귀 테스트 자동화 관련 변경은 `scripts/arp_convert_addon.py`와 이 문서를 함께 본다
- fixture 형식 변경 시 `docs/RegressionRunner.md`를 같이 수정한다
- 이 러너는 GUI 세션 기준이므로 headless CI 경로와 혼동하지 않는다

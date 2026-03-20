# BlenderRigConvert

## 프로젝트 목표

동물 캐릭터 리그를 Auto-Rig Pro 기반으로 통일하고, 리그 생성과 애니메이션 리타게팅을 자동화한다.

## 환경

- Blender 4.5 LTS
- Auto-Rig Pro

## 기준 문서

- 단일 기준 문서: `docs/ProjectPlan.md`
- 회귀 테스트 문서: `docs/RegressionRunner.md`
- 상세 구현 상태, 남은 기능, 검증 체크리스트 판단은 항상 `docs/ProjectPlan.md`를 우선 기준으로 삼는다
- 기존 `docs/AutoMappingPlan.md`, `docs/ConversionPlan.md`, `docs/FeaturePlan_v3.md`는 참고 이력 문서로만 취급한다

## 현재 메인 구현 경로

- 현재 메인 흐름은 Preview 기반 addon 경로다
- 기준 파이프라인:
  1. 소스 deform 본 분석
  2. Preview Armature 생성
  3. 역할 수정
  4. ARP 리그 생성
  5. `match_to_rig`
  6. Remap 설정
  7. 액션별 retarget

## 우선 확인할 파일

- `scripts/skeleton_analyzer.py`
  - 구조 분석
  - Preview Armature 생성
  - ARP ref 체인 탐색
  - `.bmap` 생성
- `scripts/arp_convert_addon.py`
  - Preview UI
  - BuildRig
  - Retarget
- `scripts/arp_utils.py`
  - Blender / ARP 공통 유틸
- `scripts/pipeline_runner.py`
  - 비대화형 단일 실행 경로
- `scripts/03_batch_convert.py`
  - 배치 실행 경로
- `scripts/arp_convert_addon.py`
  - Regression 패널과 fixture 기반 회귀 테스트 오퍼레이터 포함

## 레거시 또는 병행 경로

- `scripts/01_create_arp_rig.py`
- `scripts/02_retarget_animation.py`
- `scripts/rigify_to_arp.py`

위 파일들은 참고 경로일 수 있으므로, 먼저 현재 메인 구현 경로와 실제 사용 여부를 확인한 뒤 수정한다.

## 핵심 규칙

- ARP 프리셋은 `dog` 고정
- ARP ref 본은 실제 리그에서 동적 탐색
- `leg` 역할 본이 3개면 ARP도 3본 다리 체인으로 적용
- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할
- toe 본이 없으면 `virtual toe` 사용
- ear는 `ear_01_ref / ear_02_ref`에 직접 매핑
- face와 가이드 제외 `unmapped` 본은 `cc_` 커스텀 본 후보
- Preview Armature는 원본 이름 유지, 역할은 색상과 커스텀 프로퍼티로 표시

## 현재 상태 요약

- Preview 기반 변환 흐름이 현재 메인 경로다
- `leg` 3본 매핑, `foot` 분할, `virtual neck`, `virtual toe`, `cc_` 본 생성은 반영된 상태다
- spine / neck / tail / ear 본 개수 자동 조절은 아직 미구현이다
- bank / heel 자동 오프셋 보정은 부분 완료 상태다
- BuildRig와 Remap `.bmap` 규칙은 핵심 분리 규칙 반영 후 실제 리타게팅 검증이 더 필요하다
- 소스 컨스트레인트 복제는 일부 타입만 부분 구현 상태다

## 작업 원칙

- 별도 진단 스크립트 단계를 기본 경로로 가정하지 않는다
- 우선순위 기능은 현재 메인 구현 경로를 직접 읽고 수정한다
- ARP 내부 동작 확인이 꼭 필요한 항목만 최소 범위 실험으로 검증한다
- 자동 테스트가 없으므로 변경 후 `.blend` 기준 검증 항목까지 함께 확인한다
- 실행 경로가 여러 갈래이므로 한 경로만 고치고 끝내지 않는다

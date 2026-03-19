# BlenderRigConvert

## 프로젝트 목표

동물 캐릭터 리그를 Auto-Rig Pro 기반으로 통일하고, 리그 생성과 애니메이션 리타게팅을 자동화한다.

## 환경

- Blender 4.5 LTS
- Auto-Rig Pro

## 현재 기준 문서

- 구조 기반 매핑: `docs/AutoMappingPlan.md`
- 변환 파이프라인: `docs/ConversionPlan.md`
- 남은 기능 계획: `docs/FeaturePlan_v3.md`

## 핵심 규칙

- ARP 프리셋은 `dog` 고정
- ARP ref 본은 실제 리그에서 동적 탐색
- `leg` 역할 본이 3개면 ARP도 3본 다리 체인으로 적용
- `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할 생성
- toe 본이 없으면 `virtual toe` 사용
- ear는 `ear_01_ref / ear_02_ref`에 직접 매핑
- face는 cc_ 커스텀 본 후보

## 주요 파일

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
  - 공통 Blender / ARP 유틸

## 현재 한계

- spine / neck / tail / ear 본 개수 자동 조절 미구현
- `unmapped` 본 cc_ 전환 미구현
- cc_ 본 생성 안정화 필요
- bank / heel 자동 오프셋 보정 미구현
- BuildRig와 Remap `.bmap` 규칙 추가 정리 필요

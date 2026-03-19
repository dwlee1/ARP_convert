# ARP 리그 변환 계획

> 최종 수정: 2026-03-19

## 목표

소스 리그를 Auto-Rig Pro(`dog` preset) 기반 리그로 변환하고, 이후 Remap 리타게팅까지 자동화한다.

## 현재 파이프라인

```text
Preview 생성/수정
-> ARP 리그 생성
-> match_to_rig
-> Remap 설정
-> 액션별 retarget
```

## BuildRig 기준 규칙

### leg / foot

- `leg` 역할 본이 3개면 ARP도 3본으로 적용
  - 뒷다리: `thigh_b_ref -> thigh_ref -> leg_ref`
  - 앞다리: `thigh_b_ref_dupli_001 -> thigh_ref_dupli_001 -> leg_ref_dupli_001`
- `foot` 역할 본이 2개면 `foot_ref -> toes_ref`에 1:1 매핑
- `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할
  - toe 본이 없으면 `virtual toe`

### 예시

| 역할 | 소스 본 | ARP ref |
|------|---------|---------|
| back_leg_l | `thigh_L` | `thigh_b_ref.l` |
| back_leg_l | `leg_L` | `thigh_ref.l` |
| back_leg_l | `foot_L` | `leg_ref.l` |
| back_foot_l | `toe_L` 또는 virtual toe 시작 | `foot_ref.l` |
| back_foot_l | `toe tip` 또는 virtual toe 끝 | `toes_ref.l` |
| front_leg_l | `shoulder_L` | `thigh_b_ref_dupli_001.l` |
| front_leg_l | `upperarm_L` | `thigh_ref_dupli_001.l` |
| front_leg_l | `arm_L` | `leg_ref_dupli_001.l` |
| front_foot_l | `hand_L` 또는 virtual toe 시작 | `foot_ref_dupli_001.l` |
| front_foot_l | `hand tip` 또는 virtual toe 끝 | `toes_ref_dupli_001.l` |

## 구현 기준 파일

| 파일 | 역할 |
|------|------|
| `scripts/skeleton_analyzer.py` | 구조 분석, Preview 생성, ref 체인 탐색, `.bmap` 생성 |
| `scripts/arp_convert_addon.py` | Preview UI, BuildRig, Retarget |
| `scripts/arp_utils.py` | Blender / ARP 공통 유틸 |
| `scripts/01_create_arp_rig.py` | 구형 프로필 기반 리그 생성 경로 |
| `scripts/02_retarget_animation.py` | 리타게팅 경로 |
| `scripts/03_batch_convert.py` | 배치 실행 |

## 현재 완료

- Preview Armature 기반 역할 수정 워크플로우
- ARP 실제 ref 체인 동적 탐색
- leg 3본 고정 매핑
- foot 1본 -> `foot_ref + toes_ref` 분할
- virtual toe 생성
- bank / heel Preview 가이드 생성
- ear 독립 역할 처리

## 현재 미완료

- spine / tail / ear ref 개수 동적 조절
- neck fallback 생성
- `unmapped` 본 cc_ 전환
- cc_ 본 생성 안정화
- 소스 컨스트레인트 복제
- bank / heel 자동 오프셋 보정
- BuildRig 규칙과 Remap `.bmap` 규칙 완전 일치

## 주의사항

- ARP dog 프리셋은 helper ref가 포함된 limb 체인을 가진다.
- 문서 기준 다리 3본은 `thigh_b_ref / thigh_ref / leg_ref`를 의미한다.
- `foot_ref`, `toes_ref`는 `foot` 역할로 분리해서 다룬다.
- 앞다리는 `_dupli_001` 접미사를 가진 동일 구조를 사용한다.

## 다음 문서

- 구조/역할 상세: [docs/AutoMappingPlan.md](/mnt/c/Users/manag/Desktop/BlenderRigConvert/docs/AutoMappingPlan.md)
- 남은 기능 계획: [docs/FeaturePlan_v3.md](/mnt/c/Users/manag/Desktop/BlenderRigConvert/docs/FeaturePlan_v3.md)

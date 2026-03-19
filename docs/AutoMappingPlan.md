# 구조 기반 자동 본 매핑

> 최종 수정: 2026-03-19

## Context

이름 기반 JSON 프로필만으로는 동물별 본 이름 차이를 감당하기 어렵다.
현재 파이프라인은 소스 deform 본을 Preview Armature로 복제한 뒤, 역할을 지정하고 그 역할을 기준으로 ARP ref 본에 정렬하는 방식이다.

## 확정 규칙

- ARP 프리셋은 `dog` 고정
- ARP ref 본은 **실제 리그에서 동적 탐색**
- `leg` 역할 본이 3개면 ARP도 **3본 다리 체인**으로 적용
- `foot` 역할 본이 1개면 ARP `foot_ref + toes_ref`로 **분할 생성**
- 소스 toe 본이 없으면 `virtual toe` 사용
- ear는 cc_가 아니라 `ear_01_ref / ear_02_ref`에 직접 매핑
- face는 `cc_` 커스텀 본 후보
- Preview Armature는 원본 이름 유지, 역할은 색상과 커스텀 프로퍼티로 표시

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
| `face` | cc_ 커스텀 본 후보 |
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

### leg 역할

- `leg` 역할 본이 3개면 ARP도 3본으로 매핑한다.
- 예시:
  - `thigh_L -> thigh_b_ref.l`
  - `leg_L -> thigh_ref.l`
  - `foot_L -> leg_ref.l`

### foot 역할

- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- `foot` 역할 본이 1개면 다음처럼 분할
  - `foot_ref.head = source_foot.head`
  - `foot_ref.tail = toes_ref.head = source_foot` 중간 분할점
  - `toes_ref.tail = source_foot.tail`

## 워크플로우

```text
1. 소스 deform 본 분석
2. Preview Armature 생성
3. leg / foot / ear / face 역할 검토 및 수정
4. foot 역할 지정 시 bank / heel 가이드 생성
5. ARP dog 프리셋 추가
6. ARP 실제 ref 체인 검색
7. Preview 역할 기준으로 ref 본 위치 정렬
8. toe 없음 케이스는 virtual toe 분할
9. match_to_rig 실행
```

## Bank / Heel 가이드

- `back_foot_*`, `front_foot_*` 역할 지정 시 Preview에 자동 생성
- 현재는 Preview 가이드 위치를 그대로 ARP ref에 복사
- 자동 오프셋 보정은 후속 계획 문서 참고

## 현재 한계

- spine / neck / tail / ear는 소스 개수에 맞춰 ref 개수를 조절하지 않음
- `face` 외 `unmapped` 본은 자동 cc_ 생성 대상이 아님
- Remap `.bmap` 규칙은 BuildRig 규칙과 추가 정렬 필요

## 참고

- 구현 기준: [scripts/skeleton_analyzer.py](/mnt/c/Users/manag/Desktop/BlenderRigConvert/scripts/skeleton_analyzer.py)
- 적용 기준: [scripts/arp_convert_addon.py](/mnt/c/Users/manag/Desktop/BlenderRigConvert/scripts/arp_convert_addon.py)
- 후속 계획: [docs/FeaturePlan_v3.md](/mnt/c/Users/manag/Desktop/BlenderRigConvert/docs/FeaturePlan_v3.md)

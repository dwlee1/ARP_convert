# ARP 변환 파이프라인 기능 계획 v3

> 최종 수정: 2026-03-19

## Context

최근 BuildRig 쪽 핵심 정리는 끝났다.

- ARP ref 본은 실제 리그에서 **동적 탐색**
- 사족보행 다리는 **leg 역할 3본 고정**
- `foot` 역할이 1본이면 `foot_ref + toes_ref`로 **virtual toe 분할**
- ARP limb helper ref(`thigh_ref` 등)도 포함해 위치 정렬

이 문서는 현재 구현 이후에 남은 기능만 관리한다.

## 현재 구현 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| Preview Armature 생성 + 역할 수정 UI | 완료 | `root/spine/neck/head/leg/foot/ear/face/unmapped` |
| ARP ref 본 동적 검색 | 완료 | 실제 `thigh_b_ref → thigh_ref → leg_ref → foot_ref → toes_ref` 체인 기준 |
| leg 3본 고정 매핑 | 완료 | `leg` 역할 본 3개면 ARP도 3본 다리 체인 |
| foot 1본 → foot+toe 분할 | 완료 | toe 본이 없으면 virtual toe 생성 |
| bank/heel Preview 가이드 생성 | 완료 | `foot` 역할 지정 시 자동 생성 |
| 얼굴 `face` 본 cc_ 추가 시도 | 부분 완료 | 현재는 `bpy.ops.arp.add_custom_bone` 직접 호출 방식 유지 |
| spine/tail/ear 본 개수 조절 | 미구현 | ARP 기본 개수 유지 |
| virtual neck 생성 | 미구현 | neck 역할 미검출 시 fallback 없음 |
| `unmapped` 본 cc_ 전환 | 미구현 | 현재는 무시 |
| 소스 컨스트레인트 복제 | 미구현 | cc_ 본 생성 이후 후속 작업 필요 |
| bank/heel 자동 오프셋 보정 | 미구현 | 현재는 Preview 가이드 위치 의존 |
| foot 분리 기준 `.bmap` 동적 생성 정리 | 미구현 | BuildRig 규칙과 Remap 규칙을 완전히 맞춰야 함 |

## 남은 기능

### F1. spine / tail / ear 본 개수 매칭

문제:
- 현재 ARP dog 프리셋 기본 개수에 맞춘 상태로 `match_to_rig()`를 사용
- 소스 spine, tail, ear 개수가 더 적거나 많아도 ref 본 개수 자체는 조정하지 않음

목표:
- `spine`, `tail`, `ear_l`, `ear_r` 역할에 대해 소스 개수에 맞춰 ref 본 개수 조정
- 실패 시 fallback 규칙 필요

후보 방식:
- ref 본 삭제/추가 후 `match_to_rig()` 검증
- 위험하면 여분 ref를 parent 위치에 겹쳐 두는 fallback

관련 파일:
- `scripts/arp_convert_addon.py`
- 필요 시 진단 스크립트 별도 추가

### F2. neck fallback

문제:
- 구조 분석에서 neck 역할이 명확히 분리되지 않으면 neck 체인이 비게 됨

목표:
- `head`는 있는데 `neck`이 없을 때 virtual neck 생성
- Preview에도 그대로 반영

후보 방식:
- 마지막 spine 본과 head 사이 보간점에 `__virtual_neck__` 생성

관련 파일:
- `scripts/skeleton_analyzer.py`

### F3. unmapped 본 → cc_ 커스텀 본

문제:
- 현재 `face` 역할만 cc_ 생성 대상으로 취급
- `unmapped`는 결과적으로 변환에서 제외됨

목표:
- `unmapped` 중 가이드 본을 제외한 나머지도 선택적으로 cc_ 본으로 생성

관련 파일:
- `scripts/arp_convert_addon.py`
- `scripts/skeleton_analyzer.py`

### F4. 소스 컨스트레인트 복제

문제:
- cc_ 본을 만들더라도 소스 본의 제약 조건은 따라오지 않음

목표:
- 최소한 자주 쓰는 컨스트레인트만 복제
- 타겟 본 이름은 ARP 본 이름으로 변환

우선 지원 후보:
- `COPY_ROTATION`
- `COPY_LOCATION`
- `COPY_SCALE`
- `DAMPED_TRACK`
- `LIMIT_ROTATION`

관련 파일:
- `scripts/arp_convert_addon.py`

### F5. cc_ 커스텀 본 생성 안정화

문제:
- 현재 `bpy.ops.arp.add_custom_bone`는 파라미터 없이 단순 호출
- 컨텍스트에 따라 실패 가능

목표:
- 정확한 호출 컨텍스트 정리
- 불안정하면 Edit Mode 직접 생성 fallback 추가

관련 파일:
- `scripts/arp_convert_addon.py`

### F6. bank / heel 자동 배치 보정

문제:
- 현재 bank/heel은 Preview 가이드 위치를 그대로 ref에 복사
- 사용자가 가이드를 안 만지면 기본 오프셋 정확도가 낮을 수 있음

목표:
- ARP 원본 foot / toe 비율이나 toes tail 기준 오프셋을 사용한 자동 보정
- 수동 가이드 위치와 충돌하지 않도록 우선순위 규칙 필요

관련 파일:
- `scripts/arp_convert_addon.py`

### F7. Remap `.bmap` 규칙 정리

문제:
- BuildRig는 `leg`와 `foot`를 분리해 쓰지만, Remap `.bmap` 생성은 아직 이 규칙과 완전히 맞지 않음

목표:
- `back_leg/front_leg`와 `back_foot/front_foot` 역할이 BuildRig와 같은 의미로 Remap에서도 동작
- toe 없음 / virtual toe 케이스도 일관되게 처리

관련 파일:
- `scripts/skeleton_analyzer.py`
- `scripts/arp_convert_addon.py`

## 우선순위

1. F5: cc_ 커스텀 본 생성 안정화
2. F7: Remap `.bmap` 규칙 정리
3. F6: bank / heel 자동 배치 보정
4. F2: neck fallback
5. F3: unmapped 본 cc_ 전환
6. F4: 컨스트레인트 복제
7. F1: spine / tail / ear 본 개수 매칭

## BuildRig 현재 흐름

```text
1. Preview 역할 읽기
2. append_arp(dog)
3. ARP ref 체인 동적 탐색
4. leg 역할은 3본 체인으로 매핑
5. foot 역할은 foot/toes 체인으로 매핑
6. toe 본이 없으면 virtual toe 분할
7. helper ref 포함 위치 정렬
8. match_to_rig
9. face 역할 cc_ 본 생성 시도
```

## 검증 체크리스트

1. Fox: 뒷다리 `leg` 3본 + `foot` 1본으로 BuildRig → `thigh_b_ref → thigh_ref → leg_ref`, `foot_ref → toes_ref` 확인
2. Fox: 앞다리 `leg` 3본 + `foot` 1본으로 BuildRig → `_dupli_001` 체인 확인
3. toe 없는 리그: 로그에 `virtual toe tail 설정` 출력 확인
4. ear 체인: `ear_01_ref → ear_02_ref` 정렬 확인
5. Remap: BuildRig와 `.bmap` 역할 규칙이 같은지 추가 점검

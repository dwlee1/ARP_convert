# 구조 기반 자동 본 매핑 — Preview Armature 방식

> 최종 수정: 2026-03-19 (v2 — leg/foot 분리, ear, bank/heel 추가)

## Context

이름 기반 JSON 프로필은 동물마다 본 이름이 달라 확장 불가.
**소스 deform 본을 복제 → Preview Armature에서 역할 배정/수정 → ARP 리그 생성** 방식으로 전환.

## 확정 사항

- ARP **dog 프리셋 고정**, **3-bone leg 고정** (`thigh_b_ref` 계열)
- 소스 리그는 **항상 정상 트리 구조**
- **.bmap 자동 생성** (리타게팅까지 자동화)
- 얼굴 본(eye, jaw, mouth, tongue) → **cc_ 커스텀 본** (`bpy.ops.arp.add_custom_bone`)
- **ear는 cc_ 아님** → ARP 기본 `ear_01_ref` / `ear_02_ref`에 직접 매핑
- Preview Armature **원본 이름 유지** + 역할을 **본 그룹/색상**으로 표시
- 역할 지정: **본 선택 → 사이드바 드롭다운**
- 체인 순서: **하이어라키(부모→자식) 자동**
- ARP ref 본 이름은 **하드코딩 아닌 동적 검색** (`discover_arp_ref_chains`)

---

## 워크플로우

```
[Step 1: 추출]  소스 deform 본 → 새 "Preview Armature" 생성
                자동 분석으로 역할 배정 + 역할별 색상 표시
                다리는 전부 leg 역할으로 자동 배정
                     ↓
[Step 2: 검토]  3D 뷰에서 시각적 확인
                본 선택 → 사이드바 드롭다운으로 역할 변경
                ★ 다리 끝 본을 back_foot / front_foot 역할로 수동 분리
                → foot 지정 시 bank/heel 가이드 본 자동 생성
                Edit Mode에서 본 위치/방향 직접 수정
                     ↓
[Step 3: 생성]  "리그 생성" 클릭
                → append_arp(dog)
                → 동적 ref 본 검색 (discover_arp_ref_chains)
                → Preview 본 위치를 ARP ref 본에 복사 (하이어라키 순서)
                → bank/heel 가이드 → foot_bank_ref / foot_heel_ref 복사
                → match_to_rig
                → 얼굴 본은 cc_ 커스텀 본으로 추가
                     ↓
[Step 4: 리타게팅]  동적 .bmap 생성 → 액션별 retarget
```

---

## 역할 목록 + 색상

| 역할 | ARP ref 본 (동적 검색) | 본 그룹 색상 |
|------|----------------------|-------------|
| root | root_ref.x | 노랑 |
| spine | spine_01~03_ref.x | 파랑 |
| neck | neck_ref.x | 파랑 |
| head | head_ref.x | 파랑 |
| **back_leg_l/r** | thigh_b_ref → thigh_ref → leg_ref | 빨강 |
| **back_foot_l/r** | foot_ref (+ toes_ref 있으면 포함) | 진빨강 |
| **front_leg_l/r** | thigh_b_ref_dupli_001 → thigh_ref_dupli_001 → leg_ref_dupli_001 | 초록 |
| **front_foot_l/r** | foot_ref_dupli_001 (+ toes_ref_dupli_001 있으면 포함) | 진초록 |
| **ear_l/r** | ear_01_ref → ear_02_ref | 시안 |
| tail | tail_00~03_ref.x | 주황 |
| face | cc_ 커스텀 본 (eye, jaw, mouth, tongue) | 보라 |
| unmapped | (제외) | 회색 |

---

## Leg / Foot 분리 규칙

### 자동 분석 단계
- 스파인 분기점~끝까지 전체를 **leg 역할**으로 배정
- foot 분리는 사용자가 Preview에서 **수동**으로 수행

### 적용 규칙
- `leg` 역할 본이 3개면 ARP도 **반드시 3본 다리 체인**으로 매핑
  - 예: `thigh_b_ref → thigh_ref → leg_ref`
- `foot` 역할 본이 1개면 ARP `foot_ref + toes_ref`로 **분할 생성**
  - 소스 toe 본이 없으면 `virtual toe`를 생성
  - 소스 foot의 `tail`은 `toes_ref.tail` 끝점으로 사용
- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑

### Fox 예시 (뒷다리)
| 소스 본 | 역할 | ARP ref |
|---------|------|---------|
| thigh_L | back_leg_l | thigh_b_ref.l |
| leg_L | back_leg_l | thigh_ref.l |
| foot_L | back_leg_l | leg_ref.l |
| toe_L | **back_foot_l** | foot_ref.l |
| toe tip | **back_foot_l** | toes_ref.l |

### Fox 예시 (앞다리)
| 소스 본 | 역할 | ARP ref |
|---------|------|---------|
| shoulder_L | front_leg_l | thigh_b_ref_dupli_001.l |
| upperarm_L | front_leg_l | thigh_ref_dupli_001.l |
| arm_L | front_leg_l | leg_ref_dupli_001.l |
| hand_L | **front_foot_l** | foot_ref_dupli_001.l |
| hand tip | **front_foot_l** | toes_ref_dupli_001.l |

### toe가 없는 리그
- `back_foot` 또는 `front_foot` 역할이 1본이면:
  - `foot_ref.head` = 소스 foot.head
  - `foot_ref.tail = toes_ref.head` = 소스 foot 길이의 중간 분할점
  - `toes_ref.tail` = 소스 foot.tail

---

## Bank / Heel 가이드 본

### 생성 조건
- `back_foot_l/r` 또는 `front_foot_l/r` 역할이 지정될 때 **자동 생성**
- Preview Armature에 추가됨 (Edit Mode에서 위치 조정 가능)

### 기본 위치 (foot 본의 head 기준)
| 가이드 | 오프셋 | 설명 |
|--------|--------|------|
| `_heel` | -Z (바닥) + 약간 -Y (뒤쪽) | 뒤꿈치 피벗 |
| `_bank` | ±X (좌우) | 발 기울기 피벗 |

### ARP 매핑
| Preview 가이드 | ARP ref 본 |
|---------------|-----------|
| back_heel_l | foot_heel_ref.l |
| back_bank_l | foot_bank_ref.l |
| front_heel_l | foot_heel_ref_dupli_001.l |
| front_bank_l | foot_bank_ref_dupli_001.l |

---

## Ear 처리

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 역할 | face에 포함 | ear_l / ear_r 독립 |
| ARP 매핑 | cc_ 커스텀 본 | ear_01_ref / ear_02_ref (기본 제공) |
| 자동 분석 | face_bones에 포함 | ear 체인 별도 감지 → ear_l/r 자동 배정 |

---

## 체인 길이 매칭

소스 본 수 ≠ ARP ref 본 수일 때:
- **동일**: 1:1 매핑
- **소스 > ARP**: 양 끝점 고정 + 중간 인덱스 보간
- **소스 < ARP**: 루트부터 순서대로, 나머지 미매핑

---

## 파일 구조

| 파일 | 작업 | 설명 |
|------|------|------|
| `scripts/skeleton_analyzer.py` | 수정 | leg/foot 분리, ear 역할, bank/heel 가이드, 동적 ref 검색 |
| `scripts/arp_convert_addon.py` | 수정 | 새 역할 UI, foot 지정 시 가이드 자동 생성 |
| `scripts/pipeline_runner.py` | 수정 | `--auto` 모드 대응 |
| `scripts/03_batch_convert.py` | 유지 | `--auto` 전달 |

---

## 검증

1. Fox — Preview 생성 → leg/foot 수동 분리 → bank/heel 위치 확인 → 리그 생성 → ref 본 정렬 확인
2. Fox — ear 역할 → ear_ref 정렬 확인
3. Stag — 다른 이름 자동 식별 + 수동 역할 수정
4. Fox — 리타게팅 → 동적 .bmap 성공
5. 배치 — `--auto` 모드로 Preview 없이 일괄 처리

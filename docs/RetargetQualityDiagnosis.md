# 애니메이션 리타게팅 품질 이슈 진단 및 수정 계획

**작성일**: 2026-03-27
**상태**: 진단 완료, 수정 미적용

## Context

Fox 에셋 리타게팅 후 "전반적으로 살짝 틀어짐 + 오른쪽 앞발 크게 틀어짐" 현상.
원인은 `discover_arp_ctrl_map()`의 버그로 spine/tail/ear 컨트롤러가 잘못/누락 매핑되고, back_leg에 `c_thigh_b` 패턴이 빠져 있기 때문.

---

## 버그 1: `discover_arp_ctrl_map()` — 패턴당 첫 매칭만 수집 (핵심 버그)

**파일**: `scripts/skeleton_analyzer.py` 1595-1599행

```python
for pat in patterns:
    for bone_name in all_bones:
        if re.match(pat, bone_name):
            matched.append(bone_name)
            break  # ← 패턴당 첫 매칭만! wildcard 패턴에서 치명적
```

**영향**: `\d+` 와일드카드 패턴을 쓰는 역할에서 **첫 번째 매칭 본만** 반환:

| 역할 | 패턴 | 실제 본 | 발견 결과 |
|------|-------|---------|-----------|
| spine | `c_spine_\d+\.` | c_spine_01.x, c_spine_02.x, c_spine_03.x | **1개만** (비결정적) |
| tail | `c_tail_\d+\.` | c_tail_00~03.x | **1개만** |
| ear_l | `c_ear_\d+\.l` | c_ear_01.l, c_ear_02.l | **1개만** |
| ear_r | `c_ear_\d+\.r` | c_ear_01.r, c_ear_02.r | **1개만** |

`discover`가 결과를 반환하므로 fallback(`_dynamic_ctrl_names` / `ARP_CTRL_MAP`)이 **트리거되지 않음**.
→ spine01이 c_spine_03에 매핑되고 spine02/chest는 아예 매핑 안 되는 식.

**실제 .bmap 결과** (`auto_generated.bmap`에서 확인):
- `spine01 → c_spine_02.x` (잘못된 타겟, spine02/chest 매핑 없음)
- `tail_01 → c_tail_03.x` (잘못된 타겟, tail02/03/04 매핑 없음)
- `ear01_R → c_ear_02.r` (잘못된 타겟, ear02_R 매핑 없음)

### 수정 방법

```python
for pat in patterns:
    pat_matches = sorted(
        name for name in all_bones if re.match(pat, name)
    )
    matched.extend(pat_matches)
```

`break` 제거, 패턴 내 매칭을 이름 순 정렬하여 전부 수집. 패턴 간 순서는 기존대로 유지 (leg chain 순서 보존).

---

## 버그 2: back_leg 패턴에 `c_thigh_b` 누락

**파일**: `scripts/skeleton_analyzer.py` 1547-1548행

```python
"back_leg_l": [r"^c_thigh_fk\.l", r"^c_leg_fk\.l", r"^c_foot_fk\.l"],
"back_leg_r": [r"^c_thigh_fk\.r", r"^c_leg_fk\.r", r"^c_foot_fk\.r"],
```

3-bone leg 모드(dog 프리셋)에서는 `c_thigh_b.l/r`이 존재하지만 패턴이 없어 발견 불가.
→ back_leg가 2본 체인(thigh_fk, leg_fk)으로 매핑되고 thigh_b가 빠짐.

**참고**: front_leg는 `c_thigh_b_dupli_\d+` 패턴이 이미 있어 정상 동작.

### 수정 방법

```python
"back_leg_l": [r"^c_thigh_b\.l$", r"^c_thigh_fk\.l", r"^c_leg_fk\.l", r"^c_foot_fk\.l"],
"back_leg_r": [r"^c_thigh_b\.r$", r"^c_thigh_fk\.r", r"^c_leg_fk\.r", r"^c_foot_fk\.r"],
```

`c_thigh_b` 패턴을 chain 순서 맨 앞에 추가. 3-bone 모드가 아니면 매칭 안 되므로 안전.

---

## 오른쪽 앞발 크게 틀어지는 현상 분석

앞다리 자체의 L/R 매핑은 .bmap에서 대칭이므로 코드 레벨 비대칭은 없음. 가능한 원인:

1. **spine 매핑 누락의 간접 영향**: spine02/chest가 리타겟 안 되면 상체 회전이 고정됨 → 앞다리가 몸통에 의존하는 만큼 결과가 틀어짐
2. **소스 아마추어 자체의 L/R 비대칭**: rest pose에서 미세한 차이가 있으면 한쪽만 크게 틀어질 수 있음
3. **IK 모드**: .bmap에서 foot 역할에 IK=True가 설정됨 — IK pole 방향이 소스와 맞지 않으면 한쪽이 더 크게 틀어짐

→ **버그 1, 2를 먼저 수정한 뒤** 앞발 이슈가 해소되는지 재테스트. 해소 안 되면 IK/비대칭 조사.

---

## 변경 대상 파일

| 파일 | 변경 | 라인 |
|------|------|------|
| `scripts/skeleton_analyzer.py` | `discover_arp_ctrl_map()`: `break` 제거, 패턴 내 전체 수집 + 정렬 | 1595-1599 |
| `scripts/skeleton_analyzer.py` | `_CTRL_SEARCH_PATTERNS`: back_leg에 `c_thigh_b` 패턴 추가 | 1547-1548 |

---

## 검증 계획

1. `pytest tests/ -v` — 기존 테스트 통과 확인
2. Blender에서 fox 에셋 전체 파이프라인 재실행:
   - Build Rig → Remap Setup → Retarget
   - `.bmap` 확인: spine 3개, tail 4개, ear 2개씩 매핑 / back_leg에 thigh_b 포함
   - 애니메이션 결과 비교 (특히 오른쪽 앞발)
3. 앞발 이슈 미해소 시 IK mode off 테스트 (`ik_legs=False`)

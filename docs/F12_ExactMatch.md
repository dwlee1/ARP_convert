# F12: COPY_TRANSFORMS 기반 애니메이션 베이크

> 설계 확정: 2026-04-02
> 최종 보강: 2026-04-03 (grill-me 세션 반영)

## 1. 배경

ARP 리그 변환 후 원본 애니메이션을 ARP 리그로 전달하는 기능이 필요하다.

ARP 네이티브 리타게팅(`bpy.ops.arp.retarget`)은 **Rotation만 전달**하는 것이 기본이며,
spine/head 등에 **Location 키프레임**이 있을 경우 이 움직임이 누락되거나 왜곡된다.

본 위치가 유사한 상황(ARP 리그를 원본 DEF 본 기준으로 빌드)을 활용하되,
컨트롤러 rest 축 차이를 무시하지 않고 **rest delta**를 전달한다.

핵심 수식:

```text
delta = source_rest^-1 * source_pose
target_pose = controller_rest * delta
```

즉 소스 본의 pose를 그대로 복사하지 않고,
**소스 rest 기준 변화량을 ARP 컨트롤러 rest 기준으로 재해석**해
Loc/Rot/Scale을 전달한다.

### 왜 rest-delta offset bake인가

| 방식 | 문제 |
|------|------|
| ARP 네이티브 retarget | Rotation만 전달, Location 누락 또는 왜곡 |
| ARP Location 리매핑 | 계층 구조 차이로 값 왜곡 |
| FCurve 직접 복사 | 로컬 축 방향이 다르면 움직임 방향 틀어짐 |
| COPY_LOCATION + COPY_ROTATION | 개별 constraint 2개 관리 필요 |
| COPY_TRANSFORMS (WORLD) | 월드 결과는 맞아도 IK 컨트롤러 rest 축 차이에서 180° 뒤집힘 가능 |
| **rest-delta offset bake** | **rest 축 차이를 반영해 소스 pose delta를 컨트롤러 축으로 변환** |

### 전제 조건

- ARP 리그를 소스 골격 기준으로 빌드했으므로 rest pose가 **대체로 유사**
- ARP `match_to_rig` 시 roll 정규화와 IK 컨트롤러 축 차이가 생길 수 있으므로,
  bake 시점에 rest delta를 다시 계산해야 한다.

## 2. 설계 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| 매핑 방식 | Build Rig 데이터 자동 활용 | `deform_to_ref` + `discover_arp_ctrl_map`으로 구성, `arp_obj["arpconv_bone_pairs"]`에 JSON 저장 |
| 베이크 대상 | ARP FK 컨트롤러 본 | IK/FK 전환 기능 유지, ARP 리그 구조 보존 |
| 베이크 엔진 | 프레임 샘플링 + 직접 keyframe insert | rest 축 차이를 제어하고 `visual_keying`/Child Of 충돌을 피함 |
| 액션 순회 | **임시 NLA strip + 기존 NLA mute** | Blender 4.4+ Action Slot 호환 (직접 할당 방식 사용 금지) |
| IK 처리 | FK 컨트롤러만 베이크 | FK로도 동일 모션 재현 가능, IK/FK 전환 보존 |
| 스케일 채널 | 역할 본: Loc/Rot만 유지 (Scale FCurve 삭제), cc_ 커스텀 본: Scale 포함 | ARP stretch/IK 시스템 충돌 방지 |
| 액션 이름 | 원본명 + `_arp`, 기존 동명 액션은 삭제 후 재생성 | 재실행 시 중복 방지 |
| 변환 방식 | `source_rest^-1 * source_pose` → `controller_rest * delta` | source/controller 축 차이를 bake 시점에 보정 |
| Euler 처리 | 이전 프레임 근처 각도로 보정 | `±180°` 점프 최소화 |

## 3. Preflight Check (HARD GATE)

베이크 시작 전 아래 조건을 검사하고, **하나라도 실패하면 즉시 중단**한다:

| 체크 | 조건 | 실패 시 |
|------|------|---------|
| 오브젝트 Transform | 소스/ARP 양쪽 아마추어의 location=(0,0,0), rotation=(0,0,0), scale=(1,1,1) | 에러 + 중단 |
| bone_pairs 존재 | `arp_obj["arpconv_bone_pairs"]`가 존재하고 비어있지 않음 | "Build Rig를 먼저 실행하세요" 에러 |
| 소스 액션 존재 | 소스 아마추어에 최소 1개 액션이 있음 | "베이크할 액션이 없습니다" 에러 |

> 오브젝트 transform preflight는 유지한다. offset bake도 object transform이 틀어지면
> pose/rest 해석 기준이 흔들리므로 hard check가 필요하다.

## 4. 매핑 체인

Build Rig 결과물에서 자동으로 매핑을 구성한다:

```
역할 매핑 본:
  source "thigh_L"
    → deform_to_ref["thigh_L"] = "thigh_b_ref.l"     (Build Rig 결과)
    → role = "back_leg_l", chain_index = 0             (arp_chains 역산)
    → controller = "c_thigh_b.l"                        (_CTRL_SEARCH_PATTERNS)  # 2026-04-05 수정: c_thigh_b.l이 맞음 (back_leg 첫 본, IK shoulder)
    → bone_pairs: ("thigh_L", "c_thigh_b.l", False)

cc_ 커스텀 본:
  source "eye_L"
    → unmapped → cc_ 커스텀 본으로 ARP에 등록 (원본 이름 유지)
    → bone_pairs: ("eye_L", "eye_L", True)
```

### bone_pairs 저장 형식

Build Rig 완료 시 `arp_obj["arpconv_bone_pairs"]`에 JSON으로 저장:

```python
# (source_bone, arp_controller, is_custom)
[
    ("thigh_L", "c_thigh_b.l", false),
    ("leg_L", "c_leg_fk.l", false),
    ("eye_L", "eye_L", true),
    ("jaw", "jaw", true)
]
```

- `is_custom=false`: 역할 매핑 본 → 베이크 후 Scale FCurve 삭제
- `is_custom=true`: cc_ 커스텀 본 → Scale 포함 베이크

매핑에 활용하는 기존 코드:
- `skeleton_analyzer.py:61` — `ARP_CTRL_MAP` (역할별 컨트롤러 이름)
- `skeleton_analyzer.py:1628` — `discover_arp_ctrl_map()` (동적 탐색)
- `arp_convert_addon.py:1948` — `map_role_chain()` (source→ref 매핑)

## 5. 파이프라인

```
Build Rig (기존)
  ↓ bone_pairs 저장: arp_obj["arpconv_bone_pairs"] (JSON)

Bake Animation (신규, 별도 버튼)
  ↓ Preflight Check — 실패 시 중단
  ↓ bone_pairs 로드
  ↓ 소스의 모든 액션 순회 (각 액션마다):
      1. 기존 NLA 트랙 전부 뮤트
      2. 임시 NLA strip으로 해당 액션 평가
      3. 기존 _arp 액션이 있으면 삭제
      4. 각 bone_pair에 대해 source/controller rest matrix 캐시
      5. 각 프레임에서 source pose delta 계산
      6. controller rest 기준 target pose 재구성
      7. ARP 컨트롤러 local channels(location/rotation/scale)에 직접 키 삽입
      8. 역할 본(is_custom=false)의 Scale FCurve 삭제
      9. ARP에 새 액션 생성 (원본명 + "_arp")
      10. 임시 NLA strip 제거, 뮤트 복원
  ↓ 결과: ARP 컨트롤러 축 기준으로 변환된 모션
```

### 액션 평가 방식 (HARD RULE)

**액션 직접 할당(`animation_data.action = action`) 사용 금지.**

Blender 4.4+ Action Slot 시스템에서 직접 할당이 깨지는 것이 확인됨
(커밋: `fab4307`, `a1e2316`, `0d254ff`).

반드시 아래 패턴을 사용한다:
1. 소스의 기존 NLA 트랙 전부 뮤트
2. 임시 NLA 트랙 생성 → 해당 액션을 strip으로 추가
3. 평가 완료 후 임시 트랙 제거, 기존 트랙 뮤트 복원

### 실패 복구

```python
try:
    # 프레임 순회 → pose delta 계산 → 키프레임 삽입
finally:
    # 절반만 구워진 액션 삭제
    # NLA mute 상태 복원
    # 남아 있을 수 있는 레거시 ARPCONV_CopyTF constraint 정리
```

## 6. 수정 대상

| 파일 | 수정 내용 |
|------|-----------|
| `scripts/arp_utils.py` | `bake_with_copy_transforms()`를 rest-delta offset bake로 전환, `bake_all_actions()` 유지 |
| `scripts/arp_convert_addon.py` | Build Rig 완료 시 `bone_pairs` JSON 저장, `ARPCONV_OT_BakeAnimation` 오퍼레이터 + "Step 4: Bake Animation" UI 버튼 |
| `scripts/pipeline_runner.py` | Build Rig 후 `--bake` 플래그 시 `bake_all_actions()` 호출 |

## 7. 핵심 함수 시그니처

### `bake_with_copy_transforms()` — `arp_utils.py`

```python
def bake_with_copy_transforms(source_obj, arp_obj, bone_pairs, frame_start, frame_end):
    """
    bone_pairs 기반으로 source rest delta를 ARP 컨트롤러에 직접 베이크.

    Args:
        source_obj: 원본 아마추어 오브젝트
        arp_obj: ARP 아마추어 오브젝트
        bone_pairs: [(source_bone_name, arp_controller_name, is_custom), ...]
        frame_start, frame_end: 프레임 범위

    동작:
        1. bone_pairs의 source/controller rest matrix 캐시
        2. 각 프레임에서 source pose delta 계산
        3. controller rest 기준 target pose 재구성
        4. location/rotation/scale 채널에 직접 keyframe insert
        5. is_custom=False 본의 Scale FCurve 삭제
    """
```

레거시 cleanup 호환을 위해 `ARPCONV_CopyTF` 정리 코드는 유지하지만,
신규 bake는 임시 constraint를 추가하지 않는다.

### `bake_all_actions()` — `arp_utils.py`

```python
def bake_all_actions(source_obj, arp_obj, bone_pairs):
    """
    소스 아마추어의 모든 액션을 순회하며 각각 bake_with_copy_transforms() 호출.

    액션 평가: 임시 NLA strip + 기존 NLA mute (Action Slot 호환).
    프레임 범위: action.frame_range 사용.
    액션 이름: 원본명 + "_arp", 기존 동명 액션은 삭제 후 재생성.

    try/finally로 실패 시 constraint 정리 + NLA 복원 보장.
    """
```

## 8. 주의사항

1. **rest pose 미세 차이**: ARP `match_to_rig` roll 정규화나 IK 컨트롤러 축 차이가
   남아도, bake 시점의 rest delta 재계산으로 직접 보정한다.

2. **IK/FK 모드**: IK 컨트롤러를 직접 베이크하는 pair가 있으므로,
   bake 중에는 `_ensure_ik_mode()`로 IK 상태를 보장한다.

3. **세 경로 동기화** (HARD RULE #6):
   addon / pipeline_runner / batch 모두 동일한 `bake_with_copy_transforms()` 사용.

4. **pipeline_runner**: `--bake` 플래그 기반 제어. 기본값은 Build Rig까지만 실행.

## 9. 검증

- [ ] 여우 테스트 파일: Build Rig → Bake Animation → 타임라인 재생, 원본과 동일한 모션 확인
- [ ] spine/head에 Location 키가 있는 소스로 베이크 → 위치값 정상 전달 확인
- [ ] 다중 액션 파일에서 각 액션별 정상 동작 확인
- [ ] cc_ 커스텀 본(eye, jaw)의 Scale 애니메이션이 보존되는지 확인
- [ ] 베이크 재실행 시 기존 `_arp` 액션이 정상 교체되는지 확인
- [ ] Preflight check: 오브젝트 transform이 어긋난 상태에서 에러 + 중단 확인
- [ ] `pytest tests/ -v` 통과

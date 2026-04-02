# F12: COPY_TRANSFORMS 기반 애니메이션 베이크

> 설계 확정: 2026-04-02

## 1. 배경

ARP 리그 변환 후 원본 애니메이션을 ARP 리그로 전달하는 기능이 필요하다.

ARP 네이티브 리타게팅(`bpy.ops.arp.retarget`)은 **Rotation만 전달**하는 것이 기본이며,
spine/head 등에 **Location 키프레임**이 있을 경우 이 움직임이 누락되거나 왜곡된다.

본 위치가 동일한 상황(ARP 리그를 원본 DEF 본 기준으로 빌드)을 활용해,
`COPY_TRANSFORMS (WORLD→WORLD)` + `nla.bake(visual_keying=True)`로
Loc/Rot/Scale을 완벽히 복제한다.

### 왜 COPY_TRANSFORMS (WORLD→WORLD)인가

| 방식 | 문제 |
|------|------|
| ARP 네이티브 retarget | Rotation만 전달, Location 누락 또는 왜곡 |
| ARP Location 리매핑 | 계층 구조 차이로 값 왜곡 |
| FCurve 직접 복사 | 로컬 축 방향이 다르면 움직임 방향 틀어짐 |
| COPY_LOCATION + COPY_ROTATION | 개별 constraint 2개 관리 필요 |
| **COPY_TRANSFORMS (WORLD)** | **축/계층/스케일 차이를 Blender가 자동 변환, 단일 constraint** |

### 전제 조건

- ARP 리그를 소스 골격 기준으로 빌드했으므로 rest pose가 **거의 동일**
- ARP `match_to_rig` 시 roll 정규화로 미세 차이 가능하나, WORLD 공간 COPY_TRANSFORMS가 자동 보상
- 양쪽 아마추어 오브젝트 transform은 (0,0,0) 권장

## 2. 설계 결정

| 항목 | 결정 | 이유 |
|------|------|------|
| 매핑 방식 | Build Rig 데이터 자동 활용 | bones_map_v2 삭제됨, deform_to_ref+discover_arp_ctrl_map으로 대체 |
| 베이크 대상 | ARP FK 컨트롤러 본 | IK/FK 전환 기능 유지, ARP 리그 구조 보존 |
| 베이크 엔진 | `bpy.ops.nla.bake()` | 표준 Blender API, ARP 내부 의존 없음 |
| 액션 범위 | 소스의 모든 액션 자동 순회 | 일반적인 게임/애니 파일은 다중 액션 |
| IK 처리 | FK 컨트롤러만 베이크 | FK로도 동일 모션 재현 가능, IK/FK 전환 보존 |

## 3. 매핑 체인

Build Rig 결과물에서 자동으로 매핑을 구성한다:

```
source_bone "thigh_L"
  → deform_to_ref["thigh_L"] = "thigh_b_ref.l"     (Build Rig 결과)
  → role = "back_leg_l", chain_index = 0             (arp_chains 역산)
  → controller = "c_thigh_fk.l"                      (_CTRL_SEARCH_PATTERNS)
  → COPY_TRANSFORMS: source "thigh_L" → ARP "c_thigh_fk.l"

cc_ 커스텀 본 "eye_ctrl"
  → ARP 쪽도 "eye_ctrl" (이름 보존)
  → COPY_TRANSFORMS: source "eye_ctrl" → ARP "eye_ctrl"
```

매핑에 활용하는 기존 코드:
- `skeleton_analyzer.py:61` — `ARP_CTRL_MAP` (역할별 컨트롤러 이름)
- `skeleton_analyzer.py:1628` — `discover_arp_ctrl_map()` (동적 탐색)
- `arp_convert_addon.py:1948` — `map_role_chain()` (source→ref 매핑)

## 4. 파이프라인

```
Build Rig (기존)
  ↓ 매핑 데이터 저장: arp_obj["arpconv_bone_pairs"] (JSON)
Bake Animation (신규, 별도 버튼)
  ↓ build_bake_bone_pairs() — deform_to_ref + arp_chains → [(src, ctrl), ...]
  ↓ 소스의 모든 액션 순회:
      소스에 액션 할당
      COPY_TRANSFORMS (WORLD→WORLD) 추가
      nla.bake(visual_keying=True, clear_constraints=False)
      ARPCONV_CopyTF constraint만 제거
      ARP에 새 액션 생성 (원본명 + "_arp")
  ↓ 결과: ARP 컨트롤러에 소스와 동일한 월드 공간 Loc/Rot/Scale
```

## 5. 수정 대상

| 파일 | 수정 내용 |
|------|-----------|
| `scripts/arp_utils.py` | `build_bake_bone_pairs()`, `bake_with_copy_transforms()`, `bake_all_actions()` 추가 |
| `scripts/arp_convert_addon.py` | `ARPCONV_OT_BakeAnimation` 오퍼레이터 + "Step 4: Bake Animation" UI 버튼, Build Rig 완료 시 bone_pairs JSON 저장 |
| `scripts/pipeline_runner.py` | Build Rig 후 `bake_all_actions()` 호출 추가 |

## 6. 핵심 함수 시그니처

### `bake_with_copy_transforms()` — `arp_utils.py`

```python
def bake_with_copy_transforms(source_obj, arp_obj, bone_pairs, frame_start, frame_end):
    """
    bone_pairs 기반으로 COPY_TRANSFORMS → Bake → Constraint 제거.

    Args:
        source_obj: 원본 아마추어 오브젝트
        arp_obj: ARP 아마추어 오브젝트
        bone_pairs: [(source_bone_name, arp_controller_name), ...]
        frame_start, frame_end: 프레임 범위
    """
```

**`clear_constraints=False` 필수**: `True`로 하면 해당 본의 **모든** constraint가 삭제되어
ARP 내부 constraint가 파괴된다. 추가한 `ARPCONV_CopyTF`만 수동 제거.

### `bake_all_actions()` — `arp_utils.py`

```python
def bake_all_actions(source_obj, arp_obj, bone_pairs):
    """
    소스 아마추어의 모든 액션을 순회하며 각각 bake_with_copy_transforms() 호출.
    Blender 4.5 Action Slot 호환 처리 포함.
    ARP에는 원본 액션명 + "_arp" 이름으로 새 액션 생성.
    """
```

## 7. 주의사항

1. **rest pose 미세 차이**: ARP `match_to_rig`에서 roll 정규화로 발생 가능.
   WORLD 공간 COPY_TRANSFORMS가 자동 보상하므로 대부분 문제없다.
   메시 변형에 미세 차이 시 특정 본만 하이브리드 방식 고려.

2. **IK/FK 모드**: FK 컨트롤러에만 베이크하므로 베이크 후에는 FK 모드 상태.
   ARP의 IK/FK 전환 기능 자체는 유지된다.

3. **다중 액션 Bake**: `nla.bake()`는 현재 활성 액션에만 Bake.
   각 액션별: 액션 할당 → constraint 추가 → bake → constraint 제거 루프.

4. **세 경로 동기화** (HARD RULE #6):
   addon / pipeline_runner / batch 모두 동일한 `bake_with_copy_transforms()` 사용.

## 8. 검증

- [ ] 여우 테스트 파일: Build Rig → Bake Animation → 타임라인 재생, 원본과 동일한 모션 확인
- [ ] spine/head에 Location 키가 있는 소스로 베이크 → 위치값 정상 전달 확인
- [ ] 다중 액션 파일에서 각 액션별 정상 동작 확인
- [ ] `pytest tests/ -v` 통과

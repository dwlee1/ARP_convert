# F12: ARP 네이티브 리타겟 위임 방식

> 설계 확정: 2026-04-06
> 이전 문서: `F12_ExactMatch.md` (rest-delta offset bake — 폐기)

## 1. 배경

### 이전 접근 (rest-delta offset bake) 문제

rest-delta 수학으로 FK 체인(spine, head, tail)은 정확하지만, IK 컨트롤러(`c_foot_ik`)에서
축 180° 뒤집힘이 발생했다. `_bake_ik_target_frame()` 분기 처리, ARP 네이티브 리타겟 +
월드스페이스 로케이션 2-pass 등 여러 시도가 있었으나 복잡도만 증가.

### 해결: ARP 네이티브 리타겟에 전면 위임

수동 테스트 결과, ARP 리타겟 UI에서 소스 DEF 본과 ARP 컨트롤러를 직접 연결하면
FK/IK 모두 정확하게 베이크됨을 확인. 이에 따라:

- **리그 변환(Build Rig)까지만 우리 애드온** 사용
- **애니메이션 베이크는 ARP 리타겟 UI에 완전 위임**
- 우리 코드는 매핑 세팅(Setup)과 후처리(Cleanup)만 담당

## 2. 아키텍처

```
[Create Preview]      ← 기존 유지
[Build Rig]           ← 기존 유지
[Setup Retarget]      ← 신규: bone_pairs → bones_map_v2 변환
                         사용자가 ARP Remap 패널에서 매핑 확인/수정
                         사용자가 ARP "Re-Retarget" 버튼 클릭 (베이크)
[Cleanup]             ← 신규: 소스/프리뷰 삭제 + 액션 rename
```

### 핵심 원칙

- `bpy.ops.arp.retarget()`을 우리 코드에서 호출하지 않는다
- 사용자가 ARP UI에서 매핑을 확인/수정할 수 있는 기회를 보장한다
- 다중 액션은 ARP의 `batch_retarget=True` (Multiple Source Anim) 사용

## 3. Setup Retarget 오퍼레이터

### 실행 순서

```python
def execute(self, context):
    # 1. Scene property 세팅
    scn.source_rig = source_obj.name    # 원본 아마추어
    scn.target_rig = arp_obj.name       # ARP 리그

    # 2. ARP build_bones_list 호출 → bones_map_v2 생성
    bpy.ops.arp.build_bones_list()

    # 3. bone_pairs 기반 오버라이드 (나머지는 ARP 추측 유지)
    bone_pairs = deserialize_bone_pairs(arp_obj[BAKE_PAIRS_KEY])
    _override_bones_map(bone_pairs)

    # 4. batch_retarget 활성화
    scn.batch_retarget = True

    # 5. 기존 _remap 액션 삭제 (중복 방지)
    _delete_existing_remap_actions()
```

### 매핑 규칙 (bone_pairs → bones_map_v2)

| 조건 | target (name) | location | ik | set_as_root |
|------|---------------|----------|-----|-------------|
| root | `c_root.x` | True | False | True |
| root 외 모든 매핑 본 | 해당 컨트롤러 | False | **True** | False |
| 다리 중간 (leg role, idx > 0) | `""` (빈 매핑) | - | - | - |
| bone_pairs에 없는 본 | `""` (빈 매핑) | - | - | - |

> **ik=True는 월드 스페이스 매칭**: rest-pose 차이와 무관하게 소스 본의 월드 위치/회전을
> 직접 매칭한다. `location=True`(rest-relative)보다 정확하며, 여우 리그 walk 검증에서
> spine/neck/head/ear/shoulder/custom 본 모두 위치 0.000mm, 회전 0.0° 달성 (2026-04-08).

### Root 매핑 주의사항

`DEF-pelvis`는 `c_root_master.x`가 아닌 **`c_root.x`**에 매핑해야 한다.

- `c_root_master.x`: head→tail 방향이 -Y (pelvis와 180° 반전) → location 왜곡
- `c_root.x`: head→tail 방향이 +Y (pelvis와 동일) → 정상 작동
- 계층: `c_traj → c_root_master.x → c_root.x`

### IK 다리 매핑 규칙

- 4족 동물은 앞다리/뒷다리 모두 IK 모드
- 다리 체인의 첫 번째 본(shoulder, idx=0)만 FK로 매핑
- 나머지(idx > 0)는 빈 매핑 — IK solver가 처리
- 발끝(foot role)만 IK 타겟으로 매핑
- Pole vector는 매핑 불필요 — `pole_parent=1`이 Build Rig에서 이미 활성화됨

### 오버라이드 로직

```python
def _override_bones_map(bone_pairs):
    scn = bpy.context.scene

    # bone_pairs에서 유효 매핑 룩업 생성
    lookup = {}
    for src, ctrl, is_custom in bone_pairs:
        # IK 체인 중간 본 제외 로직은 역할 기반으로 판단
        lookup[src_to_def_name(src)] = {
            "ctrl": ctrl,
            "is_custom": is_custom,
            # location/ik/set_as_root는 역할에서 결정
        }

    # bones_map_v2 오버라이드 (매칭되는 것만, 나머지는 ARP 추측 유지)
    for entry in scn.bones_map_v2:
        if entry.source_bone in lookup:
            mapping = lookup[entry.source_bone]
            entry.name = mapping["ctrl"]
            entry.location = ...   # 역할별 규칙
            entry.ik = ...         # 역할별 규칙
            entry.set_as_root = ... # root만 True
```

## 4. Cleanup 오퍼레이터

사용자가 베이크 결과를 확인하고 만족한 후 수동으로 실행하는 **별도 버튼**.

### 실행 순서

```
1. 소스 아마추어 오브젝트 + 데이터 삭제
2. Preview 아마추어 오브젝트 + 데이터 삭제
3. _remap 액션을 원본 이름으로 rename (walk_remap → walk)
```

### rename 주의사항

- 소스 아마추어 삭제 시 소스 액션이 orphan이 되므로, 먼저 소스 액션을 삭제한 뒤
  `_remap` 액션을 원본 이름으로 rename하면 이름 충돌이 없다
- 순서: 소스 액션 삭제 → 소스/프리뷰 아마추어 삭제 → _remap rename

## 5. 삭제 대상 (기존 F12 코드)

### arp_utils.py에서 삭제

| 함수 | 이유 |
|------|------|
| `bake_with_copy_transforms()` | ARP 리타겟으로 대체 |
| `bake_all_actions()` | batch_retarget으로 대체 |
| `_iter_bake_pose_pairs()` | 프레임 순회 없음 |
| `_insert_pose_keyframe()` | 직접 키프레임 안 함 |
| `_insert_pose_keyframe_location_only()` | 위와 동일 |
| `_make_compatible_euler_angles()` | ARP 내부 처리 |
| `_ensure_ik_mode()` / `_restore_ik_fk()` | ARP `set_ik_fk_switch_remap()` 내부 처리 |
| `_cleanup_scale_fcurves()` | ARP 결과에 불필요한 Scale FCurve 없음 |

### arp_ops_bake_regression.py에서 수정

| 항목 | 변경 |
|------|------|
| `ARPCONV_OT_BakeAnimation` | → `ARPCONV_OT_SetupRetarget`으로 교체 |
| 신규 | `ARPCONV_OT_Cleanup` 추가 |

### 유지

| 코드 | 이유 |
|------|------|
| `serialize_bone_pairs()` / `deserialize_bone_pairs()` | Setup에서 읽기용 |
| `BAKE_PAIRS_KEY` | bone_pairs 저장 키 |
| bone_pairs 생성 로직 (arp_ops_build.py) | Build Rig에서 사용 |

## 6. 검증된 테스트 결과 (여우 리그, 2026-04-06)

| 항목 | 결과 |
|------|------|
| FK 본 (spine/neck/head/tail) rotation | 정확 |
| FK 본 location | 정확 |
| IK 발 (c_foot_ik) rotation | 정확 (180° 뒤집힘 없음) |
| IK 발 location | 정확 |
| Pole vector | pole_parent=1로 정상 작동 |
| Root (c_root.x) | c_root.x 매핑 시 정상 |
| 다중 액션 (batch_retarget) | Action Slot 문제 없이 완료 |
| Scale FCurve | 불필요한 Scale 키프레임 없음 |

## 7. 이전 문서와의 관계

- `F12_ExactMatch.md`: **폐기**. rest-delta offset bake 방식은 더 이상 사용하지 않는다.
  git history 참조용으로 파일은 유지하되, 상단에 폐기 표시를 추가한다.
- 이전 Plan B (2-pass ARP + worldspace): **폐기**. ARP 전면 위임으로 불필요.

## 8. 기존 rest-delta 접근과의 비교

| 항목 | 기존 rest-delta bake | ARP 위임 |
|------|---------------------|----------|
| FK rotation | rest-delta 수학 (정확) | ARP _REMAP (정확) |
| **IK rotation** | **180° 뒤집힘** | **ARP 처리 (정확)** |
| FK location | rest-delta 수학 | ARP 처리 (정확) |
| IK location | 월드스페이스 | ARP 처리 (정확) |
| Pole | 별도 계산 필요 | pole_parent=1 (자동) |
| Custom 본 | 미구현 | ARP 매핑 포함 |
| 코드 복잡도 | 높음 (프레임 순회, delta 수학, euler 보정) | **최소** (매핑 변환만) |
| 외부 의존 | 없음 | ARP 리타겟 오퍼레이터 |
| 액션 순회 | 직접 루프 + Action Slot 우회 필요 | ARP batch_retarget (내부 처리) |

---
name: arp-quadruped-convert
description: >
  사족보행 동물 리그를 Auto-Rig Pro(ARP) 리그로 변환하는 자동 워크플로우.
  Blender MCP를 통해 파이프라인을 자동 실행하고, 문제 발생 시만 중단한다.
  다음 표현을 언급할 때 사용: "리그 변환 실행", "ARP로 변환", "동물 리그 컨버트",
  "사족보행 변환", "여우 변환", "quadruped convert", "rig convert 실행",
  "변환 파이프라인 실행", "리타겟 실행", "애니메이션 옮기기".
  개발/코드 수정이 아닌 실제 변환 작업을 실행할 때 이 스킬을 사용한다.
---

# 사족보행 동물 리그 → ARP 변환

Blender MCP를 통해 소스 동물 리그를 ARP(dog preset) 리그로 변환하고,
선택적으로 애니메이션을 리타겟하는 **자동 파이프라인**.

> **Phase B (Step 5~9)는 F12 ARP 네이티브 리타겟 기반이다.**
> 리타게팅 재설계 시 Phase B만 교체하면 된다.
> 구 리타게팅(F10/F11)은 2026-04-02 삭제됨 — 이 스킬과 무관.

---

## 실행 모드

**자동 모드 (기본)**: 문제 없으면 Step 1→9까지 자동 진행. 아래 조건에서만 중단:
- Step 실패 (`success: false`)
- 신뢰도 < 80% (Step 2) → 역할 수동 확인 필요
- Step 6: ARP Re-Retarget은 사용자 수동 실행 필수
- Step 9: Cleanup은 비가역이므로 항상 확인

자동 모드에서는 각 Step 결과를 한 줄로 요약하고 바로 다음으로 넘어간다.
전체 완료 후 결과를 요약 보고한다.

---

## 전제 조건

- Blender 실행 중 + BlenderMCP 애드온 연결
- ARP Rig Convert 애드온 활성화
- 소스 아마추어가 있는 .blend 파일이 열려 있음

전제 조건이 안 되면 사용자에게 안내하고 중단한다.

---

## 파이프라인 흐름

```
Phase A: Build Rig (자동)
  Step 1: 씬 확인 → 소스 있고 ARP 없으면 통과
  Step 2: Create Preview → 신뢰도 >= 80%면 통과
  Step 3: 역할 확인 → 신뢰도 >= 80%면 스킵, < 80%면 중단
  Step 4: Build Rig + 웨이트 검증 → 성공하면 통과

Phase B: Retarget (자동, 액션이 있으면 진행)
  Step 5: Setup Retarget → 성공하면 통과
  Step 6: ARP Re-Retarget → **사용자 수동** (항상 중단)
  Step 7: Copy Custom Scale → 자동
  Step 8: 결과 검증 → 자동 (오차 보고만)
  Step 9: Cleanup → **항상 확인**
```

---

## MCP 호출 패턴

모든 mcp_bridge 함수는 아래 패턴으로 호출한다:

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import <함수명>
<함수명>()
```

결과는 항상 `{"success": true/false, "data": {...}, "error": "..."}` JSON으로 반환된다.
`success: false`면 Known Issues를 먼저 확인하고, 자동 해결이 가능하면 적용 후 재시도.
자동 해결 불가면 사용자에게 에러를 보여주고 중단.

---

# Phase A: Build Rig

## Step 1: 씬 확인

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_scene_summary
mcp_scene_summary(brief=True)
```

**자동 판단:**
- 소스 아마추어 존재 (c_ 본 없는 ARMATURE) → 통과
- ARP 리그 이미 존재 → 중단 ("이미 ARP 리그가 있습니다")
- 메시 바인딩 없음 → 경고 후 계속 (웨이트 전송 불가하지만 리그 생성은 가능)

> **실패 시**: 사용자에게 씬 상태 안내.

---

## Step 2: Create Preview

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_create_preview
mcp_create_preview()
```

**자동 판단:**
- 신뢰도 >= 80% → "Preview 완료 (신뢰도 N%)" 한 줄 출력, Step 3 스킵 → Step 4로
- 신뢰도 < 80% → 중단, Step 3 역할 편집으로 전환

> **실패 시**: Step 1로 돌아가 씬 상태 재확인.

---

## Step 3: 역할 확인/수정 (신뢰도 < 80%일 때만)

### 3-1. 역할 조회

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_get_bone_roles
mcp_get_bone_roles()  # 역할 편집 시에는 compact=False (전체 본 이름 필요)
```

결과에서 `roles`와 `unmapped_bones`를 사용자에게 보여준다.

### 3-2. AI 대화형 역할 편집

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_set_bone_role
mcp_set_bone_role("본이름", "새역할")
```

사용 가능한 역할: `root`, `spine`, `neck`, `head`, `back_leg_l/r`,
`back_foot_l/r`, `front_leg_l/r`, `front_foot_l/r`, `ear_l/r`, `tail`,
`trajectory`, `unmapped`

### 3-3. 복잡한 수정 (대안)

부모 변경 등 복잡한 수정이 필요하면 Blender N-panel에서 수동 수정을 안내.

---

## Step 4: Build Rig

### 4-1. ARP 리그 생성

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_build_rig
mcp_build_rig()
```

### 4-2. 웨이트 검증

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_validate_weights
mcp_validate_weights(summary=True)
```

**자동 판단:**
- `build_rig: true` + unweighted 정점 0 → "Build Rig 완료 (N본, 웨이트 OK)" 출력, 계속
- Build Rig 실패 → Known Issues 확인 후 중단

> **실패 시**: Step 3에서 역할 매핑 재확인.

---

## Phase A → B 전환 (자동)

Phase A 완료 후:
- 씬에 액션이 1개 이상 있으면 → Phase B 자동 진행
- 액션이 없으면 → "Phase A 완료. 리타겟할 액션이 없어 종료." 출력

---

# Phase B: Retarget

## Step 5: Setup Retarget

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_setup_retarget
mcp_setup_retarget()
```

**자동 판단:** 성공하면 "Setup Retarget 완료 (N쌍 매핑)" 출력, Step 6으로.

---

## Step 6: ARP Re-Retarget (항상 중단 — 사용자 수동)

사용자에게 안내:
> "ARP Remap 패널에서 Re-Retarget 버튼을 클릭하세요. 완료되면 알려주세요."

사용자가 완료를 알리면 remap 액션 생성을 확인:

```python
import bpy
remap = [a.name for a in bpy.data.actions if '_remap' in a.name]
print(f"리타겟 결과: {len(remap)}개 액션 — {remap}")
```

remap 액션이 없으면 재안내.

---

## Step 7: Copy Custom Scale (자동)

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
import bpy
from arp_utils import ensure_object_mode, get_3d_viewport_context
ensure_object_mode()
ctx = get_3d_viewport_context()
with bpy.context.temp_override(**ctx):
    result = bpy.ops.arp_convert.copy_custom_scale()
    print(f"Copy Custom Scale: {result}")
```

---

## Step 8: 결과 검증 (자동)

### 8-1. bone_pairs 조회

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_inspect_bone_pairs
mcp_inspect_bone_pairs()
```

### 8-2. 프레임 비교

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_compare_frames
# pairs: inspect_bone_pairs 결과에서 [(src, arp), ...] 구성
# frames: 액션 프레임 범위를 5등분한 샘플
mcp_compare_frames(pairs=compare_pairs, frames=sample_frames)
```

**자동 판단:**
- 통과율 >= 80% → "검증 통과 (N/M, max 위치 Xmm, 회전 Y°)" 출력, 계속
- 통과율 < 80% → Known Issues 확인. 자동 해결 가능하면 적용 후 재검증. 불가면 중단.

---

## Step 9: Cleanup (항상 확인)

**반드시 사용자 확인 후 실행** — Cleanup은 소스 아마추어를 삭제하므로 되돌릴 수 없다.

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
import bpy
from arp_utils import ensure_object_mode, get_3d_viewport_context
ensure_object_mode()
ctx = get_3d_viewport_context()
with bpy.context.temp_override(**ctx):
    result = bpy.ops.arp_convert.cleanup()
    print(f"Cleanup: {result}")
```

---

## 완료 보고

전체 파이프라인 완료 후 한 번에 요약:

```
=== 변환 완료 ===
소스: <아마추어 이름> (<N>본)
ARP: rig (<M>본)
메시: <K>개 바인딩
액션: <L>개 리타겟
검증: 통과 <X>/<Y>, max 위치 <P>mm, 회전 <R>°
```

---

# Known Issues — 자동 해결 매뉴얼

이 섹션은 실제 변환에서 발견된 문제와 자동 해결 방법을 기록한다.
새로운 문제를 해결했을 때 여기에 추가한다.

## 허용 범위 (무시)

| 증상 | 원인 | 판단 |
|------|------|------|
| Spine_01 위치 오차 2-3mm | ARP 리타겟 spine 오프셋 | 정상 — 허용 범위로 무시 |
| root(pelvis) 회전 1.03° | ARP 내부 offset | 정상 — 허용 범위로 무시 |
| rigAction_remap rename 충돌 | ARP 자체 생성 액션과 이름 충돌 | 정상 — 스킵해도 무방 |

## 자동 해결 가능

| 증상 | 원인 | 자동 해결 |
|------|------|----------|
| Root 본 unmapped → cc_ 생성 | root 위 trajectory 본 미감지 | trajectory 역할이 2026-04-09 추가됨. 자동 감지 동작. 수동 지정: `mcp_set_bone_role("Root", "trajectory")` |
| tail 오차 > 5° | tail_master COPY_ROTATION 활성 | `mcp_setup_retarget()`이 자동 mute. 검증 실패 시 수동 확인: ARP Pose 모드에서 tail_master 본의 constraint 확인 |
| Build Rig 후 mode가 REST | ARP match_to_rig 부작용 | 코드에서 자동 POSE 복원 구현됨. 검증 시 REST면: `bpy.context.object.data.pose_position = 'POSE'` |
| 웨이트 전송 후 빈 vertex group | 소스에 빈 그룹 (Center, body 등) | 정상 — 컨트롤/도우미 본 그룹. 실제 deform 그룹만 확인 |

## 중단 필요 (자동 해결 불가)

| 증상 | 원인 | 대응 |
|------|------|------|
| 신뢰도 < 70% | 비표준 본 이름 | 중단 → Step 3에서 수동 역할 편집 |
| ARP 아마추어 생성 실패 | ARP 애드온 미설치/비활성 | 중단 → 사용자에게 ARP 설치 안내 |
| MCP 연결 끊김 | BlenderMCP 재연결 필요 | 중단 → Blender에서 애드온 재연결 |
| 전체 본 오차 > 10mm | bones_map_v2 매핑 오류 | 중단 → Step 3 역할 재확인 또는 ARP Remap UI에서 수동 수정 |
| ref 본 정렬 실패 | 역할 매핑 부정확 | 중단 → Step 3에서 역할/부모 확인 |

---

## 문제 기록 방법

변환 중 새로운 문제를 해결했을 때:

1. 위 Known Issues 테이블의 적절한 섹션에 행 추가
2. **증상**: 에러 메시지 또는 관찰된 현상 (검색 가능하게)
3. **원인**: 근본 원인 (왜 발생하는지)
4. **자동 해결 / 판단 / 대응**: 다음에 같은 상황에서 취할 행동

이 테이블은 파이프라인 실행 중 에러 발생 시 자동으로 참조된다.

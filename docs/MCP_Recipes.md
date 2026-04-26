# MCP 브릿지 사용 레시피

BlenderMCP 브릿지(`scripts/mcp_bridge.py`)는 Claude가 Blender를 직접 제어·검증하기 위한 고수준 함수를 제공한다. 이 문서는 언제 브릿지를 쓰는지, 어떤 함수가 있는지, 그리고 자주 쓰이는 조합 레시피를 정리한다.

## 언제 MCP 브릿지를 쓰는가

- Blender GUI 클릭-수정-재시도 사이클의 비용이 크다고 느껴질 때
- Blender 상태를 즉석에서 조회·수정·검증하고 싶을 때
- 숫자 기반 검증(프레임별 위치 비교, 통계)을 원할 때
- 반복적 확인 작업을 자동화하고 싶을 때

## 호출 패턴

```python
import sys; sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
from mcp_bridge import mcp_scene_summary
mcp_scene_summary()
```

모든 함수는 JSON을 stdout으로 출력하며, `success: true|false` 키로 결과를 표시한다.

모듈을 수정한 뒤 재검증할 때는 `importlib.reload`로 캐시를 비운 뒤 호출한다:

```python
import sys, importlib
sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
for m in ["skeleton_analyzer", "arp_utils", "weight_transfer_rules", "mcp_verify", "mcp_bridge"]:
    if m in sys.modules:
        importlib.reload(sys.modules[m])
```

## 함수 인덱스

| 함수 | 용도 | 주요 파라미터 |
|------|------|-------------|
| `mcp_scene_summary()` | 씬 요약 (armatures, meshes, actions) | 없음 |
| `mcp_create_preview()` | Preview Armature 생성 | 없음 |
| `mcp_build_rig()` | ARP Build Rig 실행 | 없음 |
| `mcp_run_regression(fixture_path)` | Fixture 기반 회귀 테스트 | fixture 경로 |
| `mcp_get_bone_roles()` | Preview 본 역할 조회 | 없음 |
| `mcp_set_bone_role(bone, role)` | 개별 본 역할 변경 | 본명, 역할 |
| `mcp_validate_weights()` | 웨이트 커버리지 검증 | 없음 |
| `mcp_bake_animation()` | F12 COPY_TRANSFORMS 베이크 | 없음 |
| `mcp_inspect_bone_pairs(role_filter)` | bone_pairs 디코드 + 역할 필터 | `None` / str / list |
| `mcp_compare_frames(pairs, frames, action_name, detailed=False)` | 소스-ARP 월드 위치 비교 | 본 쌍, 프레임, 액션명, 상세 플래그 |
| `mcp_inspect_preset_bones(preset, pattern)` | ARP 프리셋 본 이름 조회 | 프리셋명, 정규식 |

## 로그 레벨 / 토큰 최적화

MCP 브릿지 함수는 내부적으로 `arp_utils.quiet_logs()` 컨텍스트를 사용해
Blender 연산 중 발생하는 INFO/DEBUG 레벨 로그를 자동 억제한다.
WARN / ERROR 만 출력되므로 Claude 컨텍스트 소비가 대폭 줄어든다.
(Blender GUI 버튼 경로는 `set_log_level`을 호출하지 않으므로 시스템 콘솔
출력은 변함없음.)

디버깅이 필요할 때 임계값을 DEBUG로 낮춰 호출한다:

```python
import arp_utils
arp_utils.set_log_level("DEBUG")     # 모든 로그 복원
from mcp_bridge import mcp_build_rig
mcp_build_rig()
arp_utils.set_log_level("INFO")      # 기본값 복원
```

`mcp_compare_frames`의 `detailed` 파라미터:

```python
# 기본 (compact): per_frame 배열과 report 문자열 생략
mcp_compare_frames(pairs, frames, action_name="walk")

# 전체 데이터 (per-frame 배열 + 포맷 보고서)
mcp_compare_frames(pairs, frames, action_name="walk", detailed=True)
```

7쌍 × 7프레임 호출 기준 compact 모드는 full 모드 대비 약 85% 토큰 절약.

## 단일 함수 예시 (신규 함수 3개)

### mcp_inspect_bone_pairs

```python
from mcp_bridge import mcp_inspect_bone_pairs
mcp_inspect_bone_pairs(role_filter=["back_leg_l", "back_leg_r", "back_foot_l", "back_foot_r"])
```

실제 출력 (여우 리그 F12 bake 상태, 2026-04-05):

```json
{
  "success": true,
  "data": {
    "arp_armature": "rig",
    "total_pairs": 26,
    "filtered_count": 4,
    "role_filter": ["back_leg_l", "back_leg_r", "back_foot_l", "back_foot_r"],
    "pairs": [
      {"source": "DEF-thigh_L", "target": "c_thigh_b.l", "is_custom": false, "role": "back_leg_l"},
      {"source": "DEF-toe_L",   "target": "c_foot_fk.l", "is_custom": false, "role": "back_foot_l"},
      {"source": "DEF-thigh_R", "target": "c_thigh_b.r", "is_custom": false, "role": "back_leg_r"},
      {"source": "DEF-toe_R",   "target": "c_foot_fk.r", "is_custom": false, "role": "back_foot_r"}
    ]
  }
}
```

역할 필터는 None(전체), 문자열("back_leg_l"), 리스트(여러 역할) 세 형태 지원.

### mcp_compare_frames

```python
from mcp_bridge import mcp_compare_frames
mcp_compare_frames(
    pairs=[
        ("DEF-thigh_L", "c_thigh_b.l"),
        ("DEF-thigh_R", "c_thigh_b.r"),
        ("DEF-toe_L",   "c_foot_fk.l"),
        ("DEF-toe_R",   "c_foot_fk.r"),
    ],
    frames=[0, 12, 24, 36, 48, 60, 72],
    action_name="walk"
)
```

실제 출력 (여우 walk 액션, 2026-04-05):

```json
{
  "success": true,
  "data": {
    "action": "walk",
    "frame_count": 7,
    "pair_count": 4,
    "overall_max_err": 2.897e-07,
    "overall_mean_err": 1.935e-07,
    "results": [
      {"src": "DEF-thigh_L", "arp": "c_thigh_b.l", "max_err": 2.68e-07, "mean_err": 2.26e-07},
      {"src": "DEF-thigh_R", "arp": "c_thigh_b.r", "max_err": 1.69e-07, "mean_err": 1.03e-07},
      {"src": "DEF-toe_L",   "arp": "c_foot_fk.l", "max_err": 2.33e-07, "mean_err": 1.93e-07},
      {"src": "DEF-toe_R",   "arp": "c_foot_fk.r", "max_err": 2.90e-07, "mean_err": 2.53e-07}
    ],
    "report": "src_bone                  -> arp_bone                       |   max_err |  mean_err\n-----------------------------------------------------------------------------------\nDEF-thigh_L               -> c_thigh_b.l                    |   0.00000 |   0.00000\n..."
  }
}
```

최대 오차 0.29 μm — 부동소수 노이즈 수준. 이전 F12 블로커의 0.186m(186,000 μm) 대비 **640,000배 개선**.

### mcp_inspect_preset_bones

```python
from mcp_bridge import mcp_inspect_preset_bones
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_thigh_b")
```

실제 출력 (dog 프리셋, 2026-04-05):

```json
{
  "success": true,
  "data": {
    "preset": "dog",
    "preset_path": "C:\\Users\\DWLEE\\AppData\\Roaming\\Blender Foundation\\Blender\\4.5\\extensions\\user_default\\auto_rig_pro\\armature_presets\\dog.blend",
    "total_bones": 468,
    "pattern": "^c_thigh_b",
    "matched_count": 4,
    "matched_bones": [
      "c_thigh_b.l",
      "c_thigh_b.r",
      "c_thigh_b_dupli_001.l",
      "c_thigh_b_dupli_001.r"
    ]
  }
}
```

`_append_arp` 대신 `bpy.data.libraries.load`를 사용하므로 MCP 헤드리스 컨텍스트에서도 동작한다.

## 조합 레시피

### 레시피 A: Bake 결과 정확성 검증 (F12 Task 6 재현)

목적: Build Rig + Bake Animation 후 소스와 ARP 리그의 매핑이 프레임별로 올바른지 수치로 확인.

```python
from mcp_bridge import mcp_inspect_bone_pairs, mcp_compare_frames

# Step 1: 매핑 확인 — 뒷다리가 올바른 컨트롤러로 가는지
bone_pairs_result = mcp_inspect_bone_pairs(
    role_filter=["back_leg_l", "back_leg_r", "back_foot_l", "back_foot_r"]
)

# Step 2: 프레임별 위치 비교 — 수치 검증
mcp_compare_frames(
    pairs=[
        ("DEF-thigh_L", "c_thigh_b.l"),
        ("DEF-thigh_R", "c_thigh_b.r"),
        ("DEF-toe_L",   "c_foot_fk.l"),
        ("DEF-toe_R",   "c_foot_fk.r"),
    ],
    frames=[0, 12, 24, 36, 48, 60, 72],
    action_name="walk"
)
```

F12 back_leg shoulder 작업에서 이 레시피로 leg 오차 0.186m → 2.9e-07m(0.29 μm)를 확인했다.

### 레시피 B: 코드 수정 후 프리셋 본 이름 재확인 (F12 c_toes_fk 발견 재현)

목적: 코드에 하드코딩된 본 이름(`c_toes.l`, `c_foot_fk.l` 등)이 실제 ARP 프리셋에 존재하는지 확인.

```python
from mcp_bridge import mcp_inspect_preset_bones

# 모든 c_toes* 본 조회
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_toes")
# → c_toes_fk.l/r 등만 반환. c_toes.l은 존재하지 않음

# 모든 c_foot* 본 조회
mcp_inspect_preset_bones(preset="dog", pattern=r"^c_foot")
```

F12 작업에서 이 레시피로 `c_toes.l`이 dog 프리셋에 없고 `c_toes_fk.l`만 있다는 사실을 확인했다. `ARP_CTRL_MAP` 정정 계기.

### 레시피 C: 코드 수정 후 빠른 재검증

목적: `skeleton_analyzer.py` 또는 `arp_convert_addon.py`를 수정한 뒤 즉시 확인.

```python
import sys, importlib
sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
for m in ["skeleton_analyzer", "arp_utils", "weight_transfer_rules", "mcp_verify", "mcp_bridge"]:
    if m in sys.modules:
        importlib.reload(sys.modules[m])

from mcp_bridge import mcp_build_rig, mcp_inspect_bone_pairs
mcp_build_rig()
mcp_inspect_bone_pairs()
```

각 브릿지 함수는 호출 시 내부적으로 `_reload()`를 실행하지만, 파이썬 모듈 자체(`mcp_bridge`나 `mcp_verify`)를 새로 만들거나 수정했으면 위와 같이 명시적으로 리로드해야 한다.

## F12 사례 요약

2026-04-05 F12 back_leg shoulder 작업(커밋 2a07d78/8dce2a0/5d6b301)에서 이 레시피들이 다음과 같이 쓰였다:

- **레시피 A**: Task 6에서 `walk` 액션의 7개 프레임에 대해 뒷다리 오차 검증. 이전 0.186m → 현재 2.9e-07m로 해소 확인.
- **레시피 B**: Task 5에서 `c_toes.l`이 존재하지 않고 `c_toes_fk.l`이 실제 이름임을 확인. `ARP_CTRL_MAP` 정정 계기.
- **레시피 C**: 이번 sub-project ② 자체가 이 사이클의 자동화를 목표로 함.

이전에는 매번 raw `execute_blender_code`로 즉석 루프를 작성했다. 이제는 함수 호출 1~2줄로 같은 검증이 가능하다.

관련 문서:
- 스펙: `docs/superpowers/specs/archive/2026-04-05-mcp-feedback-loop-design.md`
- 플랜: `docs/superpowers/plans/archive/2026-04-05-mcp-feedback-loop.md`
- 이전 F12 작업: `docs/superpowers/specs/archive/2026-04-05-f12-back-leg-shoulder-fix-design.md`

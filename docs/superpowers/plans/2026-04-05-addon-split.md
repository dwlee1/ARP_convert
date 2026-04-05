# arp_convert_addon.py 분할 + 레거시 정리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/arp_convert_addon.py` 2969줄을 12개 모듈로 분할하고 레거시 5개 파일(1501줄)을 삭제해 코드 건강과 작업 효율을 개선한다. 행동 변화는 0 (순수 구조 리팩터링).

**Architecture:** Phase별 13개 커밋. 의존성 역방향(bottom-up)으로 추출: (1) leaf helpers (weight_xfer, foot_guides, fixture_io, cc_bones, build_helpers) → (2) props/ui → (3) operators. 매 커밋 후 Sub-project ②의 MCP 체크포인트로 bone_pairs + 프레임별 위치 비교를 실행해 행동 무결성을 검증.

**Tech Stack:** Python 3.11, pytest, ruff, Blender 4.5 + Auto-Rig Pro (dog preset), BlenderMCP 브릿지 (`mcp_inspect_bone_pairs`, `mcp_compare_frames`).

**Spec:** `docs/superpowers/specs/2026-04-05-addon-split-design.md`

**브랜치**: `feat/addon-split` (새로 생성)

**선결 조건**: Sub-project ①(Workflow 규칙)과 ②(MCP 피드백 루프)가 이미 구현 완료되어 master에 머지됨. Sub-project ②의 `mcp_inspect_bone_pairs` / `mcp_compare_frames` 함수가 동작해야 이 플랜의 체크포인트가 작동한다.

---

## 사전 조건 검증

- [ ] **Pre-flight 1: Sub-project ② 완료 확인**

Run:
```
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, 'scripts'); import mcp_bridge; assert hasattr(mcp_bridge, 'mcp_inspect_bone_pairs'); assert hasattr(mcp_bridge, 'mcp_compare_frames'); assert hasattr(mcp_bridge, 'mcp_inspect_preset_bones'); print('OK')"
```
Expected: `OK`. 없으면 Sub-project ②를 먼저 완료.

- [ ] **Pre-flight 2: 브랜치 생성 + 테스트 baseline**

```bash
git checkout -b feat/addon-split
.venv/Scripts/python.exe -m pytest tests/ -q
```
Expected: **120 passed**.

- [ ] **Pre-flight 3: Blender에 ARP 리그 + baked walk 액션 준비**

Blender가 실행 중이고 BlenderMCP 연결 상태여야 한다. 여우 `Armature` 소스 + `rig` ARP 아마추어 + `walk` / `walk_arp` 액션이 있어야 체크포인트 검증 가능.

MCP로 확인:
```python
from mcp_bridge import mcp_scene_summary
mcp_scene_summary()
```
결과에 armature 2개, actions 중 `walk`, `walk_arp` 포함되어야 함. 없으면 사용자에게 Build Rig + Bake 선행 요청.

---

## 공통 체크포인트 절차 (Common Checkpoint Procedure)

각 Task의 Step "체크포인트 실행"은 아래 절차를 그대로 수행한다.

### CP.1: pytest + ruff

```
.venv/Scripts/python.exe -m pytest tests/ -q
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```
Expected: 120 passed, ruff clean.

### CP.2: Blender 모듈 리로드 (MCP)

```python
import sys, importlib
sys.path.insert(0, r"C:\Users\DWLEE\ARP_convert\scripts")
for m in [
    "skeleton_analyzer", "arp_utils", "weight_transfer_rules",
    "mcp_verify", "mcp_bridge",
    # 신규 모듈들 (해당 Task까지 존재하는 것만)
    "arp_weight_xfer", "arp_foot_guides", "arp_fixture_io",
    "arp_cc_bones", "arp_build_helpers",
    "arp_props", "arp_ui",
    "arp_ops_preview", "arp_ops_roles",
    "arp_ops_bake_regression", "arp_ops_build",
    "arp_convert_addon",
]:
    if m in sys.modules:
        importlib.reload(sys.modules[m])
```

아직 생성되지 않은 모듈은 `sys.modules`에 없으므로 자동 skip됨. 애드온 자체 리로드 후 unregister → register가 필요할 수 있음 — 이 경우 Blender GUI에서 ARP Convert 애드온을 Off → On 토글로 대체.

### CP.3: Build Rig 재실행 + bone_pairs 비교

```python
from mcp_bridge import mcp_build_rig, mcp_inspect_bone_pairs
mcp_build_rig()
mcp_inspect_bone_pairs()  # role_filter 없이 전체
```

결과의 `pairs` 배열이 baseline과 **bit-for-bit 일치**해야 한다 (순서 포함). baseline은 Phase 0의 Task 1에서 `docs/_scratch/baseline_bone_pairs.json`으로 저장한 것.

비교 스크립트:
```python
import json
with open(r"C:\Users\DWLEE\ARP_convert\docs\_scratch\baseline_bone_pairs.json") as f:
    baseline = json.load(f)
# mcp_inspect_bone_pairs 결과를 current로 저장
# sorted(baseline["pairs"]) == sorted(current["pairs"]) 이어야 한다
```

### CP.4: 프레임별 위치 비교 (F12 회귀 방지)

```python
from mcp_bridge import mcp_compare_frames
mcp_compare_frames(
    pairs=[
        ("DEF-thigh_L", "c_thigh_b.l"),
        ("DEF-thigh_R", "c_thigh_b.r"),
        ("DEF-toe_L", "c_foot_fk.l"),
        ("DEF-toe_R", "c_foot_fk.r"),
    ],
    frames=[0, 24, 48, 72],
    action_name="walk"
)
```

`overall_max_err` 가 **3e-06 m 이하**여야 한다 (baseline 2.9e-07 m 수준 유지, 약간의 허용 여유). 초과하면 해당 단계 revert.

### CP 실패 시 대응

1. 실패 원인 확인 (pytest 메시지 / MCP 에러 / 비교 diff)
2. 해당 Task 범위에서 수정 가능하면 수정 후 체크포인트 재실행
3. 수정 불가능하면 `git reset --hard HEAD~1`로 revert, 플랜 재검토

---

## Task 1: Phase 0 — Baseline 캡처 + 레거시 5개 삭제 (커밋 1)

**Files:**
- Create: `docs/_scratch/baseline_bone_pairs.json` (gitignored)
- Create: `docs/_scratch/baseline_compare.json` (gitignored)
- Modify: `.gitignore` — `docs/_scratch/` 추가
- Delete: `scripts/01_create_arp_rig.py`, `scripts/rigify_to_arp.py`, `scripts/bone_mapping.py`, `scripts/diagnose_arp_operators.py`, `scripts/inspect_rig.py`
- Modify: `CLAUDE.md` — 파일 맵에서 레거시 항목 제거
- Modify: `AGENTS.md` — 파일 맵에서 레거시 항목 제거
- Modify: `scripts/pipeline_runner.py:4` — docstring에서 "01_create_arp_rig" 언급 제거
- Modify: `docs/ProjectPlan.md:122` — "레거시 파일... 확인한 뒤 수정한다" 삭제

- [ ] **Step 1: `.gitignore`에 `docs/_scratch/` 추가**

Edit `.gitignore`:
- old_string:
```
# 가상환경
.venv/
```
- new_string:
```
# 가상환경
.venv/

# 리팩터링 baseline 임시 파일
docs/_scratch/
```

- [ ] **Step 2: baseline 디렉토리 생성 + bone_pairs 캡처**

```bash
mkdir -p docs/_scratch
```

MCP 실행 (Blender 필요):
```python
import json
from mcp_bridge import mcp_inspect_bone_pairs
# mcp_inspect_bone_pairs는 stdout으로 JSON을 print하므로
# 직접 호출하고 결과를 파일에 쓰도록 즉석 헬퍼 작성:

import sys, io
buf = io.StringIO()
old_stdout = sys.stdout
sys.stdout = buf
try:
    mcp_inspect_bone_pairs()
finally:
    sys.stdout = old_stdout

result = json.loads(buf.getvalue().strip().split('\n')[-1])
with open(r"C:\Users\DWLEE\ARP_convert\docs\_scratch\baseline_bone_pairs.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=True)
print(f"saved: {len(result['data']['pairs'])} pairs")
```

Expected: `saved: 26 pairs` (또는 현재 씬의 실제 개수).

- [ ] **Step 3: 프레임별 비교 baseline 캡처**

```python
import json, sys, io
from mcp_bridge import mcp_compare_frames
buf = io.StringIO()
old_stdout = sys.stdout
sys.stdout = buf
try:
    mcp_compare_frames(
        pairs=[
            ("DEF-thigh_L", "c_thigh_b.l"),
            ("DEF-thigh_R", "c_thigh_b.r"),
            ("DEF-toe_L", "c_foot_fk.l"),
            ("DEF-toe_R", "c_foot_fk.r"),
        ],
        frames=[0, 24, 48, 72],
        action_name="walk"
    )
finally:
    sys.stdout = old_stdout

result = json.loads(buf.getvalue().strip().split('\n')[-1])
with open(r"C:\Users\DWLEE\ARP_convert\docs\_scratch\baseline_compare.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2, sort_keys=True)
print(f"saved: overall_max_err={result['data']['overall_max_err']:.2e}")
```

Expected: `saved: overall_max_err=2.9e-07` (또는 유사한 μm 수준).

- [ ] **Step 4: 레거시 5개 파일 삭제**

```bash
git rm scripts/01_create_arp_rig.py
git rm scripts/rigify_to_arp.py
git rm scripts/bone_mapping.py
git rm scripts/diagnose_arp_operators.py
git rm scripts/inspect_rig.py
```

- [ ] **Step 5: `CLAUDE.md` 파일 맵에서 레거시 행 제거**

Edit `CLAUDE.md`:
- old_string:
```
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 (Build Rig까지) |
| `scripts/03_batch_convert.py` | 배치 실행 경로 |
| `scripts/01_create_arp_rig.py` | [레거시] |
| `scripts/rigify_to_arp.py` | [레거시] |

레거시 파일은 현재 메인 경로와 실제 사용 여부를 확인한 뒤 수정한다.
```
- new_string:
```
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 (Build Rig까지) |
| `scripts/03_batch_convert.py` | 배치 실행 경로 |
```

- [ ] **Step 6: `AGENTS.md` 파일 맵에서 레거시 행 제거**

Read `AGENTS.md` 로 현재 파일 맵 섹션(대략 line 20-35)을 확인한 뒤, 레거시 2개 행(`01_create_arp_rig.py`, `rigify_to_arp.py`)을 Edit로 제거. 정확한 old_string은 Read 결과 그대로.

- [ ] **Step 7: `scripts/pipeline_runner.py` docstring 수정**

Read `scripts/pipeline_runner.py` offset=1 limit=15.

Edit `scripts/pipeline_runner.py`:
- old_string (line 4 부근, 정확한 내용은 Read 결과 사용):
```
단일 .blend 파일에 대해 01_create_arp_rig을 실행하고 결과를 저장.
```
- new_string:
```
단일 .blend 파일에 대해 ARP Convert Build Rig 경로를 실행하고 결과를 저장.
```

- [ ] **Step 8: `docs/ProjectPlan.md`의 레거시 언급 삭제**

Read `docs/ProjectPlan.md` offset=118 limit=10로 line 122 근처 확인.

Edit `docs/ProjectPlan.md`:
- old_string:
```
레거시 파일 (`01_create_arp_rig.py`, `rigify_to_arp.py`)은 현재 메인 경로와 실제 사용 여부를 확인한 뒤 수정한다.
```
- new_string: (빈 문자열 또는 주변 문맥에 맞게 조정)

위 문장 한 줄만 삭제. 주변 bullet이나 섹션을 건드리지 않음.

- [ ] **Step 9: pytest + ruff (체크포인트 CP.1만)**

```
.venv/Scripts/python.exe -m pytest tests/ -q
.venv/Scripts/python.exe -m ruff check scripts/ tests/
```
Expected: 120 passed, ruff clean.

- [ ] **Step 10: 커밋**

```bash
git add .gitignore CLAUDE.md AGENTS.md scripts/pipeline_runner.py docs/ProjectPlan.md
git commit -m "$(cat <<'EOF'
chore: 레거시 스크립트 5개 삭제 + 문서 파일 맵 정리

삭제 대상 (모두 활성 코드 경로에서 import 없음, git history에 보존):
- scripts/01_create_arp_rig.py (332줄)
- scripts/rigify_to_arp.py (738줄)
- scripts/bone_mapping.py (160줄 — 리타게팅 삭제 후 고아)
- scripts/diagnose_arp_operators.py (179줄)
- scripts/inspect_rig.py (92줄)

총 1501줄 제거. Sub-project ③ addon 분할 사전 정리.

부수 업데이트: CLAUDE.md / AGENTS.md 파일 맵, pipeline_runner.py docstring,
ProjectPlan.md 레거시 언급, .gitignore에 docs/_scratch/ 추가.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md
EOF
)"
```

---

## Task 2: Phase 1.1 — `arp_weight_xfer.py` 추출 (커밋 2)

**Files:**
- Create: `scripts/arp_weight_xfer.py`
- Modify: `scripts/arp_convert_addon.py` (해당 함수 제거 + import 추가)

**이동 대상 함수** (현재 `arp_convert_addon.py` 안):
- `_build_position_weight_map` (line ~629)
- `_transfer_all_weights` (line ~674)
- `_map_source_bone_to_target_bone` (line ~766)

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=625 limit=50** — `_build_position_weight_map` 시작 확인

- [ ] **Step 2: Read `scripts/arp_convert_addon.py` offset=670 limit=100** — `_transfer_all_weights` 확인

- [ ] **Step 3: Read `scripts/arp_convert_addon.py` offset=760 limit=15** — `_map_source_bone_to_target_bone` 확인

- [ ] **Step 4: `scripts/arp_weight_xfer.py` 생성**

Create file with this structure:
```python
"""
arp_convert_addon에서 분리한 웨이트 전송 로직.

이 모듈은 소스 → ARP 리그로 웨이트를 전송하는 함수들을 담는다.
Blender bpy에 의존하지만 외부 인터페이스는 3개 함수뿐.
"""

import bpy

from arp_utils import log


# 여기에 3개 함수 본문을 그대로 붙여넣는다:
# - _build_position_weight_map
# - _transfer_all_weights
# - _map_source_bone_to_target_bone
```

구체 본문은 Step 1-3에서 Read한 내용을 그대로 복사한다. 함수 내부의 다른 private helper 참조(예: `_distance_sq`, `log`)가 있으면 그것들도 함께 가져오거나 `arp_convert_addon`에서 import하도록 조정한다.

**의존성 처리**:
- `_distance_sq`는 `_build_position_weight_map`에서 사용 → `arp_convert_addon.py`에 남아 있음 → `arp_weight_xfer.py`에서 `from arp_convert_addon import _distance_sq`는 순환 import가 된다. 해결: `_distance_sq`를 Task 6 `arp_build_helpers.py`로 미리 이동하거나, `arp_weight_xfer.py` 내부에 로컬 복사본 배치. **선택: `_distance_sq`는 작은 유틸이므로 `arp_weight_xfer.py`에 inline 복사**. 추후 Task 6에서 `arp_build_helpers.py`로 옮길 때 중복 제거.
- `log`는 `arp_utils.log`에서 온 것으로 추정 → `from arp_utils import log` 사용

- [ ] **Step 5: `arp_convert_addon.py`에서 이동된 함수 제거**

3개 함수 정의를 모두 Edit로 삭제. 각 함수의 `def ...:` 부터 다음 함수 `def` 직전까지 통째로 제거.

- [ ] **Step 6: `arp_convert_addon.py` 상단에 import 추가**

Edit `scripts/arp_convert_addon.py`:
- old_string: `def _ensure_scripts_path():` 위의 import 블록 또는 `# scripts/ 경로 설정` 섹션 뒤
- new_string: 기존 import 뒤에 추가:
```python
# 분리된 helper 모듈 import (scripts/ 경로 설정 이후)
```

실제로는 `_ensure_scripts_path()`가 호출된 뒤에 import가 실행되어야 하므로, `register()` 함수 안에서 import하거나 모듈 최상단의 `sys.path` 조작 뒤에 import한다. 기존 패턴 확인 후 맞춤.

구체적인 방법: `_ensure_scripts_path()` 호출 뒤, class 정의 전에 다음 블록을 삽입:
```python
_ensure_scripts_path()

# 분리된 helper 모듈 import (scripts/ 경로 설정 후)
from arp_weight_xfer import (
    _build_position_weight_map,
    _transfer_all_weights,
    _map_source_bone_to_target_bone,
)
```

이렇게 하면 `ARPCONV_OT_BuildRig.execute` 내부의 bare 이름 호출(예: `_transfer_all_weights(...)`)이 여전히 동작한다.

- [ ] **Step 7: `_reload_modules()` 업데이트**

Edit `scripts/arp_convert_addon.py`:
- old_string:
```python
def _reload_modules():
    """개발 중 모듈 리로드"""
    import importlib

    for mod_name in ["skeleton_analyzer", "arp_utils", "weight_transfer_rules"]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
```
- new_string:
```python
def _reload_modules():
    """개발 중 모듈 리로드"""
    import importlib

    for mod_name in [
        "skeleton_analyzer",
        "arp_utils",
        "weight_transfer_rules",
        "arp_weight_xfer",
    ]:
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
```

- [ ] **Step 8: 체크포인트 CP.1~CP.4 실행** — pytest, ruff, MCP 모듈 리로드, Build Rig 재실행, bone_pairs 비교, 프레임 비교

- [ ] **Step 9: 커밋**

```bash
git add scripts/arp_weight_xfer.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_weight_xfer.py 추출 — 웨이트 전송 3개 함수 분리

_build_position_weight_map, _transfer_all_weights, _map_source_bone_to_target_bone
을 scripts/arp_weight_xfer.py로 이동. _distance_sq는 순환 import 회피 위해
임시로 로컬 복사본 유지 (Task 6에서 arp_build_helpers.py로 통합 예정).

arp_convert_addon.py의 _reload_modules에 arp_weight_xfer 추가.

MCP 체크포인트: bone_pairs 일치 + leg 오차 2.9e-07m 유지.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 3: Phase 1.2 — `arp_foot_guides.py` 추출 (커밋 3)

**Files:**
- Create: `scripts/arp_foot_guides.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `_set_preview_pose_bone_role` (line ~1120)
- `_create_foot_guides_for_role` (line ~1129)
- `_detect_guide_kind` (line ~1339)
- `_detect_guide_side` (line ~1347)
- `_guide_default_local_head` (line ~1355)
- `_is_default_foot_guide` (line ~1363)
- `_compute_auto_foot_guide_world` (line ~1374)

- [ ] **Step 1: 각 함수의 정확한 시작/끝 Read로 확인**

Read `scripts/arp_convert_addon.py` offset=1115 limit=300 — 7개 함수 전체 범위 확인.

- [ ] **Step 2: `scripts/arp_foot_guides.py` 생성**

```python
"""
arp_convert_addon에서 분리한 foot guide 로직.

Preview Armature의 foot 역할 본에 대해 heel/bank 가이드 본을 자동
배치하고 감지하는 함수들을 담는다.
"""

import bpy

from arp_utils import log


# 7개 함수 본문을 그대로 붙여넣는다.
```

함수 순서는 현재 파일의 순서를 유지한다 (의존성이 위→아래 참조 패턴).

- [ ] **Step 3: 함수 간 의존성 확인**

7개 함수 중 다른 함수를 호출하는 것들이 있으면 그 관계가 같은 파일 안에서 해결되는지 확인. 외부 의존(예: `arp_utils.log`, `mathutils.Vector`)이 있으면 import 추가.

- [ ] **Step 4: `arp_convert_addon.py`에서 제거**

7개 함수 정의를 모두 삭제.

- [ ] **Step 5: `arp_convert_addon.py`에 import 추가**

Edit, 이전 Task의 import 뒤에 append:
- old_string:
```python
from arp_weight_xfer import (
    _build_position_weight_map,
    _transfer_all_weights,
    _map_source_bone_to_target_bone,
)
```
- new_string:
```python
from arp_weight_xfer import (
    _build_position_weight_map,
    _transfer_all_weights,
    _map_source_bone_to_target_bone,
)
from arp_foot_guides import (
    _set_preview_pose_bone_role,
    _create_foot_guides_for_role,
    _detect_guide_kind,
    _detect_guide_side,
    _guide_default_local_head,
    _is_default_foot_guide,
    _compute_auto_foot_guide_world,
)
```

- [ ] **Step 6: `_reload_modules()`에 `arp_foot_guides` 추가**

Edit — `_reload_modules` 안의 모듈 리스트에 `"arp_foot_guides"` 추가 (기존 4개 뒤).

- [ ] **Step 7: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 8: 커밋**

```bash
git add scripts/arp_foot_guides.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_foot_guides.py 추출 — foot guide 7개 함수 분리

_set_preview_pose_bone_role, _create_foot_guides_for_role, _detect_guide_kind,
_detect_guide_side, _guide_default_local_head, _is_default_foot_guide,
_compute_auto_foot_guide_world을 scripts/arp_foot_guides.py로 이동.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 4: Phase 1.3 — `arp_fixture_io.py` 추출 (커밋 4)

**Files:**
- Create: `scripts/arp_fixture_io.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `_resolve_project_root` (line ~1207)
- `_resolve_regression_path` (line ~1224)
- `_default_regression_report_dir` (line ~1232)
- `_load_regression_fixture` (line ~1236)
- `_apply_fixture_roles` (line ~1270)

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=1205 limit=150** — 5개 함수 본문 확인

- [ ] **Step 2: `scripts/arp_fixture_io.py` 생성**

```python
"""
arp_convert_addon에서 분리한 regression fixture I/O 로직.

프로젝트 루트 해석, fixture JSON 로드, preview 본 역할 적용 함수들을
담는다.
"""

import json
import os

import bpy

from arp_utils import log


# 5개 함수 본문 그대로.
```

- [ ] **Step 3: `arp_convert_addon.py`에서 5개 함수 제거**

- [ ] **Step 4: import 추가 + `_reload_modules` 업데이트**

Edit — 이전 Task의 import 뒤에:
```python
from arp_fixture_io import (
    _resolve_project_root,
    _resolve_regression_path,
    _default_regression_report_dir,
    _load_regression_fixture,
    _apply_fixture_roles,
)
```

`_reload_modules` 리스트에 `"arp_fixture_io"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_fixture_io.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_fixture_io.py 추출 — regression fixture I/O 5개 함수 분리

_resolve_project_root, _resolve_regression_path, _default_regression_report_dir,
_load_regression_fixture, _apply_fixture_roles을 scripts/arp_fixture_io.py로 이동.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 5: Phase 1.4 — `arp_cc_bones.py` 추출 (커밋 5)

**Files:**
- Create: `scripts/arp_cc_bones.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `_make_cc_bone_name` (line ~83)
- `_should_connect_cc_bone` (line ~154)
- `_ensure_nonzero_bone_length` (line ~168)
- `_create_cc_bones_from_preview` (line ~531)
- `_copy_constraint_settings` (line ~772)
- `_copy_custom_bone_constraints` (line ~860)

- [ ] **Step 1: Read 각 함수 본문 확인**

개별 Read 호출로 6개 함수의 시작/끝 확인. (5회 Read 호출)

- [ ] **Step 2: `scripts/arp_cc_bones.py` 생성**

```python
"""
arp_convert_addon에서 분리한 cc (custom bone) 생성 및 constraint 로직.

Preview의 unmapped 본을 ARP 리그에 커스텀 본으로 생성하고, 소스
constraint를 복사하는 함수들을 담는다.
"""

import bpy

from arp_utils import log


# 6개 함수 본문 그대로.
```

함수 간 호출 관계 주의:
- `_create_cc_bones_from_preview`가 `_make_cc_bone_name`, `_should_connect_cc_bone`, `_ensure_nonzero_bone_length`을 호출 → 모두 같은 파일 안이므로 OK
- `_copy_custom_bone_constraints`가 `_copy_constraint_settings`을 호출 → OK

- [ ] **Step 3: `arp_convert_addon.py`에서 제거**

- [ ] **Step 4: import + `_reload_modules` 업데이트**

```python
from arp_cc_bones import (
    _make_cc_bone_name,
    _should_connect_cc_bone,
    _ensure_nonzero_bone_length,
    _create_cc_bones_from_preview,
    _copy_constraint_settings,
    _copy_custom_bone_constraints,
)
```

`_reload_modules`에 `"arp_cc_bones"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_cc_bones.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_cc_bones.py 추출 — cc bone 생성 + constraint 6개 함수 분리

_make_cc_bone_name, _should_connect_cc_bone, _ensure_nonzero_bone_length,
_create_cc_bones_from_preview, _copy_constraint_settings,
_copy_custom_bone_constraints을 scripts/arp_cc_bones.py로 이동.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 6: Phase 1.5 — `arp_build_helpers.py` 추출 (커밋 6)

**Files:**
- Create: `scripts/arp_build_helpers.py`
- Modify: `scripts/arp_convert_addon.py` (중복 `_distance_sq` 제거 포함)
- Modify: `scripts/arp_weight_xfer.py` (Task 2의 `_distance_sq` 로컬 복사본 제거, `arp_build_helpers`에서 import)

**이동 대상** (`arp_build_helpers.py`에 모이는 16개 함수):
- `_get_arp_set_functions` (line ~184)
- `_select_edit_bone` (line ~199)
- `_adjust_chain_counts` (line ~213)
- `_get_bone_side` (line ~304)
- `_vector_to_tuple` (line ~319)
- `_is_auxiliary_arp_deform` (line ~323)
- `_classify_arp_family_kind` (line ~328)
- `_build_ref_metadata` (line ~339)
- `_find_nearest_ref_name` (line ~369)
- `_build_arp_deform_metadata` (line ~394)
- `_build_source_deform_metadata` (line ~435)
- `_distance_sq` (line ~456)
- `_build_primary_deform_bones_by_ref` (line ~460)
- `_resolve_root_deform_parent_name` (line ~488)
- `_build_cc_parent_targets` (line ~500)
- `_resolve_cc_parent_name` (line ~513)

- [ ] **Step 1: Read 각 함수 본문 확인**

Read `scripts/arp_convert_addon.py` offset=180 limit=350 — 광범위한 본문 확인.

- [ ] **Step 2: `scripts/arp_build_helpers.py` 생성**

```python
"""
arp_convert_addon에서 분리한 Build Rig 내부 헬퍼.

ARP ref 메타데이터 구성, 체인 개수 조정, source-to-ref deform 매핑,
primary deform bone 탐색, cc parent 해결 등의 함수들을 담는다.

ARPCONV_OT_BuildRig.execute에서만 사용되므로 공개 API는 없고 모두 _로
시작하는 내부 함수들이다.
"""

import re

import bpy
from mathutils import Vector

from arp_utils import log
from skeleton_analyzer import ARP_REF_MAP  # 필요시


# 16개 함수 본문 그대로.
```

실제 import는 각 함수가 사용하는 것에 따라 조정. `Vector`, `re`, `log`, `ARP_REF_MAP` 등 빠진 것이 없도록 확인.

- [ ] **Step 3: `arp_convert_addon.py`에서 16개 함수 제거**

- [ ] **Step 4: `arp_weight_xfer.py`의 임시 `_distance_sq` 제거**

Edit `scripts/arp_weight_xfer.py`:
- 상단 import에 `from arp_build_helpers import _distance_sq` 추가
- 로컬 `_distance_sq` 함수 정의 삭제

- [ ] **Step 5: `arp_convert_addon.py`에 import 추가**

```python
from arp_build_helpers import (
    _get_arp_set_functions,
    _select_edit_bone,
    _adjust_chain_counts,
    _get_bone_side,
    _vector_to_tuple,
    _is_auxiliary_arp_deform,
    _classify_arp_family_kind,
    _build_ref_metadata,
    _find_nearest_ref_name,
    _build_arp_deform_metadata,
    _build_source_deform_metadata,
    _distance_sq,
    _build_primary_deform_bones_by_ref,
    _resolve_root_deform_parent_name,
    _build_cc_parent_targets,
    _resolve_cc_parent_name,
)
```

`_reload_modules`에 `"arp_build_helpers"` 추가.

- [ ] **Step 6: 체크포인트 CP.1~CP.4 실행**

가장 큰 이동이므로 실패 가능성이 있다. 실패 시 revert + 단계 축소(한 번에 옮기는 함수 수를 줄여서 2-3개 커밋으로 나누기).

- [ ] **Step 7: 커밋**

```bash
git add scripts/arp_build_helpers.py scripts/arp_convert_addon.py scripts/arp_weight_xfer.py
git commit -m "refactor(addon): arp_build_helpers.py 추출 — Build Rig 내부 16개 헬퍼 분리

_get_arp_set_functions, _adjust_chain_counts, _build_ref_metadata,
_build_arp_deform_metadata, _build_source_deform_metadata,
_build_primary_deform_bones_by_ref, _resolve_root_deform_parent_name,
_build_cc_parent_targets, _resolve_cc_parent_name, _distance_sq, 그리고
관련 유틸 6개(_select_edit_bone, _get_bone_side, _vector_to_tuple 등)를
scripts/arp_build_helpers.py로 이동.

arp_weight_xfer.py의 임시 _distance_sq 로컬 복사본은 제거, 이 모듈에서
import하도록 변경.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 7: Phase 2.1 — `arp_props.py` 추출 (커밋 7)

**Files:**
- Create: `scripts/arp_props.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `ARPCONV_HierarchyBoneItem` (line ~955)
- `ARPCONV_Props` (line ~961)

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=950 limit=50**

- [ ] **Step 2: `scripts/arp_props.py` 생성**

```python
"""
arp_convert_addon에서 분리한 PropertyGroup 정의.

ARPCONV_HierarchyBoneItem은 source 본 하이어라키 트리의 개별 항목.
ARPCONV_Props는 Scene 레벨의 addon state (source_armature, preview 등).

classes 리스트 (arp_convert_addon.py의 register/unregister 루프에서 사용):
- ARPCONV_HierarchyBoneItem
- ARPCONV_Props
"""

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


# 2개 class 그대로.
```

- [ ] **Step 3: `arp_convert_addon.py`에서 2개 class 제거**

- [ ] **Step 4: import + classes 리스트 업데이트**

`arp_convert_addon.py` 상단 import에 추가:
```python
from arp_props import ARPCONV_HierarchyBoneItem, ARPCONV_Props
```

`classes` 리스트(line ~2939)는 class 이름만 참조하므로 그대로 동작. import로 이름이 스코프에 들어오면 됨.

`_reload_modules`에 `"arp_props"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

Blender에서 PropertyGroup 등록 순서가 중요하므로 register() 호출 시 에러 나는지 특히 주의. 실패 시 import 순서를 `classes` 리스트 정의 전으로 조정.

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_props.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_props.py 추출 — PropertyGroup 2개 분리

ARPCONV_HierarchyBoneItem, ARPCONV_Props을 scripts/arp_props.py로 이동.
classes 리스트는 import된 이름을 그대로 참조해 register 순서 유지.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 8: Phase 2.2 — `arp_ui.py` 추출 (커밋 8)

**Files:**
- Create: `scripts/arp_ui.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `ARPCONV_PT_MainPanel` (line ~2738)

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=2733 limit=210**

- [ ] **Step 2: `scripts/arp_ui.py` 생성**

```python
"""
arp_convert_addon에서 분리한 N-panel UI.

ARPCONV_PT_MainPanel만 담는다. 이 Panel은 3D Viewport N-panel의
"ARP Convert" 탭에 각 단계(Step 1~4) 버튼을 표시한다.
"""

import bpy
from bpy.types import Panel


# ARPCONV_PT_MainPanel class 그대로.
```

- [ ] **Step 3: `arp_convert_addon.py`에서 `ARPCONV_PT_MainPanel` class 제거**

- [ ] **Step 4: import 추가**

```python
from arp_ui import ARPCONV_PT_MainPanel
```

`classes` 리스트는 그대로(import된 이름 참조). `_reload_modules`에 `"arp_ui"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_ui.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_ui.py 추출 — MainPanel UI 분리

ARPCONV_PT_MainPanel을 scripts/arp_ui.py로 이동.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 9: Phase 3.1 — `arp_ops_preview.py` 추출 (커밋 9)

**Files:**
- Create: `scripts/arp_ops_preview.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `ARPCONV_OT_CreatePreview` (line ~1002)
- `_populate_hierarchy_collection` (line ~88)
- `_build_preview_hierarchy` (line ~130)
- `_iter_preview_ancestors` (line ~140)

(hierarchy 헬퍼 3개는 preview 연산 전용이므로 함께 이동)

- [ ] **Step 1: Read 대상 코드 확인**

Read `scripts/arp_convert_addon.py` offset=85 limit=70 (hierarchy helpers)
Read `scripts/arp_convert_addon.py` offset=1000 limit=100 (CreatePreview operator)

- [ ] **Step 2: `scripts/arp_ops_preview.py` 생성**

```python
"""
arp_convert_addon에서 분리한 CreatePreview 오퍼레이터 + 하이어라키 헬퍼.

Step 1 (Analyze Source) → Step 2 (Create Preview) 플로우를 담당한다.
소스 아마추어를 분석하고 Preview Armature를 생성하며, source hierarchy
트리 데이터를 CollectionProperty에 채운다.
"""

import bpy
from bpy.types import Operator

from arp_utils import log
from skeleton_analyzer import (
    analyze_source_skeleton,  # 실제 호출되는 함수명은 확인 필요
    # ... 필요한 것들
)


# _populate_hierarchy_collection
# _build_preview_hierarchy
# _iter_preview_ancestors
# ARPCONV_OT_CreatePreview class
```

구체 본문은 Read 결과 그대로. 필요한 import(skeleton_analyzer 함수들)를 정확히 확인한 뒤 옮긴다.

- [ ] **Step 3: `arp_convert_addon.py`에서 제거**

hierarchy 3개 함수 + CreatePreview class 삭제.

- [ ] **Step 4: import + classes 리스트 업데이트**

```python
from arp_ops_preview import ARPCONV_OT_CreatePreview
```

hierarchy helpers는 preview 전용이므로 addon에서 재import 불필요 (preview 오퍼레이터 안에서만 쓰임).

`_reload_modules`에 `"arp_ops_preview"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_ops_preview.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_ops_preview.py 추출 — CreatePreview 오퍼레이터 + hierarchy 헬퍼 분리

ARPCONV_OT_CreatePreview와 관련 private 헬퍼 3개(_populate_hierarchy_collection,
_build_preview_hierarchy, _iter_preview_ancestors)를 scripts/arp_ops_preview.py로
이동. hierarchy 헬퍼는 preview 전용이므로 같은 파일에 배치.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 10: Phase 3.2 — `arp_ops_roles.py` 추출 (커밋 10)

**Files:**
- Create: `scripts/arp_ops_roles.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `ARPCONV_OT_SelectBone` (line ~1413)
- `ARPCONV_OT_SetParent` (line ~1444)
- `ARPCONV_OT_SetRole` (line ~1526)

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=1410 limit=175**

- [ ] **Step 2: `scripts/arp_ops_roles.py` 생성**

```python
"""
arp_convert_addon에서 분리한 역할/선택 관련 오퍼레이터.

Step 3 Role Editing 단계에서 사용. Source Hierarchy 트리에서 본을
선택하거나 부모를 변경하거나 역할을 바꾼다.
"""

import bpy
from bpy.types import Operator

from arp_utils import log


# 3개 class 그대로.
```

- [ ] **Step 3: `arp_convert_addon.py`에서 3개 class 제거**

- [ ] **Step 4: import + classes 리스트**

```python
from arp_ops_roles import (
    ARPCONV_OT_SelectBone,
    ARPCONV_OT_SetParent,
    ARPCONV_OT_SetRole,
)
```

`_reload_modules`에 `"arp_ops_roles"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_ops_roles.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_ops_roles.py 추출 — Role editing 오퍼레이터 3개 분리

ARPCONV_OT_SelectBone, ARPCONV_OT_SetParent, ARPCONV_OT_SetRole을
scripts/arp_ops_roles.py로 이동.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 11: Phase 3.3 — `arp_ops_bake_regression.py` 추출 (커밋 11)

**Files:**
- Create: `scripts/arp_ops_bake_regression.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `ARPCONV_OT_BakeAnimation` (line ~2563)
- `ARPCONV_OT_RunRegression` (line ~2622)

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=2560 limit=175**

- [ ] **Step 2: `scripts/arp_ops_bake_regression.py` 생성**

```python
"""
arp_convert_addon에서 분리한 Bake / Regression 오퍼레이터.

Step 4 (Bake Animation)와 Regression 테스트 실행을 담당한다.
"""

import bpy
from bpy.types import Operator

from arp_utils import log


# 2개 class 그대로.
```

필요 import (arp_utils의 bake 함수, bone_pairs 직렬화 등)를 맞춤.

- [ ] **Step 3: `arp_convert_addon.py`에서 2개 class 제거**

- [ ] **Step 4: import + classes + `_reload_modules`**

```python
from arp_ops_bake_regression import (
    ARPCONV_OT_BakeAnimation,
    ARPCONV_OT_RunRegression,
)
```

`_reload_modules`에 `"arp_ops_bake_regression"` 추가.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행**

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_ops_bake_regression.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_ops_bake_regression.py 추출 — Bake + Regression 오퍼레이터 분리

ARPCONV_OT_BakeAnimation, ARPCONV_OT_RunRegression을
scripts/arp_ops_bake_regression.py로 이동.

MCP 체크포인트 통과.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 12: Phase 3.4 — `arp_ops_build.py` 추출 (커밋 12)

**Files:**
- Create: `scripts/arp_ops_build.py`
- Modify: `scripts/arp_convert_addon.py`

**이동 대상**:
- `ARPCONV_OT_BuildRig` (line ~1586, ~975줄 크기)

**가장 큰 오퍼레이터**. 이 시점에서 앞선 Task들이 모든 helper 모듈을 이미 추출했으므로, BuildRig.execute는 모든 의존을 import로 사용할 수 있다.

- [ ] **Step 1: Read `scripts/arp_convert_addon.py` offset=1583 limit=1000**

`ARPCONV_OT_BuildRig` 전체를 읽어 정확한 시작/끝 위치 확인.

- [ ] **Step 2: `scripts/arp_ops_build.py` 생성**

```python
"""
arp_convert_addon에서 분리한 BuildRig 오퍼레이터.

Step 4 (Build Rig)를 담당하는 가장 큰 오퍼레이터. execute 본문은
약 900줄로, 다음 모듈들의 helper를 사용:
- arp_build_helpers: ref 메타데이터, deform 매핑, primary ref 해결
- arp_cc_bones: cc bone 생성, constraint 복사
- arp_weight_xfer: 웨이트 전송
- arp_foot_guides: foot guide 관련 헬퍼
- arp_fixture_io: 경로 해석
- skeleton_analyzer: 체인 탐색, ctrl map
- arp_utils: 로그, 직렬화, arp 아마추어 조회

이 파일 자체는 ARPCONV_OT_BuildRig class 정의만 담고, 실제 로직은
import된 헬퍼들에 의존한다.
"""

import bpy
from bpy.types import Operator

from arp_utils import (
    BAKE_PAIRS_KEY,
    find_arp_armature,
    find_source_armature,
    log,
    serialize_bone_pairs,
)
from skeleton_analyzer import (
    ARP_REF_MAP,
    _apply_ik_to_foot_ctrl,
    discover_arp_ctrl_map,
    remap_shape_key_drivers,
)

# 이전 Task들에서 분리된 helper 모듈들
from arp_build_helpers import (
    _adjust_chain_counts,
    _build_ref_metadata,
    _build_arp_deform_metadata,
    _build_source_deform_metadata,
    _build_primary_deform_bones_by_ref,
    _resolve_root_deform_parent_name,
    _build_cc_parent_targets,
    # ... 필요한 것 전부
)
from arp_cc_bones import (
    _create_cc_bones_from_preview,
    _copy_custom_bone_constraints,
)
from arp_weight_xfer import (
    _build_position_weight_map,
    _transfer_all_weights,
)
# (foot_guides, fixture_io는 BuildRig 안에서 직접 쓰이는지 확인 필요)


# ARPCONV_OT_BuildRig class 그대로.
```

**중요**: BuildRig.execute 본문은 현재 위 helper들을 bare 이름으로 호출 중이다. 파일이 이동되면 bare 이름이 모듈 최상단 import와 매칭되어야 한다. 즉, 필요한 모든 이름을 이 파일 상단에 `from ... import ...`로 가져와야 한다. 누락 시 `NameError` 발생 → CP 실패 → revert.

이 Task는 **가장 위험**하므로 매우 신중하게 진행.

- [ ] **Step 3: `arp_convert_addon.py`에서 `ARPCONV_OT_BuildRig` class 제거**

- [ ] **Step 4: `arp_convert_addon.py`에 import + classes + `_reload_modules`**

```python
from arp_ops_build import ARPCONV_OT_BuildRig
```

`_reload_modules`에 `"arp_ops_build"` 추가.

**이 시점에서 `arp_convert_addon.py`의 BuildRig 관련 모든 로직이 제거되었다**. entry는 이제 bl_info, _ensure_scripts_path, _reload_modules, classes 리스트, register/unregister만 남음.

- [ ] **Step 5: 체크포인트 CP.1~CP.4 실행 (가장 중요)**

실패 패턴별 대응:
- `NameError`: import 누락 → `arp_ops_build.py` 상단에 추가
- `ImportError: cannot import name ...`: 이전 Task에서 누락된 함수가 있음 → 해당 Task의 모듈에 추가
- `bone_pairs mismatch`: 뭔가 로직이 바뀌었음 → revert 후 재조사

- [ ] **Step 6: 커밋**

```bash
git add scripts/arp_ops_build.py scripts/arp_convert_addon.py
git commit -m "refactor(addon): arp_ops_build.py 추출 — BuildRig 오퍼레이터 분리 (최대 크기)

ARPCONV_OT_BuildRig (~975줄)을 scripts/arp_ops_build.py로 이동.
execute 본문은 그대로 유지하고, 이전 Task 2-8에서 분리된 helper 모듈들
(arp_build_helpers, arp_cc_bones, arp_weight_xfer, arp_foot_guides,
arp_fixture_io)을 import로 사용.

arp_convert_addon.py는 이제 bl_info + _ensure_scripts_path + _reload_modules
+ classes 리스트 + register/unregister만 남는 엔트리 파일.

MCP 체크포인트 통과 — F12 back_leg 오차 2.9e-07m 유지.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md"
```

---

## Task 13: Phase 4 — 최종 정리 (커밋 13)

**Files:**
- Modify: `scripts/arp_convert_addon.py` (모듈 docstring 추가, 주석 정리)
- Modify: `CLAUDE.md` (파일 맵 갱신)
- Modify: `AGENTS.md` (파일 맵 갱신)
- Modify: `docs/ProjectPlan.md` (sub-project ③ 완료 기록)

- [ ] **Step 1: `arp_convert_addon.py` 최종 크기 확인**

```
wc -l scripts/arp_convert_addon.py
```

Expected: < 250 줄. 초과 시 누락된 추출이 있다는 뜻 — 어떤 함수가 남아 있는지 확인.

- [ ] **Step 2: 각 새 모듈에 module docstring이 있는지 확인**

12개 모듈 각각 상단에 `"""..."""` docstring이 있어야 한다. 누락된 파일이 있으면 Edit로 추가.

- [ ] **Step 3: `CLAUDE.md` 파일 맵 갱신**

Read `CLAUDE.md` offset=17 limit=20으로 파일 맵 섹션 확인.

기존 `arp_convert_addon.py` 단일 행을 12개 모듈로 교체:

Edit old_string (정확한 내용은 Read 결과 기준):
```
| `scripts/arp_convert_addon.py` | Preview UI, BuildRig 오퍼레이터, 회귀 테스트 패널 |
```
new_string:
```
| `scripts/arp_convert_addon.py` | Blender 애드온 엔트리: bl_info, register/unregister |
| `scripts/arp_props.py` | PropertyGroup 정의 (Scene 레벨 addon state) |
| `scripts/arp_ui.py` | N-panel UI (ARPCONV_PT_MainPanel) |
| `scripts/arp_ops_preview.py` | CreatePreview 오퍼레이터 + hierarchy 헬퍼 |
| `scripts/arp_ops_roles.py` | Role editing 오퍼레이터 (SelectBone/SetParent/SetRole) |
| `scripts/arp_ops_build.py` | BuildRig 오퍼레이터 (가장 큰 execute 본문) |
| `scripts/arp_ops_bake_regression.py` | BakeAnimation + RunRegression 오퍼레이터 |
| `scripts/arp_build_helpers.py` | BuildRig 내부 헬퍼 (ref 메타데이터, deform 매핑) |
| `scripts/arp_cc_bones.py` | cc bone 생성 + constraint 복사 |
| `scripts/arp_weight_xfer.py` | 웨이트 전송 로직 |
| `scripts/arp_foot_guides.py` | Foot guide 생성/감지/자동 배치 |
| `scripts/arp_fixture_io.py` | Regression fixture 로딩/적용 |
```

- [ ] **Step 4: `AGENTS.md` 파일 맵도 동일하게 갱신**

`AGENTS.md`의 파일 맵 섹션을 찾아 같은 방식으로 교체.

- [ ] **Step 5: `docs/ProjectPlan.md`에 Sub-project ③ 완료 기록 추가**

F12 섹션 또는 후속 기능 섹션 뒤에 삽입:

```markdown

### arp_convert_addon.py 분할 완료 (2026-04-05)

2969줄 단일 파일을 12개 모듈로 분할 + 레거시 스크립트 5개 삭제.

- 엔트리: `arp_convert_addon.py` (~220줄)
- PropertyGroup: `arp_props.py`
- UI: `arp_ui.py`
- 오퍼레이터 5개: `arp_ops_preview.py`, `arp_ops_roles.py`, `arp_ops_build.py`, `arp_ops_bake_regression.py`
- 헬퍼 5개: `arp_build_helpers.py`, `arp_cc_bones.py`, `arp_weight_xfer.py`, `arp_foot_guides.py`, `arp_fixture_io.py`
- 삭제된 레거시: `01_create_arp_rig.py`, `rigify_to_arp.py`, `bone_mapping.py`, `diagnose_arp_operators.py`, `inspect_rig.py` (1501줄)
- MCP 체크포인트: 모든 Phase 커밋 후 bone_pairs + 프레임별 위치 비교로 행동 무결성 검증. F12 back_leg 오차 2.9e-07m 유지.

3개 통합 개선(Workflow / MCP / 코드 건강) 전체 완료.
```

- [ ] **Step 6: 전체 검증**

```
.venv/Scripts/python.exe -m pytest tests/ -v --tb=short
.venv/Scripts/python.exe -m ruff check scripts/ tests/
wc -l scripts/arp_convert_addon.py
ls scripts/arp_*.py | wc -l
```

Expected:
- pytest: 120 passed
- ruff: clean
- addon 엔트리: < 250 줄
- arp_*.py 파일: 12개 (addon + props + ui + 4 ops + 5 helpers)

- [ ] **Step 7: MCP 최종 체크포인트 (CP.1~CP.4 전체)**

- [ ] **Step 8: 커밋**

```bash
git add scripts/arp_convert_addon.py CLAUDE.md AGENTS.md docs/ProjectPlan.md
git commit -m "$(cat <<'EOF'
docs(addon): 분할 완료 기록 + CLAUDE.md/AGENTS.md 파일 맵 갱신

3개 통합 개선 sub-project ③/③ 구현 완료.

- arp_convert_addon.py 2969줄 → 엔트리 ~220줄 (12개 모듈로 분할)
- 레거시 5개 파일(1501줄) 삭제
- Phase별 13커밋, 각 커밋 후 MCP 체크포인트로 bone_pairs + 프레임별
  위치 비교 검증. F12 회귀 없음 확인.

CLAUDE.md / AGENTS.md 파일 맵을 12개 모듈 구조로 갱신.
ProjectPlan.md에 완료 기록 추가.

Spec: docs/superpowers/specs/2026-04-05-addon-split-design.md
EOF
)"
```

- [ ] **Step 9: 최종 로그 확인**

```
git log --oneline -15
git diff master..HEAD --stat
```

---

## 완료 기준

- [ ] `arp_convert_addon.py` < 250줄
- [ ] 12개 분할 모듈 (arp_props, arp_ui, arp_ops_preview, arp_ops_roles, arp_ops_build, arp_ops_bake_regression, arp_build_helpers, arp_cc_bones, arp_weight_xfer, arp_foot_guides, arp_fixture_io) 생성
- [ ] 레거시 5개 파일 삭제 (`01_create_arp_rig`, `rigify_to_arp`, `bone_mapping`, `diagnose_arp_operators`, `inspect_rig`)
- [ ] `pytest tests/ -v` → 120 passed
- [ ] `ruff check scripts/ tests/` → clean
- [ ] MCP 체크포인트: bone_pairs가 Phase 0 baseline과 일치, `mcp_compare_frames`의 overall_max_err < 3e-06m
- [ ] Blender GUI 수동 테스트: ARP Convert 애드온 재활성화, N 패널 정상 표시, Step 1~4 버튼 동작
- [ ] CLAUDE.md / AGENTS.md 파일 맵 12개 모듈 반영
- [ ] `docs/ProjectPlan.md` 완료 기록 추가
- [ ] 피처 브랜치 `feat/addon-split`이 master에 fast-forward 머지됨
- [ ] 총 커밋 13개 (Phase 0 ×1 + Phase 1 ×5 + Phase 2 ×2 + Phase 3 ×4 + Phase 4 ×1)

# ARP Convert UX 전면 개선 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프리뷰 본 시인성, 역할 UI 가독성, 패널 구조를 상용 애드온 수준으로 개선한다.

**Architecture:** 기존 기능 로직은 변경하지 않고 UI 레이어만 리팩토링한다. `skeleton_detection.py`에 색상/라벨 데이터를 추가하고, `arp_ui.py`를 서브패널 구조로 분리하며, `arp_role_icons.py`에서 `bpy.utils.previews` 기반 색상 아이콘을 생성한다. 뷰포트 부모 체인 하이라이트는 `arp_viewport_handler.py`에 `depsgraph_update_post` 핸들러로 구현한다.

**Tech Stack:** Blender 4.5 Python API (`bpy`), `bpy.utils.previews`

**스펙:** `docs/superpowers/specs/2026-04-15-ux-overhaul-design.md`

---

### Task 1: 색상 팔레트 + 한국어 라벨 데이터

**Files:**
- Modify: `scripts/skeleton_detection.py:95-116`
- Test: `tests/test_skeleton_analyzer.py` (기존 파일에 추가)

- [ ] **Step 1: ROLE_COLORS 테스트 작성**

`tests/test_skeleton_analyzer.py` 끝에 추가:

```python
def test_role_colors_all_unique():
    """각 역할의 색상이 고유한지 검증 (L/R 포함)."""
    from skeleton_detection import ROLE_COLORS

    colors = list(ROLE_COLORS.values())
    color_set = set(colors)
    assert len(color_set) == len(colors), (
        f"중복 색상 발견: {len(colors)} 역할, {len(color_set)} 고유색"
    )


def test_role_colors_lr_differ():
    """L/R 쌍의 색상이 서로 다른지 검증."""
    from skeleton_detection import ROLE_COLORS

    lr_pairs = [
        ("back_leg_l", "back_leg_r"),
        ("back_foot_l", "back_foot_r"),
        ("front_leg_l", "front_leg_r"),
        ("front_foot_l", "front_foot_r"),
        ("ear_l", "ear_r"),
    ]
    for left, right in lr_pairs:
        assert ROLE_COLORS[left] != ROLE_COLORS[right], (
            f"{left}과 {right} 색상이 동일: {ROLE_COLORS[left]}"
        )
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_skeleton_analyzer.py::test_role_colors_all_unique tests/test_skeleton_analyzer.py::test_role_colors_lr_differ -v`
Expected: FAIL — 현재 spine/neck/head 동일, L/R 동일

- [ ] **Step 3: ROLE_COLORS 팔레트 교체**

`scripts/skeleton_detection.py:98-116`의 `ROLE_COLORS`를 교체:

```python
ROLE_COLORS = {
    "root": (1.0, 0.82, 0.0),
    "spine": (0.24, 0.39, 0.86),
    "neck": (0.31, 0.55, 1.0),
    "head": (0.51, 0.67, 1.0),
    "back_leg_l": (0.86, 0.24, 0.24),
    "back_leg_r": (1.0, 0.43, 0.43),
    "back_foot_l": (0.71, 0.16, 0.27),
    "back_foot_r": (0.86, 0.35, 0.47),
    "front_leg_l": (0.20, 0.71, 0.20),
    "front_leg_r": (0.39, 0.86, 0.39),
    "front_foot_l": (0.12, 0.51, 0.24),
    "front_foot_r": (0.27, 0.67, 0.39),
    "ear_l": (0.0, 0.75, 0.78),
    "ear_r": (0.31, 0.86, 0.90),
    "tail": (0.94, 0.59, 0.12),
    "trajectory": (0.71, 0.63, 0.24),
    "unmapped": (0.43, 0.43, 0.43),
}
```

- [ ] **Step 4: ROLE_LABELS 딕셔너리 추가**

`scripts/skeleton_detection.py`에서 `ROLE_COLORS` 직후에 추가:

```python
ROLE_LABELS = {
    "root": "루트",
    "spine": "스파인",
    "neck": "목",
    "head": "머리",
    "back_leg_l": "뒷다리 L",
    "back_leg_r": "뒷다리 R",
    "back_foot_l": "뒷발 L",
    "back_foot_r": "뒷발 R",
    "front_leg_l": "앞다리 L",
    "front_leg_r": "앞다리 R",
    "front_foot_l": "앞발 L",
    "front_foot_r": "앞발 R",
    "ear_l": "귀 L",
    "ear_r": "귀 R",
    "tail": "꼬리",
    "trajectory": "궤적",
    "unmapped": "미매핑",
}
```

- [ ] **Step 5: ROLE_LABELS 테스트 추가 + 실행**

`tests/test_skeleton_analyzer.py` 끝에 추가:

```python
def test_role_labels_keys_match_colors():
    """ROLE_LABELS와 ROLE_COLORS의 키가 동일한지 검증."""
    from skeleton_detection import ROLE_COLORS, ROLE_LABELS

    assert set(ROLE_LABELS.keys()) == set(ROLE_COLORS.keys())
```

Run: `pytest tests/test_skeleton_analyzer.py -v`
Expected: ALL PASS

- [ ] **Step 6: 커밋**

```bash
git add scripts/skeleton_detection.py tests/test_skeleton_analyzer.py
git commit -m "feat(ux): 고유색 팔레트 + ROLE_LABELS 한국어 라벨 추가"
```

---

### Task 2: 프로퍼티 업데이트 (툴팁 + 상태 프로퍼티)

**Files:**
- Modify: `scripts/arp_props.py:55-96`

- [ ] **Step 1: ARPCONV_HierarchyBoneItem에 tree_prefix 추가**

`scripts/arp_props.py`의 `ARPCONV_HierarchyBoneItem` 클래스에 프로퍼티 추가:

```python
class ARPCONV_HierarchyBoneItem(PropertyGroup):
    """하이어라키 트리 아이템 (name은 PropertyGroup에서 상속)"""
    depth: IntProperty(default=0)
    tree_prefix: StringProperty(default="")
```

- [ ] **Step 2: ARPCONV_Props 툴팁 + 상태 프로퍼티 추가**

`scripts/arp_props.py`의 `ARPCONV_Props` 클래스를 수정:

```python
class ARPCONV_Props(PropertyGroup):
    """전역 프로퍼티"""
    preview_armature: StringProperty(
        name="프리뷰 아마추어",
        description="생성된 프리뷰 아마추어",
        default="",
    )
    source_armature: StringProperty(
        name="소스 아마추어",
        description="변환할 원본 아마추어",
        default="",
    )
    is_analyzed: BoolProperty(
        name="분석 완료",
        description="소스 아마추어 분석 완료 여부",
        default=False,
    )
    confidence: FloatProperty(
        name="신뢰도",
        description="자동 역할 추론 신뢰도 (0~100%)",
        default=0.0,
    )
    regression_fixture: StringProperty(
        name="Fixture JSON",
        description="회귀 테스트용 피처 파일 경로",
        default="",
        subtype="FILE_PATH",
    )
    regression_report_dir: StringProperty(
        name="리포트 폴더",
        description="회귀 테스트 결과 저장 폴더",
        default="",
        subtype="DIR_PATH",
    )
    front_3bones_ik: FloatProperty(
        name="앞다리 3본 IK",
        description="앞다리 3본 IK 영향도. 0이면 어깨 독립 회전, 1이면 발 IK에 연동",
        default=0.0,
        min=0.0,
        max=1.0,
    )
    show_source_hierarchy: BoolProperty(
        name="소스 계층 트리",
        description="소스 본 계층 트리 표시/숨김",
        default=False,
    )
    pending_parent: StringProperty(
        name="새 부모",
        description="선택한 본의 새 부모 — 선택 시 자동 적용",
        default="",
        update=_on_pending_parent_changed,
    )
    build_completed: BoolProperty(
        name="리그 생성 완료",
        description="Build Rig 완료 여부",
        default=False,
    )
    retarget_setup_done: BoolProperty(
        name="리타겟 설정 완료",
        description="Retarget Setup 완료 여부",
        default=False,
    )
    mapped_bone_count: IntProperty(
        name="매핑 본 수",
        description="역할이 매핑된 본 수",
        default=0,
    )
    total_bone_count: IntProperty(
        name="전체 본 수",
        description="프리뷰 아마추어의 전체 본 수",
        default=0,
    )
```

- [ ] **Step 3: ruff 확인 + 커밋**

Run: `ruff check scripts/arp_props.py`
Expected: PASS

```bash
git add scripts/arp_props.py
git commit -m "feat(ux): 프로퍼티 툴팁 한국어화 + 상태 추적 프로퍼티 추가"
```

---

### Task 3: 역할 라벨 한국어화 (ROLE_ITEMS)

**Files:**
- Modify: `scripts/arp_ops_roles.py:23-42`

- [ ] **Step 1: ROLE_ITEMS 라벨 교체**

`scripts/arp_ops_roles.py`의 `ROLE_ITEMS`를 교체 (lines 23-41):

```python
ROLE_ITEMS = [
    ("root", "루트", "루트 본"),
    ("spine", "스파인", "스파인 체인"),
    ("neck", "목", "목"),
    ("head", "머리", "머리"),
    ("back_leg_l", "뒷다리 L", "뒷다리 좌"),
    ("back_leg_r", "뒷다리 R", "뒷다리 우"),
    ("back_foot_l", "뒷발 L", "뒷발 좌"),
    ("back_foot_r", "뒷발 R", "뒷발 우"),
    ("front_leg_l", "앞다리 L", "앞다리 좌"),
    ("front_leg_r", "앞다리 R", "앞다리 우"),
    ("front_foot_l", "앞발 L", "앞발 좌"),
    ("front_foot_r", "앞발 R", "앞발 우"),
    ("ear_l", "귀 L", "귀 좌"),
    ("ear_r", "귀 R", "귀 우"),
    ("tail", "꼬리", "꼬리"),
    ("trajectory", "궤적", "궤적 본 (Root→c_traj)"),
    ("unmapped", "미매핑", "미매핑 (cc_ 커스텀 본)"),
]
```

- [ ] **Step 2: ruff 확인 + 테스트**

Run: `ruff check scripts/arp_ops_roles.py && pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: 커밋**

```bash
git add scripts/arp_ops_roles.py
git commit -m "feat(ux): ROLE_ITEMS 라벨 한국어 풀네임으로 교체"
```

---

### Task 4: 역할 색상 아이콘 모듈

**Files:**
- Create: `scripts/arp_role_icons.py`
- Test: `tests/test_role_icons.py`

- [ ] **Step 1: 아이콘 생성 로직 테스트 작성**

`tests/test_role_icons.py` 생성:

```python
"""arp_role_icons의 픽셀 데이터 생성 로직 테스트.

bpy.utils.previews는 Blender 전용이므로 픽셀 배열 생성 함수만 테스트한다.
"""

from arp_role_icons import make_icon_pixels


def test_make_icon_pixels_length():
    """16x16 RGBA = 1024 float."""
    pixels = make_icon_pixels((1.0, 0.0, 0.0))
    assert len(pixels) == 16 * 16 * 4


def test_make_icon_pixels_color():
    """첫 픽셀이 지정 RGB + alpha 1.0인지 확인."""
    pixels = make_icon_pixels((0.5, 0.3, 0.8))
    assert pixels[0:4] == [0.5, 0.3, 0.8, 1.0]


def test_make_icon_pixels_all_same():
    """모든 픽셀이 동일 색상."""
    pixels = make_icon_pixels((0.2, 0.4, 0.6))
    for i in range(0, len(pixels), 4):
        assert pixels[i:i + 4] == [0.2, 0.4, 0.6, 1.0]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_role_icons.py -v`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: arp_role_icons.py 구현**

`scripts/arp_role_icons.py` 생성:

```python
"""역할별 색상 아이콘 생성.

bpy.utils.previews를 사용하여 16x16 색상 사각형 아이콘을 생성한다.
UI 버튼과 트리 항목에서 icon_value로 참조한다.
"""

_ICON_SIZE = 16
_preview_collection = None


def make_icon_pixels(rgb):
    """RGB 튜플로 16x16 RGBA 픽셀 배열 생성."""
    r, g, b = rgb
    pixel = [r, g, b, 1.0]
    return pixel * (_ICON_SIZE * _ICON_SIZE)


def register():
    """역할별 색상 아이콘 프리뷰 컬렉션 생성."""
    import bpy.utils.previews
    from skeleton_detection import ROLE_COLORS

    global _preview_collection
    _preview_collection = bpy.utils.previews.new()

    for role_id, rgb in ROLE_COLORS.items():
        icon = _preview_collection.new(role_id)
        icon.icon_size = (_ICON_SIZE, _ICON_SIZE)
        icon.image_size = (_ICON_SIZE, _ICON_SIZE)
        icon.image_pixels_float[:] = make_icon_pixels(rgb)


def unregister():
    """프리뷰 컬렉션 정리."""
    import bpy.utils.previews

    global _preview_collection
    if _preview_collection is not None:
        bpy.utils.previews.remove(_preview_collection)
        _preview_collection = None


def get_icon_id(role_id):
    """역할 ID로 아이콘 ID 반환. 등록 전이면 0."""
    if _preview_collection is None:
        return 0
    icon = _preview_collection.get(role_id)
    return icon.icon_id if icon else 0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_role_icons.py -v`
Expected: ALL PASS

- [ ] **Step 5: ruff 확인 + 커밋**

Run: `ruff check scripts/arp_role_icons.py tests/test_role_icons.py`

```bash
git add scripts/arp_role_icons.py tests/test_role_icons.py
git commit -m "feat(ux): 역할별 색상 아이콘 모듈 추가 (bpy.utils.previews)"
```

---

### Task 5: 계층 트리 연결선 + 색상 아이콘

**Files:**
- Modify: `scripts/arp_ops_preview.py:19-60`
- Test: `tests/test_tree_prefix.py`

- [ ] **Step 1: tree_prefix 계산 함수 테스트 작성**

`tests/test_tree_prefix.py` 생성:

```python
"""트리 연결선(├─ └─ │) 접두사 생성 로직 테스트."""

from arp_ops_preview import compute_tree_prefixes


def test_single_root():
    """루트 하나만 있을 때 접두사 없음."""
    items = [{"name": "Root", "depth": 0, "children_count": 0}]
    prefixes = compute_tree_prefixes(items)
    assert prefixes == [""]


def test_root_with_children():
    """루트 + 자식 2개."""
    items = [
        {"name": "Root", "depth": 0},
        {"name": "Spine1", "depth": 1},
        {"name": "Hip", "depth": 1},
    ]
    prefixes = compute_tree_prefixes(items)
    assert prefixes[0] == ""
    assert prefixes[1] == "├─ "
    assert prefixes[2] == "└─ "


def test_deep_hierarchy():
    """3단계 깊이 트리."""
    items = [
        {"name": "Root", "depth": 0},
        {"name": "Spine", "depth": 1},
        {"name": "Neck", "depth": 2},
        {"name": "Head", "depth": 3},
        {"name": "Tail", "depth": 1},
    ]
    prefixes = compute_tree_prefixes(items)
    assert prefixes[0] == ""
    assert prefixes[1] == "├─ "
    assert prefixes[2] == "│  ├─ "  # Spine has Neck child, but also need to check siblings
    assert prefixes[3] == "│  │  └─ "  # Head is last child of Neck... but Neck has no siblings shown
    # Actually let me reconsider. The prefix depends on whether ancestors have more siblings.
    # Root children: Spine (not last), Tail (last)
    # Spine children: Neck (only child → last)
    # Neck children: Head (only child → last)
    assert prefixes[1] == "├─ "       # Spine: not last child of Root
    assert prefixes[2] == "│  └─ "    # Neck: last child of Spine; Spine not last → │
    assert prefixes[3] == "│     └─ " # Head: last child of Neck; Spine not last → │
    assert prefixes[4] == "└─ "       # Tail: last child of Root


def test_excluded_bone_at_end():
    """제외 본(depth만 있고 자식 없음)이 마지막에 올 때."""
    items = [
        {"name": "Root", "depth": 0},
        {"name": "Spine", "depth": 1},
        {"name": "ExcludedBone", "depth": 1},
    ]
    prefixes = compute_tree_prefixes(items)
    assert prefixes[1] == "├─ "
    assert prefixes[2] == "└─ "
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_tree_prefix.py -v`
Expected: FAIL — `compute_tree_prefixes` 없음

- [ ] **Step 3: compute_tree_prefixes 함수 구현**

`scripts/arp_ops_preview.py` 상단(imports 아래, `_populate_hierarchy_collection` 전)에 추가:

```python
def compute_tree_prefixes(items):
    """depth 기반 아이템 리스트로 트리 연결선 접두사를 계산한다.

    Parameters
    ----------
    items : list[dict]
        각 dict에 "name"(str), "depth"(int) 키 필요.

    Returns
    -------
    list[str]
        각 아이템의 트리 접두사 문자열.
    """
    n = len(items)
    prefixes = [""] * n

    def _has_next_sibling(idx):
        """idx 아이템 뒤에 같은 depth의 형제가 있는지."""
        my_depth = items[idx]["depth"]
        for j in range(idx + 1, n):
            d = items[j]["depth"]
            if d == my_depth:
                return True
            if d < my_depth:
                return False
        return False

    for i in range(n):
        depth = items[i]["depth"]
        if depth == 0:
            prefixes[i] = ""
            continue

        parts = []
        # 조상 레벨별로 수직선(│) 또는 공백 결정
        for d in range(1, depth):
            # depth=d인 조상이 다음 형제를 갖는지 확인
            ancestor_idx = None
            for k in range(i - 1, -1, -1):
                if items[k]["depth"] == d:
                    ancestor_idx = k
                    break
                if items[k]["depth"] < d:
                    break
            if ancestor_idx is not None and _has_next_sibling(ancestor_idx):
                parts.append("│  ")
            else:
                parts.append("   ")

        # 현재 아이템의 연결 문자
        if _has_next_sibling(i):
            parts.append("├─ ")
        else:
            parts.append("└─ ")

        prefixes[i] = "".join(parts)

    return prefixes
```

- [ ] **Step 4: 테스트 통과 확인 및 수정**

Run: `pytest tests/test_tree_prefix.py -v`

테스트의 기대값이 구현과 맞지 않으면 테스트를 구현에 맞게 조정한다. 트리 접두사의 정확한 공백 수가 중요 — 실행 결과를 보고 assert 값을 맞춘다.

- [ ] **Step 5: _populate_hierarchy_collection에 tree_prefix 저장 로직 추가**

`scripts/arp_ops_preview.py`의 `_populate_hierarchy_collection` 함수 끝에 추가:

```python
    # tree_prefix 계산
    items_for_prefix = [{"name": item.name, "depth": item.depth} for item in coll]
    prefixes = compute_tree_prefixes(items_for_prefix)
    for i, item in enumerate(coll):
        item.tree_prefix = prefixes[i]
```

- [ ] **Step 6: ruff 확인 + 커밋**

Run: `ruff check scripts/arp_ops_preview.py tests/test_tree_prefix.py && pytest tests/ -v`

```bash
git add scripts/arp_ops_preview.py tests/test_tree_prefix.py
git commit -m "feat(ux): 계층 트리 연결선 접두사 계산 로직 추가"
```

---

### Task 6: 서브패널 구조로 UI 분리

**Files:**
- Modify: `scripts/arp_ui.py` (전면 리팩토링)

이 태스크가 가장 크다. 단일 `ARPCONV_PT_MainPanel`을 7개 패널 클래스로 분리한다.

- [ ] **Step 1: 메인 패널 + Step 1 서브패널 작성**

`scripts/arp_ui.py`를 전면 교체. 먼저 상단 imports와 메인패널 + Step 1:

```python
"""
ARP Convert N-panel UI.

메인 패널 + 5개 서브패널 + 도구 패널로 구성.
"""

import os
import sys

import bpy
from bpy.types import Panel


def _ensure_scripts_path():
    """scripts/ 폴더를 sys.path에 추가"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.exists(os.path.join(script_dir, "skeleton_analyzer.py")):
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
        return script_dir
    try:
        blend_filepath = bpy.data.filepath
    except AttributeError:
        blend_filepath = ""
    if blend_filepath:
        d = os.path.dirname(blend_filepath)
        for _ in range(10):
            candidate = os.path.join(d, "scripts")
            if os.path.exists(os.path.join(candidate, "skeleton_analyzer.py")):
                if candidate not in sys.path:
                    sys.path.insert(0, candidate)
                return candidate
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    return ""


def _get_step_status(props):
    """현재 워크플로 진행 상태 반환.

    Returns dict: step_number → "done" | "current" | "pending"
    """
    status = {1: "pending", 2: "pending", 3: "pending", 4: "pending", 5: "pending"}
    if props.is_analyzed:
        status[1] = "done"
        status[2] = "current"
    if props.build_completed:
        status[2] = "done"
        status[3] = "done"
        status[4] = "current"
    if props.retarget_setup_done:
        status[4] = "done"
        status[5] = "current"
    return status


_STATUS_ICONS = {"done": "CHECKMARK", "current": "PLAY", "pending": "RADIOBUT_OFF"}


class ARPCONV_PT_MainPanel(Panel):
    """ARP 리그 변환 메인 패널"""

    bl_label = "ARP 리그 변환"
    bl_idname = "ARPCONV_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"

    def draw(self, context):
        layout = self.layout
        from arp_convert_addon import bl_info
        layout.label(text=f"v{'.'.join(str(v) for v in bl_info['version'])}")


class ARPCONV_PT_Step1_Analysis(Panel):
    """1. 분석"""

    bl_label = "1. 분석"
    bl_idname = "ARPCONV_PT_step1"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[1]])
        if props.is_analyzed:
            self.layout.label(text=f"신뢰도 {props.confidence:.0%}")

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props
        if props.source_armature:
            layout.label(text=f"소스: {props.source_armature}")
        row = layout.row()
        row.scale_y = 1.5
        row.operator("arp_convert.create_preview", icon="ARMATURE_DATA")
        if not props.is_analyzed:
            layout.label(text="소스 아마추어를 선택하고 분석을 실행하세요.", icon="INFO")
        elif props.preview_armature:
            layout.label(text=f"프리뷰: {props.preview_armature}")
```

- [ ] **Step 2: Step 2 서브패널 작성 (역할 수정)**

같은 파일에 이어서:

```python
class ARPCONV_PT_Step2_Roles(Panel):
    """2. 역할 수정"""

    bl_label = "2. 역할 수정"
    bl_idname = "ARPCONV_PT_step2"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[2]])
        if props.total_bone_count > 0:
            self.layout.label(
                text=f"{props.mapped_bone_count}/{props.total_bone_count} 매핑됨"
            )

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props

        _ensure_scripts_path()
        from skeleton_analyzer import ROLE_PROP_KEY
        from skeleton_detection import ROLE_LABELS
        from arp_role_icons import get_icon_id

        # Source Hierarchy (접이식)
        hier_coll = getattr(context.scene, "arp_source_hierarchy", None)
        if hier_coll and len(hier_coll) > 0:
            row = layout.row()
            row.prop(
                props,
                "show_source_hierarchy",
                icon="TRIA_DOWN" if props.show_source_hierarchy else "TRIA_RIGHT",
                text=f"소스 계층 트리 ({len(hier_coll)})",
                emboss=False,
            )
            if props.show_source_hierarchy:
                preview_obj = bpy.data.objects.get(props.preview_armature)
                hier_box = layout.box()
                col = hier_box.column(align=True)
                for item in hier_coll:
                    row = col.row(align=True)
                    pbone = (
                        preview_obj.pose.bones.get(item.name) if preview_obj else None
                    )
                    if pbone is None:
                        icon_val = 0
                        blender_icon = "RADIOBUT_OFF"
                        role = "unmapped"
                        label = f"{item.tree_prefix}{item.name} (w=0)"
                    else:
                        role = pbone.get(ROLE_PROP_KEY, "unmapped")
                        icon_val = get_icon_id(role)
                        blender_icon = ""
                        role_label = ROLE_LABELS.get(role, "")
                        label = f"{item.tree_prefix}{item.name}"
                        if role_label and role != "unmapped":
                            label += f"  {role_label}"

                    if icon_val:
                        op = row.operator(
                            "arp_convert.select_bone",
                            text=label,
                            icon_value=icon_val,
                            emboss=False,
                        )
                    else:
                        op = row.operator(
                            "arp_convert.select_bone",
                            text=label,
                            icon=blender_icon or "DOT",
                            emboss=False,
                        )
                    op.bone_name = item.name

        layout.label(text="본 선택 후 역할을 변경하세요:")

        # 역할 버튼 — 카테고리별
        # 몸통
        sub = layout.column(align=True)
        sub.label(text="몸통:")
        grid = sub.grid_flow(columns=3, align=True)
        for role_id in ["root", "spine", "neck", "head", "tail"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator(
                    "arp_convert.set_role", text=label, icon_value=icon_val
                )
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 다리
        sub = layout.column(align=True)
        sub.label(text="다리:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["back_leg_l", "back_leg_r", "front_leg_l", "front_leg_r"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator(
                    "arp_convert.set_role", text=label, icon_value=icon_val
                )
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 발
        sub = layout.column(align=True)
        sub.label(text="발:")
        sub.label(text="(bank/heel 가이드 자동 생성)", icon="INFO")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in [
            "back_foot_l",
            "back_foot_r",
            "front_foot_l",
            "front_foot_r",
        ]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator(
                    "arp_convert.set_role", text=label, icon_value=icon_val
                )
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 머리 부속
        sub = layout.column(align=True)
        sub.label(text="머리 부속:")
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["ear_l", "ear_r"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator(
                    "arp_convert.set_role", text=label, icon_value=icon_val
                )
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 기타
        sub = layout.column(align=True)
        grid = sub.grid_flow(columns=2, align=True)
        for role_id in ["trajectory", "unmapped"]:
            icon_val = get_icon_id(role_id)
            label = ROLE_LABELS.get(role_id, role_id)
            if icon_val:
                op = grid.operator(
                    "arp_convert.set_role", text=label, icon_value=icon_val
                )
            else:
                op = grid.operator("arp_convert.set_role", text=label)
            op.role = role_id

        # 선택 본 정보
        if context.active_object and context.active_object.type == "ARMATURE":
            arm_obj = context.active_object
            selected_bones = [b for b in arm_obj.data.bones if b.select]

            if selected_bones:
                layout.separator()
                if len(selected_bones) == 1:
                    bone = selected_bones[0]
                    pbone = arm_obj.pose.bones.get(bone.name)
                    current_role = (
                        pbone.get(ROLE_PROP_KEY, "unmapped") if pbone else "?"
                    )
                    role_label = ROLE_LABELS.get(current_role, current_role)
                    layout.label(text=f"선택: {bone.name}", icon="BONE_DATA")
                    layout.label(text=f"현재 역할: {role_label}")
                    parent_name = bone.parent.name if bone.parent else "(없음)"
                    layout.label(text=f"부모: {parent_name}", icon="LINKED")
                else:
                    layout.label(
                        text=f"선택: {len(selected_bones)}개 본",
                        icon="BONE_DATA",
                    )
                    names = ", ".join(b.name for b in selected_bones[:4])
                    if len(selected_bones) > 4:
                        names += f" 외 {len(selected_bones) - 4}개"
                    layout.label(text=names)

                preview_obj = bpy.data.objects.get(props.preview_armature)
                if preview_obj:
                    row2 = layout.row(align=True)
                    row2.prop_search(
                        props,
                        "pending_parent",
                        preview_obj.data,
                        "bones",
                        text="새 부모",
                    )

            if not selected_bones:
                layout.separator()
                layout.label(text="Shift+클릭으로 복수 선택 가능", icon="INFO")
```

- [ ] **Step 3: Step 3~5 + 도구 서브패널 작성**

같은 파일에 이어서:

```python
class ARPCONV_PT_Step3_Build(Panel):
    """3. 리그 생성"""

    bl_label = "3. 리그 생성"
    bl_idname = "ARPCONV_PT_step3"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[3]])

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props
        layout.prop(props, "front_3bones_ik", slider=True)
        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.build_rig", icon="MOD_ARMATURE")


class ARPCONV_PT_Step4_Retarget(Panel):
    """4. 리타겟"""

    bl_label = "4. 리타겟"
    bl_idname = "ARPCONV_PT_step4"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[4]])

    def draw(self, context):
        layout = self.layout
        scn = context.scene

        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.setup_retarget", icon="LINKED")

        has_bones_map = hasattr(scn, "bones_map_v2") and len(scn.bones_map_v2) > 0

        if has_bones_map:
            target_rig = bpy.data.objects.get(getattr(scn, "target_rig", ""))

            layout.separator()
            row = layout.row(align=True)
            split = row.split(factor=0.5)
            split.label(text="소스 본:")
            split.label(text="타겟 본:")

            row = layout.row(align=True)
            try:
                row.template_list(
                    "ARP_UL_items",
                    "",
                    scn,
                    "bones_map_v2",
                    scn,
                    "bones_map_index",
                    rows=4,
                )
            except Exception:
                row.label(
                    text="ARP Remap UIList를 불러올 수 없습니다.", icon="ERROR"
                )

            idx = getattr(scn, "bones_map_index", -1)
            if 0 <= idx < len(scn.bones_map_v2):
                item = scn.bones_map_v2[idx]
                prop_box = layout.box()

                row = prop_box.row(align=True)
                row.label(text=item.source_bone + ":")
                if target_rig and target_rig.type == "ARMATURE":
                    row.prop_search(item, "name", target_rig.data, "bones", text="")
                else:
                    row.prop(item, "name", text="")

                row = prop_box.row(align=True)
                row.prop(item, "set_as_root", text="루트 지정")
                sub = row.row()
                sub.enabled = not item.ik and not item.set_as_root
                sub.prop(item, "location", text="위치")

                row = prop_box.row(align=True)
                split = row.split(factor=0.2)
                split.enabled = not item.set_as_root
                split.prop(item, "ik", text="IK")
                if item.ik and target_rig and target_rig.type == "ARMATURE":
                    sub = split.split(factor=0.9, align=True)
                    sub.prop_search(
                        item, "ik_pole", target_rig.data, "bones", text="폴 벡터"
                    )

        layout.separator()

        if hasattr(scn, "batch_retarget"):
            row = layout.row(align=True)
            row.prop(scn, "batch_retarget", text="다중 소스 애니메이션")
            if getattr(scn, "batch_retarget", False):
                marked = sum(
                    1 for act in bpy.data.actions if act.get("arp_remap", False)
                )
                row.label(text=f"({marked}개 액션)")

        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.execute_retarget", icon="PLAY")

        row = layout.row()
        row.operator("arp_convert.copy_custom_scale", icon="CON_SIZELIKE")


class ARPCONV_PT_Step5_Cleanup(Panel):
    """5. 정리"""

    bl_label = "5. 정리"
    bl_idname = "ARPCONV_PT_step5"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return context.scene.arp_convert_props.is_analyzed

    def draw_header(self, context):
        props = context.scene.arp_convert_props
        status = _get_step_status(props)
        self.layout.label(text="", icon=_STATUS_ICONS[status[5]])

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.3
        row.operator("arp_convert.cleanup", icon="TRASH")


class ARPCONV_PT_Tools(Panel):
    """도구"""

    bl_label = "도구"
    bl_idname = "ARPCONV_PT_tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARP Convert"
    bl_parent_id = "ARPCONV_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        props = context.scene.arp_convert_props
        layout.prop(props, "regression_fixture", text="Fixture")
        layout.prop(props, "regression_report_dir", text="리포트 폴더")
        row = layout.row()
        row.scale_y = 1.2
        row.operator("arp_convert.run_regression", icon="CHECKMARK")
```

- [ ] **Step 4: ruff 확인**

Run: `ruff check scripts/arp_ui.py`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/arp_ui.py
git commit -m "feat(ux): 단일 패널 → 7개 서브패널 구조로 분리 + 진행 상태 표시"
```

---

### Task 7: 뷰포트 부모 체인 하이라이트 핸들러

**Files:**
- Create: `scripts/arp_viewport_handler.py`

- [ ] **Step 1: 핸들러 모듈 구현**

`scripts/arp_viewport_handler.py` 생성:

```python
"""뷰포트 부모 체인 하이라이트 핸들러.

프리뷰 아마추어에서 본 선택 시, 선택 본 → 루트까지
부모 체인의 bone.select를 True로 설정하여 select 색상으로 표시한다.
"""

import bpy

_prev_selection = set()
_prev_active_object = None


def _parent_chain_highlight(scene, depsgraph):
    """depsgraph_update_post 핸들러."""
    global _prev_selection, _prev_active_object

    obj = bpy.context.view_layer.objects.active
    if obj is None or obj.type != "ARMATURE":
        return

    props = bpy.context.scene.arp_convert_props
    if not props.preview_armature or obj.name != props.preview_armature:
        return

    if bpy.context.mode != "POSE":
        return

    current_selection = {b.name for b in obj.data.bones if b.select}
    if current_selection == _prev_selection and obj == _prev_active_object:
        return

    _prev_selection = current_selection.copy()
    _prev_active_object = obj

    user_selected = {b.name for b in obj.data.bones if b.select}

    chain_bones = set()
    for bone_name in user_selected:
        bone = obj.data.bones.get(bone_name)
        parent = bone.parent if bone else None
        while parent:
            if parent.name in user_selected:
                break
            chain_bones.add(parent.name)
            parent = parent.parent

    for bone in obj.data.bones:
        if bone.name in user_selected:
            continue
        bone.select = bone.name in chain_bones


def register():
    """핸들러 등록."""
    if _parent_chain_highlight not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_parent_chain_highlight)


def unregister():
    """핸들러 해제."""
    global _prev_selection, _prev_active_object
    if _parent_chain_highlight in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_parent_chain_highlight)
    _prev_selection = set()
    _prev_active_object = None
```

- [ ] **Step 2: ruff 확인 + 커밋**

Run: `ruff check scripts/arp_viewport_handler.py`

```bash
git add scripts/arp_viewport_handler.py
git commit -m "feat(ux): 뷰포트 부모 체인 하이라이트 핸들러 추가"
```

---

### Task 8: 애드온 등록 업데이트

**Files:**
- Modify: `scripts/arp_convert_addon.py`

- [ ] **Step 1: bl_info 한국어 설명 수정**

`scripts/arp_convert_addon.py`의 `bl_info["description"]` 수정:

```python
"description": "프리뷰 기반 ARP 리그 자동 변환",
```

- [ ] **Step 2: classes 리스트에 서브패널 추가**

`scripts/arp_convert_addon.py`의 classes 리스트를 수정. 기존 `ARPCONV_PT_MainPanel` 뒤에 서브패널 클래스들 추가:

```python
from arp_ui import (
    ARPCONV_PT_MainPanel,
    ARPCONV_PT_Step1_Analysis,
    ARPCONV_PT_Step2_Roles,
    ARPCONV_PT_Step3_Build,
    ARPCONV_PT_Step4_Retarget,
    ARPCONV_PT_Step5_Cleanup,
    ARPCONV_PT_Tools,
)
```

classes 리스트에서 기존 `ARPCONV_PT_MainPanel`을 7개 패널로 교체:

```python
classes = [
    ARPCONV_HierarchyBoneItem,
    ARPCONV_Props,
    ARPCONV_OT_CreatePreview,
    ARPCONV_OT_SelectBone,
    ARPCONV_OT_SetParent,
    ARPCONV_OT_SetRole,
    ARPCONV_OT_BuildRig,
    ARPCONV_OT_SetupRetarget,
    ARPCONV_OT_CopyCustomScale,
    ARPCONV_OT_ExecuteRetarget,
    ARPCONV_OT_Cleanup,
    ARPCONV_OT_RunRegression,
    ARPCONV_PT_MainPanel,
    ARPCONV_PT_Step1_Analysis,
    ARPCONV_PT_Step2_Roles,
    ARPCONV_PT_Step3_Build,
    ARPCONV_PT_Step4_Retarget,
    ARPCONV_PT_Step5_Cleanup,
    ARPCONV_PT_Tools,
]
```

- [ ] **Step 3: register/unregister에 아이콘 + 핸들러 등록 추가**

`scripts/arp_convert_addon.py`의 register 함수에 추가:

```python
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.arp_convert_props = PointerProperty(type=ARPCONV_Props)
    bpy.types.Scene.arp_source_hierarchy = CollectionProperty(
        type=ARPCONV_HierarchyBoneItem
    )
    import arp_role_icons
    arp_role_icons.register()
    import arp_viewport_handler
    arp_viewport_handler.register()
```

unregister 함수에 추가:

```python
def unregister():
    import arp_viewport_handler
    arp_viewport_handler.unregister()
    import arp_role_icons
    arp_role_icons.unregister()
    del bpy.types.Scene.arp_source_hierarchy
    del bpy.types.Scene.arp_convert_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

- [ ] **Step 4: _reload_modules에 새 모듈 추가**

`scripts/arp_convert_addon.py`의 `_reload_modules()` 함수에 새 모듈 추가:

```python
"arp_role_icons",
"arp_viewport_handler",
```

- [ ] **Step 5: ruff 확인 + 커밋**

Run: `ruff check scripts/arp_convert_addon.py`

```bash
git add scripts/arp_convert_addon.py
git commit -m "feat(ux): 서브패널 등록 + 아이콘/핸들러 register/unregister"
```

---

### Task 9: 오퍼레이터 피드백 + 상태 플래그 설정

**Files:**
- Modify: `scripts/arp_ops_build.py` (build_completed 플래그)
- Modify: `scripts/arp_ops_preview.py` (bone count 캐시)
- Modify: `scripts/arp_ops_roles.py` (mapped_bone_count 업데이트)

- [ ] **Step 1: CreatePreview에서 bone count 캐시**

`scripts/arp_ops_preview.py`의 `ARPCONV_OT_CreatePreview.execute()` 끝부분에서, `_populate_hierarchy_collection()` 호출 이후에 추가:

```python
        # bone count 캐시 업데이트
        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)
        if preview_obj:
            from skeleton_analyzer import ROLE_PROP_KEY
            total = len(preview_obj.pose.bones)
            mapped = sum(
                1
                for pb in preview_obj.pose.bones
                if pb.get(ROLE_PROP_KEY, "unmapped") != "unmapped"
            )
            props.total_bone_count = total
            props.mapped_bone_count = mapped
```

- [ ] **Step 2: SetRole에서 mapped_bone_count 업데이트**

`scripts/arp_ops_roles.py`의 `ARPCONV_OT_SetRole.execute()` 끝부분, `self.report()` 직전에 추가:

```python
        # mapped_bone_count 캐시 갱신
        props = context.scene.arp_convert_props
        preview_obj = bpy.data.objects.get(props.preview_armature)
        if preview_obj:
            props.mapped_bone_count = sum(
                1
                for pb in preview_obj.pose.bones
                if pb.get(ROLE_PROP_KEY, "unmapped") != "unmapped"
            )
```

- [ ] **Step 3: BuildRig에서 build_completed 플래그 설정**

`scripts/arp_ops_build.py`의 `ARPCONV_OT_BuildRig.execute()` 끝부분, `return {'FINISHED'}` 직전에 추가:

```python
        context.scene.arp_convert_props.build_completed = True
```

- [ ] **Step 4: ruff 확인 + 테스트**

Run: `ruff check scripts/arp_ops_build.py scripts/arp_ops_preview.py scripts/arp_ops_roles.py && pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: 커밋**

```bash
git add scripts/arp_ops_build.py scripts/arp_ops_preview.py scripts/arp_ops_roles.py
git commit -m "feat(ux): 오퍼레이터에 상태 플래그 + bone count 캐시 업데이트 추가"
```

---

### Task 10: 전체 검증 + 문서 갱신

**Files:**
- Modify: `docs/ProjectPlan.md`

- [ ] **Step 1: 전체 테스트 실행**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: ruff 전체 확인**

Run: `ruff check scripts/ tests/`
Expected: PASS

- [ ] **Step 3: ProjectPlan.md 갱신**

UX 개선 관련 항목의 상태를 갱신한다. 구체적인 내용은 현재 ProjectPlan.md를 읽고 해당 기능의 체크리스트/상태를 업데이트.

- [ ] **Step 4: 최종 커밋**

```bash
git add docs/ProjectPlan.md
git commit -m "docs(ProjectPlan): UX 전면 개선 완료 상태 반영"
```

- [ ] **Step 5: Blender에서 수동 검증**

Blender를 실행하고 애드온을 로드하여 확인:

1. N-패널에 7개 서브패널이 정상 표시되는지
2. 프리뷰 생성 시 새 색상 팔레트가 적용되는지
3. 역할 버튼에 색상 아이콘이 표시되는지
4. 계층 트리에 연결선 + 색상 아이콘이 보이는지
5. 본 선택 시 부모 체인이 하이라이트되는지
6. 진행 상태 아이콘이 단계에 따라 변하는지

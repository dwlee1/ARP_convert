# F12 Animation Bake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Rig 후 소스 애니메이션을 ARP FK 컨트롤러에 COPY_TRANSFORMS + nla.bake로 복제하는 기능 구현

**Architecture:** Build Rig 완료 시 `arp_obj["arpconv_bone_pairs"]` JSON에 `(src, ctrl, is_custom)` 매핑 저장. Bake 시 임시 NLA strip으로 액션 평가, 전체 본에 COPY_TRANSFORMS(WORLD→WORLD) 추가 후 `nla.bake(visual_keying=True)` 1회 호출, constraint 제거, 역할 본 Scale FCurve 삭제.

**Tech Stack:** Blender 4.5 Python API (`bpy`), Auto-Rig Pro

**설계 문서:** `docs/F12_ExactMatch.md`

---

## 파일 구조

| 파일 | 변경 | 역할 |
|------|------|------|
| `scripts/arp_utils.py` | 수정 | `preflight_check_transforms()`, `bake_with_copy_transforms()`, `bake_all_actions()` 추가 |
| `scripts/arp_convert_addon.py` | 수정 | Build Rig 완료 시 bone_pairs 저장, `ARPCONV_OT_BakeAnimation` 오퍼레이터 + UI |
| `scripts/pipeline_runner.py` | 수정 | `--bake` 플래그, Build Rig 후 조건부 bake 호출 |
| `tests/test_bake_utils.py` | 생성 | bone_pairs 직렬화, Scale FCurve 삭제, preflight 로직 단위 테스트 |

---

### Task 1: bone_pairs 직렬화 유틸리티 + 테스트

Build Rig 결과를 JSON으로 저장/로드하는 함수. Blender 없이 테스트 가능한 순수 Python.

**Files:**
- Modify: `scripts/arp_utils.py` (line 193 이후 추가)
- Create: `tests/test_bake_utils.py`

- [ ] **Step 1: 테스트 작성**

`tests/test_bake_utils.py` 생성:

```python
"""F12 베이크 유틸리티 단위 테스트 (Blender 불필요)."""

import json

from arp_utils import serialize_bone_pairs, deserialize_bone_pairs


class TestBonePairsSerialization:
    def test_roundtrip(self):
        pairs = [
            ("thigh_L", "c_thigh_fk.l", False),
            ("eye_L", "eye_L", True),
        ]
        serialized = serialize_bone_pairs(pairs)
        result = deserialize_bone_pairs(serialized)
        assert result == pairs

    def test_serialize_returns_json_string(self):
        pairs = [("spine01", "c_spine_01.x", False)]
        serialized = serialize_bone_pairs(pairs)
        parsed = json.loads(serialized)
        assert isinstance(parsed, list)
        assert parsed[0] == ["spine01", "c_spine_01.x", False]

    def test_deserialize_empty(self):
        result = deserialize_bone_pairs("[]")
        assert result == []

    def test_deserialize_converts_lists_to_tuples(self):
        raw = json.dumps([["a", "b", True]])
        result = deserialize_bone_pairs(raw)
        assert result == [("a", "b", True)]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_bake_utils.py -v`
Expected: FAIL — `ImportError: cannot import name 'serialize_bone_pairs'`

- [ ] **Step 3: 구현**

`scripts/arp_utils.py` 파일 끝(line 193 이후)에 추가:

```python
# ═══════════════════════════════════════════════════════════════
# F12: 애니메이션 베이크 유틸리티
# ═══════════════════════════════════════════════════════════════

BAKE_PAIRS_KEY = "arpconv_bone_pairs"
BAKE_CONSTRAINT_NAME = "ARPCONV_CopyTF"


def serialize_bone_pairs(pairs):
    """bone_pairs 리스트를 JSON 문자열로 직렬화.

    Args:
        pairs: [(source_bone, arp_controller, is_custom), ...]

    Returns:
        str: JSON 문자열
    """
    return json.dumps([list(t) for t in pairs], ensure_ascii=False)


def deserialize_bone_pairs(json_str):
    """JSON 문자열에서 bone_pairs 리스트 복원.

    Returns:
        list[tuple]: [(source_bone, arp_controller, is_custom), ...]
    """
    raw = json.loads(json_str)
    return [(r[0], r[1], r[2]) for r in raw]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_bake_utils.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add scripts/arp_utils.py tests/test_bake_utils.py
git commit -m "feat(F12): bone_pairs 직렬화 유틸리티 + 테스트"
```

---

### Task 2: Build Rig 완료 시 bone_pairs 저장

Build Rig 오퍼레이터가 완료될 때 `deform_to_ref` + `cc_bone_map`을 합쳐서 `arp_obj["arpconv_bone_pairs"]`에 저장.

**Files:**
- Modify: `scripts/arp_convert_addon.py:2493` (Build Rig return 직전)

- [ ] **Step 1: bone_pairs 구성 + 저장 코드 삽입**

`scripts/arp_convert_addon.py`에서 Build Rig의 `return {"FINISHED"}` 직전(line 2494)에 삽입:

```python
        # ── F12: bone_pairs 저장 ──
        from arp_utils import serialize_bone_pairs, BAKE_PAIRS_KEY
        from skeleton_analyzer import discover_arp_ctrl_map

        bone_pairs = []

        # 역할 매핑 본: deform_to_ref → discover_arp_ctrl_map으로 컨트롤러 탐색
        ctrl_map = discover_arp_ctrl_map(arp_obj)
        # arp_chains의 역산: ref_name → (role, index)
        ref_to_role_idx = {}
        for role, refs in arp_chains.items():
            for idx, ref_name in enumerate(refs):
                ref_to_role_idx[ref_name] = (role, idx)

        for src_name, ref_name in deform_to_ref.items():
            role_idx = ref_to_role_idx.get(ref_name)
            if role_idx and role_idx[0] in ctrl_map:
                ctrls = ctrl_map[role_idx[0]]
                if role_idx[1] < len(ctrls):
                    bone_pairs.append((src_name, ctrls[role_idx[1]], False))

        # cc_ 커스텀 본: 이름 동일 매핑
        for cc_src in custom_bones:
            cc_name = _make_cc_bone_name(cc_src)
            if arp_obj.data.bones.get(cc_name):
                bone_pairs.append((cc_src, cc_name, True))

        arp_obj[BAKE_PAIRS_KEY] = serialize_bone_pairs(bone_pairs)
        log(f"  bone_pairs 저장: {len(bone_pairs)}쌍 (역할 {sum(1 for _,_,c in bone_pairs if not c)}, 커스텀 {sum(1 for _,_,c in bone_pairs if c)})")
```

- [ ] **Step 2: 기존 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 기존 테스트 통과 (arp_convert_addon.py 변경은 bpy mock 환경에서 import되지 않음)

- [ ] **Step 3: 커밋**

```bash
git add scripts/arp_convert_addon.py
git commit -m "feat(F12): Build Rig 완료 시 bone_pairs JSON 저장"
```

---

### Task 3: preflight_check_transforms 구현

오브젝트 transform 검증 함수. Blender API 의존이므로 별도 단위 테스트 없이 통합 테스트에서 검증.

**Files:**
- Modify: `scripts/arp_utils.py` (serialize/deserialize 아래 추가)

- [ ] **Step 1: preflight 함수 구현**

`scripts/arp_utils.py`에 추가:

```python
def preflight_check_transforms(source_obj, arp_obj):
    """베이크 전 오브젝트 transform 검증. 실패 시 에러 메시지 반환.

    Args:
        source_obj: 소스 아마추어 오브젝트
        arp_obj: ARP 아마추어 오브젝트

    Returns:
        str or None: 에러 메시지 (None이면 통과)
    """
    from mathutils import Vector

    tolerance = 1e-4
    for obj, label in [(source_obj, "소스"), (arp_obj, "ARP")]:
        loc = obj.location
        rot = obj.rotation_euler
        scale = obj.scale
        if (loc - Vector((0, 0, 0))).length > tolerance:
            return f"{label} 아마추어 위치가 원점이 아닙니다: {tuple(round(v, 4) for v in loc)}"
        if (Vector(rot) - Vector((0, 0, 0))).length > tolerance:
            return f"{label} 아마추어 회전이 0이 아닙니다: {tuple(round(v, 4) for v in rot)}"
        if (scale - Vector((1, 1, 1))).length > tolerance:
            return f"{label} 아마추어 스케일이 1이 아닙니다: {tuple(round(v, 4) for v in scale)}"
    return None
```

- [ ] **Step 2: 기존 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 기존 테스트 통과

- [ ] **Step 3: 커밋**

```bash
git add scripts/arp_utils.py
git commit -m "feat(F12): preflight_check_transforms 오브젝트 transform 검증"
```

---

### Task 4: bake_with_copy_transforms 핵심 함수

단일 액션에 대해 COPY_TRANSFORMS 추가 → bake → constraint 제거 → Scale FCurve 삭제를 수행.

**Files:**
- Modify: `scripts/arp_utils.py` (preflight 아래 추가)

- [ ] **Step 1: 구현**

`scripts/arp_utils.py`에 추가:

```python
def bake_with_copy_transforms(source_obj, arp_obj, bone_pairs, frame_start, frame_end):
    """bone_pairs 기반으로 COPY_TRANSFORMS → Bake → Constraint 제거.

    Args:
        source_obj: 소스 아마추어 오브젝트
        arp_obj: ARP 아마추어 오브젝트
        bone_pairs: [(source_bone_name, arp_controller_name, is_custom), ...]
        frame_start, frame_end: 프레임 범위
    """
    ensure_object_mode()
    select_only(arp_obj)
    bpy.ops.object.mode_set(mode="POSE")

    # 1. 전체 bone_pairs에 COPY_TRANSFORMS 추가
    added_bones = []
    for src_name, ctrl_name, _is_custom in bone_pairs:
        pose_bone = arp_obj.pose.bones.get(ctrl_name)
        if pose_bone is None:
            log(f"  [WARN] ARP 컨트롤러 '{ctrl_name}' 없음 — 스킵", "WARN")
            continue
        src_bone = source_obj.pose.bones.get(src_name)
        if src_bone is None:
            log(f"  [WARN] 소스 본 '{src_name}' 없음 — 스킵", "WARN")
            continue

        con = pose_bone.constraints.new("COPY_TRANSFORMS")
        con.name = BAKE_CONSTRAINT_NAME
        con.target = source_obj
        con.subtarget = src_name
        con.target_space = "WORLD"
        con.owner_space = "WORLD"
        added_bones.append(ctrl_name)

    if not added_bones:
        log("  [WARN] 추가된 constraint 없음 — 베이크 건너뜀", "WARN")
        return

    log(f"  COPY_TRANSFORMS 추가: {len(added_bones)}개")

    # 2. bone_pairs의 컨트롤러 본만 선택
    for bone in arp_obj.data.bones:
        bone.select = False
    added_set = set(added_bones)
    for bone in arp_obj.data.bones:
        if bone.name in added_set:
            bone.select = True

    # 3. nla.bake
    bpy.ops.nla.bake(
        frame_start=frame_start,
        frame_end=frame_end,
        only_selected=True,
        visual_keying=True,
        clear_constraints=False,
        use_current_action=True,
        bake_types={"POSE"},
    )
    log(f"  nla.bake 완료: {frame_start}~{frame_end}")

    # 4. ARPCONV_CopyTF constraint만 제거
    for ctrl_name in added_bones:
        pose_bone = arp_obj.pose.bones.get(ctrl_name)
        if pose_bone is None:
            continue
        for con in list(pose_bone.constraints):
            if con.name == BAKE_CONSTRAINT_NAME:
                pose_bone.constraints.remove(con)

    # 5. 역할 본(is_custom=False)의 Scale FCurve 삭제
    action = arp_obj.animation_data.action if arp_obj.animation_data else None
    if action:
        non_custom_ctrls = {ctrl for _, ctrl, is_custom in bone_pairs if not is_custom}
        fcurves_to_remove = []
        for fc in action.fcurves:
            if fc.data_path.startswith("pose.bones["):
                # pose.bones["name"].scale → 본 이름 추출
                try:
                    bone_name = fc.data_path.split('"')[1]
                except IndexError:
                    continue
                if bone_name in non_custom_ctrls and ".scale" in fc.data_path:
                    fcurves_to_remove.append(fc)
        for fc in fcurves_to_remove:
            action.fcurves.remove(fc)
        if fcurves_to_remove:
            log(f"  Scale FCurve 삭제: {len(fcurves_to_remove)}개 (역할 본)")

    ensure_object_mode()
```

- [ ] **Step 2: 기존 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 기존 테스트 통과

- [ ] **Step 3: 커밋**

```bash
git add scripts/arp_utils.py
git commit -m "feat(F12): bake_with_copy_transforms 핵심 베이크 함수"
```

---

### Task 5: bake_all_actions 액션 순회 함수

임시 NLA strip + 기존 NLA mute 패턴으로 모든 액션을 순회하며 베이크.

**Files:**
- Modify: `scripts/arp_utils.py` (bake_with_copy_transforms 아래 추가)

- [ ] **Step 1: 구현**

`scripts/arp_utils.py`에 추가:

```python
def _collect_actions_for_armature(armature_obj):
    """아마추어에 관련된 모든 액션을 수집.

    Returns:
        list[bpy.types.Action]: 액션 리스트
    """
    actions = []
    armature_bone_names = {b.name for b in armature_obj.data.bones}

    for action in bpy.data.actions:
        # 이 액션이 해당 아마추어의 본을 참조하는지 확인
        dominated = False
        for fc in action.fcurves:
            if fc.data_path.startswith("pose.bones["):
                try:
                    bone_name = fc.data_path.split('"')[1]
                except IndexError:
                    continue
                if bone_name in armature_bone_names:
                    dominated = True
                    break
        if dominated:
            actions.append(action)

    return actions


def bake_all_actions(source_obj, arp_obj, bone_pairs):
    """소스 아마추어의 모든 액션을 순회하며 ARP 컨트롤러에 베이크.

    Args:
        source_obj: 소스 아마추어 오브젝트
        arp_obj: ARP 아마추어 오브젝트
        bone_pairs: [(source_bone_name, arp_controller_name, is_custom), ...]

    Returns:
        list[str]: 생성된 ARP 액션 이름 리스트
    """
    actions = _collect_actions_for_armature(source_obj)
    if not actions:
        log("  베이크할 액션이 없습니다.", "WARN")
        return []

    log(f"액션 {len(actions)}개 발견, 베이크 시작")

    # 소스 NLA 트랙 상태 저장
    anim_data = source_obj.animation_data
    if anim_data is None:
        source_obj.animation_data_create()
        anim_data = source_obj.animation_data

    # ARP에도 animation_data 보장
    if arp_obj.animation_data is None:
        arp_obj.animation_data_create()

    original_mute_states = [(t, t.mute) for t in anim_data.nla_tracks]
    created_actions = []

    for action_idx, action in enumerate(actions):
        action_name = action.name
        frame_start = int(action.frame_range[0])
        frame_end = int(action.frame_range[1])
        arp_action_name = f"{action_name}_arp"

        log(f"  [{action_idx + 1}/{len(actions)}] '{action_name}' ({frame_start}~{frame_end})")

        # 기존 _arp 액션 삭제
        existing_arp = bpy.data.actions.get(arp_action_name)
        if existing_arp:
            bpy.data.actions.remove(existing_arp)
            log(f"    기존 '{arp_action_name}' 삭제")

        # ARP에 새 액션 생성
        arp_action = bpy.data.actions.new(name=arp_action_name)
        arp_action.use_fake_user = True
        arp_obj.animation_data.action = arp_action

        # 기존 NLA 트랙 뮤트
        for track, _ in original_mute_states:
            track.mute = True

        # 임시 NLA strip으로 액션 평가
        tmp_track = anim_data.nla_tracks.new()
        tmp_track.name = "_arpconv_tmp"
        tmp_strip = tmp_track.strips.new(action_name, int(action.frame_range[0]), action)
        tmp_strip.action_frame_start = frame_start
        tmp_strip.action_frame_end = frame_end

        try:
            bake_with_copy_transforms(source_obj, arp_obj, bone_pairs, frame_start, frame_end)
            created_actions.append(arp_action_name)
            log(f"    → '{arp_action_name}' 생성 완료")
        except Exception as e:
            log(f"    베이크 실패: {e}", "ERROR")
            # 실패한 액션 정리
            if arp_obj.animation_data and arp_obj.animation_data.action == arp_action:
                arp_obj.animation_data.action = None
            bpy.data.actions.remove(arp_action)
        finally:
            # 임시 NLA strip/track 제거
            anim_data.nla_tracks.remove(tmp_track)
            # NLA 뮤트 복원
            for track, was_muted in original_mute_states:
                track.mute = was_muted
            # 잔여 constraint 정리
            ensure_object_mode()
            for _, ctrl_name, _ in bone_pairs:
                pose_bone = arp_obj.pose.bones.get(ctrl_name)
                if pose_bone is None:
                    continue
                for con in list(pose_bone.constraints):
                    if con.name == BAKE_CONSTRAINT_NAME:
                        pose_bone.constraints.remove(con)

    log(f"베이크 완료: {len(created_actions)}/{len(actions)} 액션 성공")
    return created_actions
```

- [ ] **Step 2: 기존 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 기존 테스트 통과

- [ ] **Step 3: 커밋**

```bash
git add scripts/arp_utils.py
git commit -m "feat(F12): bake_all_actions NLA strip 기반 액션 순회 + 베이크"
```

---

### Task 6: ARPCONV_OT_BakeAnimation 오퍼레이터 + UI

addon에 "Step 4: Bake Animation" 버튼 추가.

**Files:**
- Modify: `scripts/arp_convert_addon.py:2496` (BuildRig 클래스 아래에 새 오퍼레이터)
- Modify: `scripts/arp_convert_addon.py:2796` (UI 패널에 Step 4 추가)
- Modify: `scripts/arp_convert_addon.py:2818` (classes 리스트에 등록)

- [ ] **Step 1: 오퍼레이터 클래스 작성**

`scripts/arp_convert_addon.py`에서 `ARPCONV_OT_BuildRig` 클래스 직후 (line 2496 뒤, `# 오퍼레이터: 회귀 테스트` 섹션 앞)에 삽입:

```python
# ═══════════════════════════════════════════════════════════════
# 오퍼레이터: Step 4 — 애니메이션 베이크
# ═══════════════════════════════════════════════════════════════


class ARPCONV_OT_BakeAnimation(Operator):
    """COPY_TRANSFORMS 기반 애니메이션 베이크"""

    bl_idname = "arp_convert.bake_animation"
    bl_label = "애니메이션 베이크"
    bl_description = "소스 애니메이션을 ARP FK 컨트롤러에 COPY_TRANSFORMS로 베이크"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        from arp_utils import (
            BAKE_PAIRS_KEY,
            bake_all_actions,
            deserialize_bone_pairs,
            find_arp_armature,
            find_source_armature,
            log,
            preflight_check_transforms,
        )

        source_obj = find_source_armature()
        if source_obj is None:
            self.report({"ERROR"}, "소스 아마추어를 찾을 수 없습니다.")
            return {"CANCELLED"}

        arp_obj = find_arp_armature()
        if arp_obj is None:
            self.report({"ERROR"}, "ARP 아마추어를 찾을 수 없습니다.")
            return {"CANCELLED"}

        # bone_pairs 로드
        raw_pairs = arp_obj.get(BAKE_PAIRS_KEY)
        if not raw_pairs:
            self.report({"ERROR"}, "bone_pairs가 없습니다. Build Rig를 먼저 실행하세요.")
            return {"CANCELLED"}

        bone_pairs = deserialize_bone_pairs(raw_pairs)
        if not bone_pairs:
            self.report({"ERROR"}, "bone_pairs가 비어있습니다.")
            return {"CANCELLED"}

        # Preflight check
        error = preflight_check_transforms(source_obj, arp_obj)
        if error:
            self.report({"ERROR"}, f"Preflight 실패: {error}")
            return {"CANCELLED"}

        log("=" * 50)
        log("Step 4: 애니메이션 베이크 (COPY_TRANSFORMS)")
        log("=" * 50)

        created = bake_all_actions(source_obj, arp_obj, bone_pairs)

        self.report({"INFO"}, f"베이크 완료: {len(created)}개 액션 생성")
        return {"FINISHED"}
```

- [ ] **Step 2: UI 패널에 Step 4 추가**

`scripts/arp_convert_addon.py`의 UI 패널에서 Step 3 뒤의 `layout.separator()` (line 2796) 다음에 삽입:

```python
        # Step 4: 애니메이션 베이크
        box = layout.box()
        box.label(text="Step 4: Bake Animation", icon="ACTION")
        row = box.row()
        row.scale_y = 1.3
        row.operator("arp_convert.bake_animation", icon="ACTION")
```

- [ ] **Step 3: classes 리스트에 등록**

`scripts/arp_convert_addon.py`의 classes 리스트에서 `ARPCONV_OT_RunRegression` 앞에 추가:

```python
    ARPCONV_OT_BakeAnimation,
```

- [ ] **Step 4: 기존 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 기존 테스트 통과

- [ ] **Step 5: 커밋**

```bash
git add scripts/arp_convert_addon.py
git commit -m "feat(F12): ARPCONV_OT_BakeAnimation 오퍼레이터 + Step 4 UI"
```

---

### Task 7: pipeline_runner.py --bake 플래그

비대화형 파이프라인에서 Build Rig 후 조건부로 베이크 실행.

**Files:**
- Modify: `scripts/pipeline_runner.py:51` (argparse에 --bake 추가)
- Modify: `scripts/pipeline_runner.py:344` (Build Rig 후 bake 호출)

- [ ] **Step 1: --bake 플래그 추가**

`scripts/pipeline_runner.py`의 `parse_args()` 함수에서 `--auto` 처리 다음에 추가:

```python
        elif custom_args[i] == "--bake":
            args["bake"] = True
            i += 1
```

- [ ] **Step 2: Build Rig 후 bake 호출 추가**

`scripts/pipeline_runner.py`에서 `result.add_step("rig_generated")` (line 344) 다음, `except` 블록 전에 삽입:

```python
        # F12: 애니메이션 베이크 (--bake 플래그 시)
        if args.get("bake"):
            from arp_utils import (
                BAKE_PAIRS_KEY,
                bake_all_actions,
                deserialize_bone_pairs,
                preflight_check_transforms,
            )

            log("=" * 50)
            log("F12: 애니메이션 베이크")
            log("=" * 50)

            error = preflight_check_transforms(source_obj, arp_obj)
            if error:
                log(f"Preflight 실패: {error}", "ERROR")
                result.add_error(f"베이크 Preflight 실패: {error}")
            else:
                raw_pairs = arp_obj.get(BAKE_PAIRS_KEY)
                if raw_pairs:
                    bone_pairs = deserialize_bone_pairs(raw_pairs)
                    created = bake_all_actions(source_obj, arp_obj, bone_pairs)
                    result.add_step("animation_baked")
                    log(f"베이크 완료: {len(created)}개 액션")
                else:
                    log("bone_pairs 없음 — 베이크 건너뜀", "WARN")
```

- [ ] **Step 3: 기존 테스트 통과 확인**

Run: `pytest tests/ -v`
Expected: 모든 기존 테스트 통과

- [ ] **Step 4: 커밋**

```bash
git add scripts/pipeline_runner.py
git commit -m "feat(F12): pipeline_runner --bake 플래그로 조건부 베이크"
```

---

### Task 8: /sync-addon + 전체 테스트 + 최종 검증

addon 동기화 및 최종 검증.

**Files:**
- 전체 프로젝트

- [ ] **Step 1: /sync-addon 실행**

하드 링크 동기화로 Blender addons 폴더에 최신 코드 반영.

- [ ] **Step 2: 전체 테스트 실행**

Run: `pytest tests/ -v`
Expected: 모든 테스트 통과

- [ ] **Step 3: retarget 잔존 확인**

Run: `grep -rn "retarget\|run_retarget" scripts/*.py`
Expected: `diagnose_arp_operators.py`의 ARP 오퍼레이터 목록만 검출

- [ ] **Step 4: 최종 커밋**

```bash
git add -A
git commit -m "feat(F12): 애니메이션 베이크 구현 완료"
```

---

## 검증 (Blender 내 수동 테스트)

구현 후 Blender에서 수동 검증:

1. 여우 테스트 파일 열기 → Step 1 (Preview) → Step 2 (역할 확인) → Step 3 (Build Rig) → Step 4 (Bake Animation)
2. 타임라인 재생 — 원본과 ARP 리그의 모션이 동일한지 확인
3. spine/head에 Location 키가 있는 소스 → 위치값 정상 전달 확인
4. 다중 액션 파일에서 각 액션별 `_arp` 생성 확인
5. Preflight: ARP 오브젝트 위치를 (1,0,0)으로 이동 후 Bake → 에러 메시지 확인
6. 재실행: 같은 파일에서 Bake 두 번 실행 → 기존 `_arp` 액션 정상 교체 확인

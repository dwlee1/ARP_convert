# Unity 이주 Phase 0 + Phase 1 + pre-pilot 도구 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unity 프로젝트 이주 설계의 Phase 0(인벤토리) + Phase 1(Rabbit 파일럿)을 실행하고, 파일럿에 필요한 pre-pilot 도구 `tools/fbx_to_blend.py`를 빌드한다.

**Architecture:** 순수 Python 스크립트 2개(`tools/build_migration_inventory.py`, `tools/fbx_to_blend.py`)를 TDD로 만든다. 그 외 Phase 1 단계(1a, 1c~1h)는 Blender/Unity 수작업이며 산출물은 마크다운 리포트로 문서화한다. 기존 BlenderRigConvert 애드온은 수정하지 않는다.

**Tech Stack:** Python 3.11 표준 라이브러리(`csv`, `re`, `pathlib`, `argparse`), pytest, Blender 4.5 (headless `--background --python` 호출), ARP 애드온, Unity 2022 LTS

**스펙:** `docs/superpowers/specs/2026-04-16-unity-migration-design.md`

**범위 밖 (이 플랜이 다루지 않음):** Phase 2 도구화 결정 게이트, Phase 3 배치 20마리, Phase 4 마무리. 각각 별도 계획 문서로 분기한다.

**작업 브랜치:**
- BlenderRigConvert 레포: `feat/unity-migration-p0-p1` — 도구 2개, 테스트, Phase 0 CSV, Phase 1 리포트
- Unity 레포(`C:\Users\manag\GitProject\LittleWitchForestMobile`): `migration/pilot-rabbit` — Task 15부터 cut, FBX swap + .meta 유지

---

### Task 1: 작업 브랜치 + 디렉터리 스캐폴딩

**Files:**
- Modify: `.gitignore`
- Create: `tests/fixtures/unity_migration/` (디렉터리)
- Create: `docs/superpowers/pilot/` (디렉터리)
- Create: `pilot/` (디렉터리, `.gitignore` 처리)

- [ ] **Step 1: 브랜치 cut**

```bash
cd C:/Users/manag/Desktop/BlenderRigConvert
git checkout -b feat/unity-migration-p0-p1
```

- [ ] **Step 2: 디렉터리 생성**

```bash
mkdir -p tests/fixtures/unity_migration
mkdir -p docs/superpowers/pilot
mkdir -p pilot/exports
```

- [ ] **Step 3: `.gitignore`에 pilot 바이너리 제외**

`.gitignore` 끝에 추가:

```
# Unity 이주 파일럿 중간 산출물 (binary blend/fbx)
pilot/*.blend
pilot/exports/
```

- [ ] **Step 4: 커밋**

```bash
git add .gitignore
git commit -m "chore(migration): Unity 이주 p0-p1 스캐폴딩 (gitignore + dirs)"
```

---

### Task 2: Unity .meta GUID 파서 (TDD)

**Files:**
- Create: `tests/fixtures/unity_migration/rabbit_animation.fbx.meta`
- Create: `tests/test_build_migration_inventory.py`
- Create: `tools/build_migration_inventory.py`

- [ ] **Step 1: fixture 작성 — 실제 Unity .meta 구조 축약본**

`tests/fixtures/unity_migration/rabbit_animation.fbx.meta`:

```yaml
fileFormatVersion: 2
guid: f01ef593d9cf73a4e94a2ab37b4745c1
ModelImporter:
  serializedVersion: 22200
  internalIDToNameTable:
  - first:
      74: 7400000
    second: Rabbit_idle
  - first:
      74: 7400002
    second: Rabbit_walk
  - first:
      74: 7400004
    second: Rabbit_run
  animationType: 2
```

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_build_migration_inventory.py` 신규 파일:

```python
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "unity_migration"

import build_migration_inventory as bmi


def test_parse_meta_guid_extracts_top_level_guid():
    meta_path = FIXTURE_DIR / "rabbit_animation.fbx.meta"
    assert bmi.parse_meta_guid(meta_path) == "f01ef593d9cf73a4e94a2ab37b4745c1"


def test_parse_meta_guid_returns_none_if_missing(tmp_path):
    bad_meta = tmp_path / "no_guid.meta"
    bad_meta.write_text("fileFormatVersion: 2\n", encoding="utf-8")
    assert bmi.parse_meta_guid(bad_meta) is None
```

- [ ] **Step 3: 테스트 실행 — 실패 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'build_migration_inventory'`

- [ ] **Step 4: 최소 구현**

`tools/build_migration_inventory.py` 신규 파일:

```python
"""Unity 프로젝트 animation FBX 인벤토리 CSV 생성.

Usage:
    python tools/build_migration_inventory.py \\
        --unity-root "C:/Users/manag/GitProject/LittleWitchForestMobile" \\
        --output docs/MigrationInventory.csv
"""

from __future__ import annotations

import re
from pathlib import Path

_GUID_RE = re.compile(r"^guid:\s*([0-9a-f]{32})\s*$", re.MULTILINE)


def parse_meta_guid(meta_path: Path) -> str | None:
    """.meta 파일 최상위 `guid:` 라인에서 32자리 hex 추출."""
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _GUID_RE.search(text)
    return m.group(1) if m else None
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 2 passed

- [ ] **Step 6: 커밋**

```bash
git add tests/fixtures/unity_migration/rabbit_animation.fbx.meta \
        tests/test_build_migration_inventory.py \
        tools/build_migration_inventory.py
git commit -m "feat(migration): .meta guid 파서 추가 (Phase 0)"
```

---

### Task 3: .meta에서 AnimationClip 이름 추출 (TDD)

**Files:**
- Modify: `tests/test_build_migration_inventory.py`
- Modify: `tools/build_migration_inventory.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_build_migration_inventory.py` 끝에 추가:

```python
def test_parse_meta_clip_names_extracts_ordered_list():
    meta_path = FIXTURE_DIR / "rabbit_animation.fbx.meta"
    clips = bmi.parse_meta_clip_names(meta_path)
    assert clips == ["Rabbit_idle", "Rabbit_walk", "Rabbit_run"]


def test_parse_meta_clip_names_empty_when_no_table(tmp_path):
    meta = tmp_path / "no_clips.fbx.meta"
    meta.write_text("guid: abc\nModelImporter:\n  serializedVersion: 1\n", encoding="utf-8")
    assert bmi.parse_meta_clip_names(meta) == []
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_build_migration_inventory.py::test_parse_meta_clip_names_extracts_ordered_list -v
```
Expected: FAIL with `AttributeError: module ... has no attribute 'parse_meta_clip_names'`

- [ ] **Step 3: 구현 추가**

`tools/build_migration_inventory.py` 맨 아래에 추가:

```python
_CLIP_NAME_RE = re.compile(r"^\s*second:\s*(\S.*?)\s*$", re.MULTILINE)


def parse_meta_clip_names(meta_path: Path) -> list[str]:
    """`internalIDToNameTable` 하위 `second: <name>` 라인을 순서대로 수집."""
    try:
        text = meta_path.read_text(encoding="utf-8")
    except OSError:
        return []
    if "internalIDToNameTable:" not in text:
        return []
    return _CLIP_NAME_RE.findall(text.split("internalIDToNameTable:", 1)[1])
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add tools/build_migration_inventory.py tests/test_build_migration_inventory.py
git commit -m "feat(migration): .meta clip 이름 파서 추가"
```

---

### Task 4: AnimatorController m_Motion GUID 참조 스캐너 (TDD)

**Files:**
- Create: `tests/fixtures/unity_migration/AnimalController_0_Rabbit.controller`
- Create: `tests/fixtures/unity_migration/UnrelatedController.controller`
- Modify: `tests/test_build_migration_inventory.py`
- Modify: `tools/build_migration_inventory.py`

- [ ] **Step 1: controller fixture 2개**

`tests/fixtures/unity_migration/AnimalController_0_Rabbit.controller`:

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1102 &1
AnimatorState:
  m_Name: Idle
  m_Motion: {fileID: 7400000, guid: f01ef593d9cf73a4e94a2ab37b4745c1, type: 3}
--- !u!1102 &2
AnimatorState:
  m_Name: Walk
  m_Motion: {fileID: 7400002, guid: f01ef593d9cf73a4e94a2ab37b4745c1, type: 3}
```

`tests/fixtures/unity_migration/UnrelatedController.controller`:

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1102 &1
AnimatorState:
  m_Name: Fly
  m_Motion: {fileID: 7400000, guid: 9999999999999999999999999999abcd, type: 3}
```

- [ ] **Step 2: 실패 테스트 추가**

`tests/test_build_migration_inventory.py` 끝에 추가:

```python
def test_find_controllers_referencing_guid_returns_matches_only():
    rabbit_guid = "f01ef593d9cf73a4e94a2ab37b4745c1"
    matches = bmi.find_controllers_referencing_guid(FIXTURE_DIR, rabbit_guid)
    names = sorted(p.name for p in matches)
    assert names == ["AnimalController_0_Rabbit.controller"]


def test_find_controllers_referencing_guid_empty_when_no_match():
    matches = bmi.find_controllers_referencing_guid(FIXTURE_DIR, "0" * 32)
    assert matches == []
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/test_build_migration_inventory.py::test_find_controllers_referencing_guid_returns_matches_only -v
```
Expected: FAIL (function missing)

- [ ] **Step 4: 구현 추가**

`tools/build_migration_inventory.py` 맨 아래에 추가:

```python
def find_controllers_referencing_guid(search_root: Path, target_guid: str) -> list[Path]:
    """search_root 아래 *.controller 파일 중 m_Motion에서 target_guid 참조하는 것."""
    needle = f"guid: {target_guid}"
    matches: list[Path] = []
    for ctrl in search_root.rglob("*.controller"):
        try:
            if needle in ctrl.read_text(encoding="utf-8"):
                matches.append(ctrl)
        except OSError:
            continue
    return matches
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 6 passed

- [ ] **Step 6: 커밋**

```bash
git add tests/fixtures/unity_migration/*.controller \
        tests/test_build_migration_inventory.py \
        tools/build_migration_inventory.py
git commit -m "feat(migration): AnimatorController guid 참조 스캐너 추가"
```

---

### Task 5: Prefab m_SourcePrefab GUID 참조 카운터 (TDD)

**Files:**
- Create: `tests/fixtures/unity_migration/Animal_0.prefab`
- Create: `tests/fixtures/unity_migration/Animal_1.prefab`
- Create: `tests/fixtures/unity_migration/OtherAnimal.prefab`
- Modify: `tests/test_build_migration_inventory.py`
- Modify: `tools/build_migration_inventory.py`

- [ ] **Step 1: prefab fixture 3개**

`tests/fixtures/unity_migration/Animal_0.prefab`:

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1001 &1
PrefabInstance:
  m_SourcePrefab: {fileID: 100100000, guid: f01ef593d9cf73a4e94a2ab37b4745c1, type: 3}
```

`tests/fixtures/unity_migration/Animal_1.prefab`:

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1001 &1
PrefabInstance:
  m_SourcePrefab: {fileID: 100100000, guid: f01ef593d9cf73a4e94a2ab37b4745c1, type: 3}
```

`tests/fixtures/unity_migration/OtherAnimal.prefab`:

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1001 &1
PrefabInstance:
  m_SourcePrefab: {fileID: 100100000, guid: 9999999999999999999999999999abcd, type: 3}
```

- [ ] **Step 2: 실패 테스트 추가**

`tests/test_build_migration_inventory.py` 끝에 추가:

```python
def test_count_prefabs_referencing_guid_only_counts_matches():
    rabbit_guid = "f01ef593d9cf73a4e94a2ab37b4745c1"
    assert bmi.count_prefabs_referencing_guid(FIXTURE_DIR, rabbit_guid) == 2


def test_count_prefabs_returns_zero_when_no_match():
    assert bmi.count_prefabs_referencing_guid(FIXTURE_DIR, "0" * 32) == 0
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/test_build_migration_inventory.py::test_count_prefabs_referencing_guid_only_counts_matches -v
```
Expected: FAIL (function missing)

- [ ] **Step 4: 구현 추가**

`tools/build_migration_inventory.py` 맨 아래에 추가:

```python
def count_prefabs_referencing_guid(search_root: Path, target_guid: str) -> int:
    """search_root 아래 *.prefab 중 m_SourcePrefab이 target_guid인 파일 수."""
    needle = f"guid: {target_guid}"
    count = 0
    for pf in search_root.rglob("*.prefab"):
        try:
            text = pf.read_text(encoding="utf-8")
        except OSError:
            continue
        if "m_SourcePrefab" in text and needle in text:
            count += 1
    return count
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 8 passed

- [ ] **Step 6: 커밋**

```bash
git add tests/fixtures/unity_migration/*.prefab \
        tests/test_build_migration_inventory.py \
        tools/build_migration_inventory.py
git commit -m "feat(migration): prefab guid 참조 카운터 추가"
```

---

### Task 6: 한 animation FBX에 대한 row 조립 (TDD)

**Files:**
- Create: `tests/fixtures/mini_unity/Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx` (빈 파일)
- Create: `tests/fixtures/mini_unity/Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx.meta` (기존 fixture 복사본 배치)
- Create: `tests/fixtures/mini_unity/Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx` (빈 파일)
- Create: `tests/fixtures/mini_unity/Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx.meta`
- Create: `tests/fixtures/mini_unity/Assets/6_Animations/Animals/Controllers/Landmark/AnimalController_0_Rabbit.controller` (복사본)
- Create: `tests/fixtures/mini_unity/Assets/3_Prefabs/Animals/Animal_0.prefab` (복사본)
- Create: `tests/fixtures/mini_unity/Assets/3_Prefabs/Animals/Animal_1.prefab` (복사본)
- Modify: `tests/test_build_migration_inventory.py`
- Modify: `tools/build_migration_inventory.py`

> **Note**: fixture 트리는 `tests/fixtures/mini_unity/`에 **별도로** 둔다. 기존 Tasks 2-5 테스트는 `FIXTURE_DIR = tests/fixtures/unity_migration/`를 `rglob`하므로, 같은 경로 아래 `Assets/`를 두면 컨트롤러/프리팹이 중복 수집되어 기존 테스트가 깨진다.

- [ ] **Step 1: 미니 Unity 디렉터리 트리 구성**

기존 fixture 파일들을 `Assets/...` 경로로 복제해 실제 프로젝트 배치를 흉내 낸다.

```bash
mkdir -p "tests/fixtures/mini_unity/Assets/5_Models/02. Animals/00.Rabbit"
mkdir -p "tests/fixtures/mini_unity/Assets/6_Animations/Animals/Controllers/Landmark"
mkdir -p "tests/fixtures/mini_unity/Assets/3_Prefabs/Animals"

cd tests/fixtures
touch "mini_unity/Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx"
cp unity_migration/rabbit_animation.fbx.meta "mini_unity/Assets/5_Models/02. Animals/00.Rabbit/"

touch "mini_unity/Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx"
cat > "mini_unity/Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx.meta" <<'EOF'
fileFormatVersion: 2
guid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
ModelImporter:
  serializedVersion: 22200
EOF

cp unity_migration/AnimalController_0_Rabbit.controller "mini_unity/Assets/6_Animations/Animals/Controllers/Landmark/"
cp unity_migration/Animal_0.prefab "mini_unity/Assets/3_Prefabs/Animals/"
cp unity_migration/Animal_1.prefab "mini_unity/Assets/3_Prefabs/Animals/"
cd ../..
```

테스트 파일 상단에 `MINI_UNITY_DIR = PROJECT_ROOT / "tests" / "fixtures" / "mini_unity"` 추가.

- [ ] **Step 2: 실패 테스트 추가**

`tests/test_build_migration_inventory.py` 끝에 추가:

```python
def test_build_row_for_rabbit_animation_fbx():
    unity_root = MINI_UNITY_DIR
    fbx = unity_root / "Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx"
    row = bmi.build_row(fbx, unity_root)

    assert row["id"] == "Rabbit"
    assert row["animation_fbx_path"] == "Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx"
    assert row["animation_fbx_guid"] == "f01ef593d9cf73a4e94a2ab37b4745c1"
    assert row["model_fbx_paths"] == ["Rabbit_DutchBrown.fbx"]
    assert any("AnimalController_0_Rabbit" in p for p in row["controller_paths"])
    assert row["prefab_count"] == 2
    assert row["clip_count"] == 3
    assert row["clip_names"] == ["Rabbit_idle", "Rabbit_walk", "Rabbit_run"]
    assert row["locomotion"] == "pending"
    assert row["scope"] == "pending"
    assert row["status"] == "not_started"
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/test_build_migration_inventory.py::test_build_row_for_rabbit_animation_fbx -v
```
Expected: FAIL

- [ ] **Step 4: 구현 추가**

`tools/build_migration_inventory.py` 맨 아래에 추가:

```python
def _derive_id_from_folder(animation_fbx_path: Path) -> str:
    """부모 폴더명을 id로 사용. `00.Rabbit` → `Rabbit`."""
    folder = animation_fbx_path.parent.name
    if "." in folder:
        folder = folder.split(".", 1)[1]
    return folder


def build_row(animation_fbx: Path, unity_root: Path) -> dict:
    """animation FBX 1개에 대한 CSV row 조립. guid/클립/컨트롤러/프리팹 참조 계산."""
    meta = animation_fbx.with_suffix(animation_fbx.suffix + ".meta")
    guid = parse_meta_guid(meta) or ""
    clip_names = parse_meta_clip_names(meta)

    model_fbxs = sorted(
        p.name
        for p in animation_fbx.parent.glob("*.fbx")
        if p.name != animation_fbx.name
    )

    controllers_root = unity_root / "Assets" / "6_Animations" / "Animals" / "Controllers"
    prefabs_root = unity_root / "Assets" / "3_Prefabs" / "Animals"

    controller_paths = [
        str(p.relative_to(unity_root)).replace("\\", "/")
        for p in find_controllers_referencing_guid(controllers_root, guid)
    ] if guid else []
    prefab_count = count_prefabs_referencing_guid(prefabs_root, guid) if guid else 0

    return {
        "id": _derive_id_from_folder(animation_fbx),
        "animation_fbx_path": str(animation_fbx.relative_to(unity_root)).replace("\\", "/"),
        "animation_fbx_guid": guid,
        "model_fbx_paths": model_fbxs,
        "controller_paths": controller_paths,
        "prefab_count": prefab_count,
        "clip_count": len(clip_names),
        "clip_names": clip_names,
        "locomotion": "pending",
        "scope": "pending",
        "source_blend_hint": "",
        "status": "not_started",
        "notes": "",
    }
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 9 passed

- [ ] **Step 6: 커밋**

```bash
git add tests/fixtures/mini_unity \
        tests/test_build_migration_inventory.py \
        tools/build_migration_inventory.py
git commit -m "feat(migration): animation FBX row 조립 함수 추가"
```

---

### Task 7: CSV 쓰기 + main 엔트리 (TDD)

**Files:**
- Modify: `tests/test_build_migration_inventory.py`
- Modify: `tools/build_migration_inventory.py`

- [ ] **Step 1: 실패 테스트 추가**

`tests/test_build_migration_inventory.py` 끝에 추가:

```python
import csv


def test_write_csv_produces_expected_header_and_row(tmp_path):
    row = {
        "id": "Rabbit",
        "animation_fbx_path": "Assets/x.fbx",
        "animation_fbx_guid": "g",
        "model_fbx_paths": ["a.fbx", "b.fbx"],
        "controller_paths": ["c.controller"],
        "prefab_count": 2,
        "clip_count": 3,
        "clip_names": ["Rabbit_idle", "Rabbit_walk", "Rabbit_run"],
        "locomotion": "pending",
        "scope": "pending",
        "source_blend_hint": "",
        "status": "not_started",
        "notes": "",
    }
    out = tmp_path / "inv.csv"
    bmi.write_csv([row], out)

    with out.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    assert rows[0]["id"] == "Rabbit"
    assert rows[0]["model_fbx_paths"] == "a.fbx;b.fbx"
    assert rows[0]["clip_names"] == "Rabbit_idle;Rabbit_walk;Rabbit_run"
    assert rows[0]["prefab_count"] == "2"


def test_collect_rows_scans_animation_fbxs_under_assets():
    rows = bmi.collect_rows(MINI_UNITY_DIR)
    assert len(rows) == 1
    assert rows[0]["id"] == "Rabbit"
```

- [ ] **Step 2: 실패 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 2 new tests FAIL (functions missing)

- [ ] **Step 3: 구현 추가 — write_csv + collect_rows + main**

`tools/build_migration_inventory.py` 맨 아래에 추가:

```python
import argparse
import csv
import sys


CSV_COLUMNS = [
    "id",
    "animation_fbx_path",
    "animation_fbx_guid",
    "model_fbx_paths",
    "controller_paths",
    "prefab_count",
    "clip_count",
    "clip_names",
    "locomotion",
    "scope",
    "source_blend_hint",
    "status",
    "notes",
]


def _encode_list(v):
    if isinstance(v, list):
        return ";".join(v)
    return v


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _encode_list(row.get(col, "")) for col in CSV_COLUMNS})


def collect_rows(unity_root: Path) -> list[dict]:
    animals_root = unity_root / "Assets" / "5_Models" / "02. Animals"
    animation_fbxs = sorted(
        p for p in animals_root.rglob("*.fbx") if "animation" in p.stem.lower()
    )
    return [build_row(fbx, unity_root) for fbx in animation_fbxs]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Unity 이주 인벤토리 CSV 생성")
    parser.add_argument("--unity-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    rows = collect_rows(args.unity_root)
    write_csv(rows, args.output)
    print(f"[inventory] {len(rows)} rows written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_build_migration_inventory.py -v
```
Expected: 11 passed

- [ ] **Step 5: ruff 확인**

```bash
ruff check tools/build_migration_inventory.py tests/test_build_migration_inventory.py
```
Expected: no errors (or fix reported ones, typically import 순서)

- [ ] **Step 6: 커밋**

```bash
git add tools/build_migration_inventory.py tests/test_build_migration_inventory.py
git commit -m "feat(migration): CSV 쓰기 + main 엔트리 추가 (Phase 0 완성)"
```

---

### Task 8: Phase 0 실행 + locomotion 수동 분류

**Files:**
- Create: `docs/MigrationInventory.csv`
- Modify: `docs/MigrationInventory.csv` (수동 locomotion/scope 편집)

- [ ] **Step 1: Unity 프로젝트에 대해 스크립트 실행**

```bash
python tools/build_migration_inventory.py \
  --unity-root "C:/Users/manag/GitProject/LittleWitchForestMobile" \
  --output docs/MigrationInventory.csv
```

Expected: `[inventory] N rows written to docs/MigrationInventory.csv` — N은 약 42.

- [ ] **Step 2: 로우 수 검증**

```bash
python -c "import csv; rows = list(csv.DictReader(open('docs/MigrationInventory.csv', encoding='utf-8'))); print(f'total rows: {len(rows)}')"
```
Expected: `total rows: 42` (±2). 42와 크게 다르면 `Assets/5_Models/02. Animals/` 경로와 `*animation*.fbx` glob을 재확인한다.

- [ ] **Step 3: CSV 엑셀/스프레드시트로 열어 locomotion 수동 확정**

각 row를 보고 `locomotion` 컬럼을 다음 중 하나로 수정:
- `quadruped` — 사족보행 (in_scope 후보)
- `biped_bird` — 조류
- `aquatic` — 수생
- `amphibian` — 양서류 (frog, redfrog 등)
- `other` — 무척추/기타

스펙의 out_of_scope 목록 참조: `duck`, `bald_eagle`, `flamingo`, `flamingo_v1`, `dolphin`, `orca`, `baby_orca`, `swan`, `baby_duck`, `baby_eagle`, `seal`, `eagle_owl`, `puffin`, `seagull`, `sparrow`, `clam`, `crab`, `shellsand`, `albatross`, `frog`, `redfrog`.

quadruped 후보: `rabbit, lopear, fox, bear, deer, stag, wolf, turtle, llama, sheep, raccoon, baby_rabbit, baby_wolf, baby_bear, baby_turtle, blackcat, whitecat, babyfox, mole, hedgehog, capybara`.

- [ ] **Step 4: scope 컬럼 확정**

- `locomotion == quadruped` → `scope = in_scope`
- 나머지 → `scope = out_of_scope`

- [ ] **Step 5: in_scope 개수 검증**

```bash
python -c "import csv; rows = list(csv.DictReader(open('docs/MigrationInventory.csv', encoding='utf-8'))); print('in_scope:', sum(1 for r in rows if r['scope']=='in_scope'))"
```
Expected: `in_scope: 21` (±2). 벗어나면 수동 재검토 — turtle/mole이 사족인지 확인하거나 빠진 종이 있는지 확인.

- [ ] **Step 6: 커밋**

```bash
git add docs/MigrationInventory.csv
git commit -m "docs(migration): Phase 0 인벤토리 CSV 수동 분류 완료 (in_scope=21)"
```

---

### Task 9: fbx_to_blend.py 순수 헬퍼 (TDD)

**Files:**
- Create: `tests/fixtures/unity_migration/migration_inventory_sample.csv`
- Create: `tests/test_fbx_to_blend.py`
- Create: `tools/fbx_to_blend.py`

- [ ] **Step 1: 샘플 CSV fixture**

`tests/fixtures/unity_migration/migration_inventory_sample.csv`:

```csv
id,animation_fbx_path,animation_fbx_guid,model_fbx_paths,controller_paths,prefab_count,clip_count,clip_names,locomotion,scope,source_blend_hint,status,notes
Rabbit,Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx,f01ef593d9cf73a4e94a2ab37b4745c1,Rabbit_DutchBrown.fbx;Animal_2002.fbx,Assets/6_Animations/Animals/Controllers/Landmark/AnimalController_0_Rabbit.controller,38,3,Rabbit_idle;Rabbit_walk;Rabbit_run,quadruped,in_scope,,not_started,
Fox,Assets/5_Models/02. Animals/01.Fox/fox_animation.fbx,abcdef12345678901234567890123456,Fox_Silver.fbx,,0,1,Fox_idle,quadruped,in_scope,,not_started,
```

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_fbx_to_blend.py` 신규:

```python
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

FIXTURE_CSV = PROJECT_ROOT / "tests" / "fixtures" / "unity_migration" / "migration_inventory_sample.csv"

import fbx_to_blend as ftb


def test_lookup_row_by_id_finds_rabbit():
    row = ftb.lookup_row(FIXTURE_CSV, "Rabbit")
    assert row["animation_fbx_path"].endswith("rabbit_animation.fbx")
    assert row["model_fbx_paths"] == ["Rabbit_DutchBrown.fbx", "Animal_2002.fbx"]


def test_lookup_row_raises_for_unknown_id():
    with pytest.raises(KeyError, match="Unknown id"):
        ftb.lookup_row(FIXTURE_CSV, "ghostzebra")


def test_resolve_fbx_paths_returns_absolute():
    row = ftb.lookup_row(FIXTURE_CSV, "Rabbit")
    unity_root = Path("C:/Unity")
    anim, models = ftb.resolve_fbx_paths(row, unity_root)
    assert anim == unity_root / "Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx"
    assert models == [
        unity_root / "Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx",
        unity_root / "Assets/5_Models/02. Animals/00.Rabbit/Animal_2002.fbx",
    ]
```

- [ ] **Step 3: 실패 확인**

```bash
pytest tests/test_fbx_to_blend.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'fbx_to_blend'`

- [ ] **Step 4: 최소 구현**

`tools/fbx_to_blend.py` 신규:

```python
"""Unity FBX들을 하나의 blend로 재구성.

외부 실행 (Blender headless):
    blender --background --python tools/fbx_to_blend.py -- \\
        --csv docs/MigrationInventory.csv \\
        --id Rabbit \\
        --unity-root "C:/Users/manag/GitProject/LittleWitchForestMobile" \\
        --output pilot/rabbit_unity_source.blend

`bpy` 없이도 임포트 가능하도록 헬퍼와 Blender 본문을 분리한다.
"""

from __future__ import annotations

import csv
from pathlib import Path


def lookup_row(csv_path: Path, target_id: str) -> dict:
    """CSV에서 id가 일치하는 row를 dict로 반환. 없으면 KeyError."""
    with csv_path.open(encoding="utf-8", newline="") as fh:
        for raw in csv.DictReader(fh):
            if raw["id"] == target_id:
                return {
                    **raw,
                    "model_fbx_paths": [
                        s for s in (raw.get("model_fbx_paths") or "").split(";") if s
                    ],
                    "clip_names": [
                        s for s in (raw.get("clip_names") or "").split(";") if s
                    ],
                }
    raise KeyError(f"Unknown id: {target_id}")


def resolve_fbx_paths(row: dict, unity_root: Path) -> tuple[Path, list[Path]]:
    """row → (animation_fbx 절대경로, [model_fbx 절대경로...])."""
    anim = unity_root / row["animation_fbx_path"]
    anim_folder = anim.parent
    models = [anim_folder / name for name in row["model_fbx_paths"]]
    return anim, models
```

- [ ] **Step 5: 테스트 통과 확인**

```bash
pytest tests/test_fbx_to_blend.py -v
```
Expected: 3 passed

- [ ] **Step 6: 커밋**

```bash
git add tests/fixtures/unity_migration/migration_inventory_sample.csv \
        tests/test_fbx_to_blend.py \
        tools/fbx_to_blend.py
git commit -m "feat(migration): fbx_to_blend.py 순수 헬퍼 (CSV 룩업) 추가"
```

---

### Task 10: fbx_to_blend.py Blender 통합 본문

**Files:**
- Modify: `tools/fbx_to_blend.py`

- [ ] **Step 1: Blender 본문 + argparse 추가**

`tools/fbx_to_blend.py` 맨 아래에 추가:

```python
import argparse
import sys


def _reconstruct_in_blender(anim_fbx: Path, model_fbxs: list[Path], output: Path) -> None:
    """Blender 내부 전용 — factory reset → animation FBX import → model FBX import → mesh reparent → save."""
    import bpy  # noqa: PLC0415 (Blender 런타임에만 존재)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.import_scene.fbx(filepath=str(anim_fbx))
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError(f"animation FBX에 Armature 없음: {anim_fbx}")
    master_arm = armatures[0]
    master_arm.name = "Armature_" + output.stem

    for model_fbx in model_fbxs:
        before = set(bpy.data.objects.keys())
        bpy.ops.import_scene.fbx(filepath=str(model_fbx))
        added = [bpy.data.objects[n] for n in bpy.data.objects.keys() if n not in before]

        # 중복 armature는 삭제, mesh는 master armature로 re-parent
        for obj in list(added):
            if obj.type == "ARMATURE":
                bpy.data.objects.remove(obj, do_unlink=True)
            elif obj.type == "MESH":
                obj.parent = master_arm
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE":
                        mod.object = master_arm

    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output))


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        # Blender `--python ... -- --id X` 호출: `--` 이후만 파싱
        if "--" in sys.argv:
            argv = sys.argv[sys.argv.index("--") + 1 :]
        else:
            argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Unity FBX → 통합 blend 재구성")
    parser.add_argument("--csv", required=True, type=Path, help="MigrationInventory.csv 경로")
    parser.add_argument("--id", dest="target_id", required=True, help="CSV의 id 컬럼")
    parser.add_argument("--unity-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    row = lookup_row(args.csv, args.target_id)
    anim, models = resolve_fbx_paths(row, args.unity_root)

    for p in [anim, *models]:
        if not p.is_file():
            raise FileNotFoundError(p)

    _reconstruct_in_blender(anim, models, args.output)
    print(f"[fbx_to_blend] saved: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 기존 헬퍼 테스트가 여전히 통과하는지 확인**

```bash
pytest tests/test_fbx_to_blend.py -v
```
Expected: 3 passed (Blender 본문은 `bpy` import가 함수 내부라 테스트 import 방해 안 함)

- [ ] **Step 3: ruff 확인**

```bash
ruff check tools/fbx_to_blend.py tests/test_fbx_to_blend.py
```
Expected: no errors

- [ ] **Step 4: 커밋**

```bash
git add tools/fbx_to_blend.py
git commit -m "feat(migration): fbx_to_blend.py Blender 재구성 본문 추가"
```

---

### Task 11: Phase 1a — Rabbit 구조 Baseline (경량판)

**Files:**
- Create: `docs/superpowers/pilot/rabbit_baseline.md`

**메모**: 원 스펙의 Play mode 녹화 3종(idle/walk/run × 1분)은 시간 비용 대비 이득이 낮아 **제외**. 대신 `.meta` 파일에서 GUID + clip fileID 매핑만 구조적 baseline으로 뽑는다 (swap 후 GUID 유지/clip 이름 유지 확인용). Task 17 검증은 baseline 영상 대비 diff가 아닌 **절대 기준**(T-pose 없이 재생됨, Missing 경고 전수 기록)으로 판정한다.

- [ ] **Step 1: Rabbit 관련 FBX .meta 파일 6개 열기**

다음 파일들을 텍스트 에디터로 연다 (`.meta`는 YAML):
- `Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx.meta`
- `Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx.meta`
- `Assets/5_Models/02. Animals/00.Rabbit/Animal_2002.fbx.meta`
- `Assets/5_Models/02. Animals/00.Rabbit/Animal_2011.fbx.meta`
- `Assets/5_Models/02. Animals/00.Rabbit/Animal_3161.fbx.meta`
- `Assets/5_Models/02. Animals/00.Rabbit/rabbit_CherryBlossom.fbx.meta`

(CSV에서도 `id == Rabbit` row의 `animation_fbx_path` + `model_fbx_paths`로 경로 확인 가능)

- [ ] **Step 2: `rabbit_baseline.md` 작성**

`docs/superpowers/pilot/rabbit_baseline.md`:

```markdown
# Rabbit 구조 Baseline (경량)

**날짜**: YYYY-MM-DD
**대상**: `Assets/5_Models/02. Animals/00.Rabbit/`
**BlenderRigConvert 커밋**: `<git rev-parse HEAD>`
**범위 한정**: Play mode 녹화/Console 경고 capture는 시간 비용으로 생략. 구조 baseline만 유지.

## FBX GUID 전수 (swap 후 변동 없어야 함)

| FBX | GUID |
|-----|------|
| rabbit_animation.fbx | <.meta의 guid 복사> |
| Rabbit_DutchBrown.fbx | <복사> |
| Animal_2002.fbx | <복사> |
| Animal_2011.fbx | <복사> |
| Animal_3161.fbx | <복사> |
| rabbit_CherryBlossom.fbx | <복사> |

## AnimationClip fileID ↔ 이름 매핑 (Cleanup 후 유지되어야 함)

| Clip Name | fileID (10자리 정수) |
|-----------|----------------------|
| Rabbit_idle | 7400000 |
| Rabbit_walk | 7400002 |
| ... | ... |

(`rabbit_animation.fbx.meta` → `internalIDToNameTable:` 블록 전수 복사. Task 14 sandbox 반입 결과의 clip fileID와 비교하여 보존 여부 검증)
```

- [ ] **Step 3: 커밋**

```bash
git add docs/superpowers/pilot/rabbit_baseline.md
git commit -m "docs(migration): Phase 1a Rabbit 구조 baseline (녹화 생략)"
```

---

### Task 12: Phase 1b — FBX → Blender 재구성 실행

**Files:**
- Create: `pilot/rabbit_unity_source.blend` (로컬, 커밋 안 함)

- [ ] **Step 1: 스크립트 실행**

```bash
"C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" \
  --background --python tools/fbx_to_blend.py -- \
  --csv docs/MigrationInventory.csv \
  --id Rabbit \
  --unity-root "C:/Users/manag/GitProject/LittleWitchForestMobile" \
  --output "$(pwd)/pilot/rabbit_unity_source.blend"
```

Expected: 마지막 줄 `[fbx_to_blend] saved: .../pilot/rabbit_unity_source.blend`.

- [ ] **Step 2: Blender GUI에서 결과 열기**

```bash
"C:/Program Files/Blender Foundation/Blender 4.5/blender.exe" pilot/rabbit_unity_source.blend
```

- [ ] **Step 3: 육안 검증**

- [ ] Outliner에 Armature 1개만 남아 있음
- [ ] skin variant 5개 mesh(Rabbit_DutchBrown, Animal_2002, Animal_2011, Animal_3161, rabbit_CherryBlossom)가 모두 존재
- [ ] 5개 mesh 모두 Armature modifier의 Object 필드가 통합 Armature를 가리킴
- [ ] Action 개수 ≥ 26 (rabbit master FBX의 clip 수)

- [ ] **Step 4: 기능 검증 — armature root 이동**

Blender에서 Armature 선택 → Pose mode → root bone 이동 → 모든 mesh가 따라오는지 확인.

OK면 ctrl-z로 복원.

- [ ] **Step 5: 실패 시 대응**

- Armature 여러 개 남음 → `_reconstruct_in_blender`의 중복 armature 삭제 로직 재검토
- mesh가 원본 armature에 bound → modifier.object 재할당 로직 수정

수정 후 Task 9/10 테스트 재실행 + Step 1 재실행.

- [ ] **Step 6: 확인 기록 (Task 14 diagnosis에서 재사용)**

메모 파일 임시 작성: `pilot/rabbit_reconstruct_check.txt` (커밋 안 함):
```
armature count: 1
mesh count: 5
action count: 26
root follow test: OK
```

---

### Task 13: Phase 1c — BlenderRigConvert 5단계 실행

**Files:**
- Create: `pilot/rabbit_arp.blend` (로컬, 커밋 안 함)

- [ ] **Step 1: Blender에서 `pilot/rabbit_unity_source.blend` 열기**

- [ ] **Step 2: ARP Convert N-panel 노출 확인**

사이드바(N 키) → `ARP Convert` 탭. 없으면 `sync-addon` 스킬로 애드온 동기화 후 재시작.

- [ ] **Step 3: Step 1 — Create Preview**

Armature 선택 → Create Preview 클릭 → 신뢰도 표시 확인. 목표: **≥70%**.

- [ ] **Step 4: Step 2 — 역할 수정 (필요 시)**

Preview Armature의 빨강/노랑 본 탐색해 역할 수정. 얼굴 본(eye, jaw 등)은 `cc_` 커스텀 본 처리 규칙 유지 (CLAUDE.md 참고).

- [ ] **Step 5: Step 3 — Build Rig**

실행. 완료 시 ARP dog 리그가 생성됨. 에러 시 콘솔 로그 확인 + 스펙의 "파일럿 실패 시 blend-first fallback" 트리거 판단.

- [ ] **Step 6: Step 4 — Setup Retarget → Re-Retarget → Copy Custom Scale**

순서대로 실행. `_remap` 접미사가 붙은 Action이 생성되는지 확인.

- [ ] **Step 7: Step 5 — Cleanup**

소스/프리뷰 삭제 + `_remap` 접미사 제거 확인. 최종 Action 이름이 원본과 동일해야 함 (예: `Rabbit_idle`).

- [ ] **Step 8: 저장**

`File → Save As` → `pilot/rabbit_arp.blend`.

- [ ] **Step 9: 체크포인트 기록**

`pilot/rabbit_arp_check.txt` (커밋 안 함):
```
step1 confidence: NN%
step3 build rig: OK / FAIL(사유)
step4 retarget: OK / FAIL
step5 cleanup action names: <원본과 동일?> Y/N
final action count: N
```

- [ ] **Step 10: 실패 시**

Build Rig 에러나 신뢰도 <50% → 즉시 중단. 스펙의 "blend-first fallback" 경로로 설계 재고. 이 계획 범위 밖이므로 새 브레인스토밍 스킬로 이동.

---

### Task 14: Phase 1d — ARP 익스포트 → Unity sandbox

**Files:**
- Create: `pilot/exports/rabbit_animation.fbx` (로컬)
- Create: `pilot/exports/Rabbit_DutchBrown.fbx` ... (로컬)
- Create Unity: `Assets/_Migration_Sandbox/Rabbit/` 하위 FBX 반입

- [ ] **Step 1: ARP 익스포터로 animation FBX 내보내기**

Blender에서 `pilot/rabbit_arp.blend` 열고 ARP 아마추어 선택 → ARP → Export FBX → 파일명 `rabbit_animation.fbx` → 저장 경로 `pilot/exports/`.

- [ ] **Step 2: 각 skin variant FBX 내보내기**

mesh만 선택된 상태에서 ARP Export. 총 5개:
- `Rabbit_DutchBrown.fbx`
- `Animal_2002.fbx`
- `Animal_2011.fbx`
- `Animal_3161.fbx`
- `rabbit_CherryBlossom.fbx`

- [ ] **Step 3: Unity sandbox 폴더 생성 및 복사**

Unity 프로젝트에서:
```bash
mkdir -p "C:/Users/manag/GitProject/LittleWitchForestMobile/Assets/_Migration_Sandbox/Rabbit"
cp pilot/exports/*.fbx "C:/Users/manag/GitProject/LittleWitchForestMobile/Assets/_Migration_Sandbox/Rabbit/"
```

- [ ] **Step 4: Unity Editor 포커스 → 재import 대기**

Console 에러 없는지 확인. 있으면 캡처해서 Task 15 diagnosis에 기록.

- [ ] **Step 5: 각 FBX 인스펙터 확인**

- [ ] Avatar 생성되었는지 (Rig 탭 > Avatar Definition)
- [ ] Clip 이름/개수가 baseline과 일치
- [ ] Bone hierarchy 전수 복사 → `pilot/rabbit_new_bone_hierarchy.txt` (로컬)

---

### Task 15: Phase 1e — Diagnosis 리포트 작성

**Files:**
- Create: `docs/superpowers/pilot/rabbit_diagnosis.md`

- [ ] **Step 1: diagnosis.md 템플릿 작성**

`docs/superpowers/pilot/rabbit_diagnosis.md`:

```markdown
# Rabbit Diagnosis (Sandbox 단계)

**날짜**: YYYY-MM-DD
**Baseline**: `rabbit_baseline.md`
**Sandbox 경로**: `Assets/_Migration_Sandbox/Rabbit/`

## FBX 내부 구조

| 항목 | old | new | 결과 |
|------|-----|-----|------|
| bone 개수 | NNN | NNN | OK / 차이: ±N |
| bone 이름 | <링크: baseline 목록> | <링크: new 목록> | 매핑표 별첨 |
| AnimationClip 개수 | 26 | NN | OK / 차이 |
| AnimationClip 이름 | <baseline> | <new> | 전수 일치? Y/N |
| shape key (있다면) | N개 | N개 | OK / 손실 |

### Bone 이름 매핑표 (old → new)

| old | new | 상태 |
|-----|-----|------|
| Hips | root.x | unchanged / renamed |
| ... | ... | ... |

## Unity reference 보존

| 항목 | 예상 | 실측 | 결과 |
|------|------|------|------|
| `.meta` swap 시 GUID 유지 | 유지 | <재import 후 guid 재확인> | OK / broken |
| m_Motion 살아남은 비율 | 21/21 | NN/21 | OK / loss N |
| NavMeshAgent override 유지 | 유지 | Y/N | OK |
| BoxCollider override 유지 | 유지 | Y/N | OK |
| MonoBehaviour override 유지 | 유지 | Y/N | OK |
| Animator.Controller override 유지 | 유지 | Y/N | OK |
| Transform(본) override Missing 수 | 미상 | NN개 | 측정값 |

## 시각적 품질 (절대 기준, baseline 영상 없음)

Task 11에서 녹화 생략으로 before/after 비교 불가. 대신 절대 기준으로 판정한다.

| 항목 | 결과 |
|------|------|
| rest pose가 자연스러운가 (뒤틀림/T-pose 없음) | OK / 차이: <설명> |
| idle 재생이 자연스러운가 | OK / <어색한 부분> |
| walk 재생이 자연스러운가 | OK / <> |
| run 재생이 자연스러운가 | OK / <> |
| skin binding (T-pose 안 뜸) | OK / FAIL |

## 자동화 후보 메모 (Phase 2 인풋)

- <수작업으로 고친 항목 + 소요 시간>
- <반복 가능한 패턴>
- <1마리 × 20마리 절감 추정>
```

- [ ] **Step 2: 실제 데이터 채우기**

Task 11(baseline) + Task 12/13/14 결과 + Unity sandbox 인스펙터 확인으로 표 전수 채움.

Transform override Missing 측정 방법: Unity에서 Sandbox FBX를 기존 프리팹에 강제 연결 시도 (별도 테스트 scene 만들어서) — 파기 범위 측정. 이 단계가 Phase 2 도구화 결정의 핵심 인풋.

- [ ] **Step 3: 커밋**

```bash
git add docs/superpowers/pilot/rabbit_diagnosis.md
git commit -m "docs(migration): Phase 1e Rabbit diagnosis 리포트"
```

---

### Task 16: Phase 1f — 실제 교체 (Unity 레포 브랜치)

**Files (Unity 레포):**
- Create: `Assets/_Migration_Backup/Rabbit/` (`.gitignore`)
- Modify: `Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx` (내용만 교체, .meta 유지)
- Modify: `Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx` 등

- [ ] **Step 1: Unity 레포로 이동 + 브랜치 cut**

```bash
cd "C:/Users/manag/GitProject/LittleWitchForestMobile"
git status   # 깨끗한지 확인
git checkout -b migration/pilot-rabbit
```

- [ ] **Step 2: `.gitignore`에 backup 폴더 추가**

Unity 레포 `.gitignore` 끝에:
```
/Assets/_Migration_Backup/
```

- [ ] **Step 3: 기존 FBX 백업**

```bash
mkdir -p Assets/_Migration_Backup/Rabbit
cp "Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx" Assets/_Migration_Backup/Rabbit/
cp "Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx" Assets/_Migration_Backup/Rabbit/
cp "Assets/5_Models/02. Animals/00.Rabbit/Animal_2002.fbx" Assets/_Migration_Backup/Rabbit/
cp "Assets/5_Models/02. Animals/00.Rabbit/Animal_2011.fbx" Assets/_Migration_Backup/Rabbit/
cp "Assets/5_Models/02. Animals/00.Rabbit/Animal_3161.fbx" Assets/_Migration_Backup/Rabbit/
cp "Assets/5_Models/02. Animals/00.Rabbit/rabbit_CherryBlossom.fbx" Assets/_Migration_Backup/Rabbit/
```

- [ ] **Step 4: FBX 본문만 교체 (.meta 유지)**

```bash
PILOT_EXPORTS="C:/Users/manag/Desktop/BlenderRigConvert/pilot/exports"
cp "$PILOT_EXPORTS/rabbit_animation.fbx"       "Assets/5_Models/02. Animals/00.Rabbit/rabbit_animation.fbx"
cp "$PILOT_EXPORTS/Rabbit_DutchBrown.fbx"      "Assets/5_Models/02. Animals/00.Rabbit/Rabbit_DutchBrown.fbx"
cp "$PILOT_EXPORTS/Animal_2002.fbx"            "Assets/5_Models/02. Animals/00.Rabbit/Animal_2002.fbx"
cp "$PILOT_EXPORTS/Animal_2011.fbx"            "Assets/5_Models/02. Animals/00.Rabbit/Animal_2011.fbx"
cp "$PILOT_EXPORTS/Animal_3161.fbx"            "Assets/5_Models/02. Animals/00.Rabbit/Animal_3161.fbx"
cp "$PILOT_EXPORTS/rabbit_CherryBlossom.fbx"   "Assets/5_Models/02. Animals/00.Rabbit/rabbit_CherryBlossom.fbx"
```

`.meta` 파일은 절대 덮어쓰지 않는다. (확인: `git status`에서 `.meta` 파일은 변경 없어야 함)

- [ ] **Step 5: Unity 재import**

Unity Editor 포커스 → `Assets > Reimport All` 또는 에디터 재시작.

- [ ] **Step 6: Sandbox 폴더 정리**

검증 전이라 `Assets/_Migration_Sandbox/Rabbit/`은 Task 17 통과 전까지 남겨둔다. 통과 후 삭제.

- [ ] **Step 7: Unity 레포에 중간 커밋**

```bash
cd "C:/Users/manag/GitProject/LittleWitchForestMobile"
git add -A
git commit -m "migration(pilot): Rabbit FBX swap (meta 유지)"
```

(swap이므로 `.meta` 파일은 diff에 없어야 정상)

---

### Task 17: Phase 1g — Play mode 검증

**Files:**
- (Unity 레포) `Assets/_Migration_Sandbox/Rabbit/` 삭제 (검증 통과 시)

- [ ] **Step 1: Console 초기화 후 Play mode 진입**

Rabbit 대표 프리팹 `Animal_0` 씬에서 Play. 1 cycle 돌린다.

- [ ] **Step 2: idle / walk / run 3 state 육안 확인 (절대 기준)**

baseline 영상이 없으므로 diff가 아닌 절대 기준으로 본다:
- T-pose / A-pose 고정 없음
- 본 뒤틀림/꺾임 없음
- 애니메이션이 자연스럽게 루프

Rabbit이 포유류로서 "정상으로 걷는가/뛰는가" 수준의 판정.

- [ ] **Step 3: Console 경고 전수 기록**

Play mode 1 cycle 중 Console에 찍히는 모든 Missing Transform / Missing Script / Missing Component / 기타 에러/경고를 텍스트로 `rabbit_diagnosis.md`에 복사.

(baseline이 없으므로 "새로 생긴 것만" 거르지 않고 전수 기록. 기존에 있던 경고인지 여부는 Task 18 리포트에서 메모로 구분.)

- [ ] **Step 4: 프리팹 인스펙터 Missing 마크 전수 확인**

Rabbit 계열 프리팹 전부(`Animal_0` ~ `Animal_12` 등)를 열어서 Missing override 개수 기록.

- [ ] **Step 5: 통과 기준 4가지 판정 (baseline 영상 없음 반영)**

- [ ] (1) `Animal_0` Play mode에서 idle/walk/run 3 state 정상 재생 (멈춤/T-pose 없음)
- [ ] (2) 애니메이션 재생이 "사족보행 Rabbit으로서 자연스러운가" 절대 기준 육안 OK (본 뒤틀림/꺾임 없음)
- [ ] (3) Console Missing 경고가 전부 "알려진 기존 경고"로 분류되고, 새로 생긴 추정 경고는 수동 복구 가능 범위 이내 (baseline 없음 → 경험적 분류)
- [ ] (4) 프리팹 variant Missing override 수가 수동 복구 가능 범위 이내

전부 통과면 Task 18로. 하나라도 실패면 Task 15 diagnosis에 실패 항목 상세 기록 → Phase 2 도구화 결정 인풋으로 남기고 Task 18로 (파일럿은 학습 단계라 실패도 유효 결과).

- [ ] **Step 6: 통과 시 Sandbox 폴더 삭제**

```bash
cd "C:/Users/manag/GitProject/LittleWitchForestMobile"
rm -rf Assets/_Migration_Sandbox/Rabbit
# 관련 .meta 함께 삭제됨
git add -A
git commit -m "migration(pilot): sandbox 폴더 정리"
```

---

### Task 18: Phase 1h — 파일럿 리포트 작성

**Files:**
- Create: `docs/superpowers/pilot/rabbit_report.md`

- [ ] **Step 1: 리포트 작성**

`docs/superpowers/pilot/rabbit_report.md`:

```markdown
# Rabbit 파일럿 최종 리포트

**날짜**: YYYY-MM-DD
**브랜치 (Blender 레포)**: `feat/unity-migration-p0-p1`
**브랜치 (Unity 레포)**: `migration/pilot-rabbit`
**결과**: 통과 / 부분통과 / 실패

## 1. 소요 시간 breakdown

| 단계 | 소요 |
|------|------|
| Task 1 스캐폴딩 | NN분 |
| Task 2~7 build_migration_inventory TDD | NN분 |
| Task 8 Phase 0 실행 + 수동 분류 | NN분 |
| Task 9~10 fbx_to_blend TDD + Blender 본문 | NN분 |
| Task 11 구조 baseline (.meta 전사, 녹화 생략) | NN분 |
| Task 12 fbx_to_blend 실행 + 검증 | NN분 |
| Task 13 BlenderRigConvert 5단계 | NN분 |
| Task 14 ARP 익스포트 + sandbox | NN분 |
| Task 15 diagnosis | NN분 |
| Task 16 swap | NN분 |
| Task 17 play mode 검증 | NN분 |
| **총계** | **NN시간** |

## 2. Diagnosis 결과 요약

(Task 15 diagnosis.md에서 핵심 표만 옮김)

| 영역 | 결과 |
|------|------|
| FBX 내부 구조 | OK / 차이 N건 |
| Unity reference 보존 | m_Motion NN/21 유지, Transform override NN개 Missing |
| 시각 품질 (절대 기준, baseline 영상 없음) | OK / 차이 |

**제약**: Task 11에서 녹화를 생략해 before/after 영상 diff가 불가능. 품질 판정은 "절대 기준 육안 OK"로 한정됨.

## 3. 수작업으로 고친 항목 + 타임스탬프

- HH:MM Preview 역할 수정 (eye_l/r → cc_ 재할당) — NN분
- HH:MM prefab override 수동 복구 NN건 — NN분
- ...

## 4. 자동화 후보 리스트 (Phase 2 인풋)

| 후보 | 관찰 | 1마리 절감 | 20마리 절감 |
|------|------|------------|-------------|
| Unity prefab override 자동 재연결 Editor 스크립트 | NN개 Missing 수동 복구 필요 | NN분 | NN시간 |
| Role 자동 재추론 개선 | Preview 신뢰도 NN% — 수정 NN개 | NN분 | NN시간 |
| migrate_batch.py orchestrator | 개별 Task 11~17 오케스트레이션 오버헤드 NN분 | NN분 | NN시간 |

## 5. blend-fallback 필요 여부

- [ ] Unity FBX에서 역할 추론 신뢰도 ≥50%? Y/N
- [ ] Shape key 손실 있음? Y/N
- [ ] round-trip 품질 열화 심각? Y/N

→ 전부 N이면 FBX-first 유지. 하나라도 Y면 blend-fallback 검토.

## 6. 다음 동물(lopear)에 적용 가능한 공통 패턴

- <패턴 1>
- <패턴 2>
- ...

## 7. Phase 2 권고

(a) 파일럿 성공 + 도구화 추가 불필요 → Phase 3 즉시
(b) 파일럿 성공 + N개 도구 개발 → 각각 Tier 3 spec/plan 분기
(c) 파일럿 실패 → blend-first 재설계

→ **선택: (a/b/c)** + 근거
```

- [ ] **Step 2: 실제 데이터 채우기**

Task 11~17 내내 기록한 메모와 파일들을 참고해 표 전수 채움.

- [ ] **Step 3: 커밋**

```bash
cd C:/Users/manag/Desktop/BlenderRigConvert
git add docs/superpowers/pilot/rabbit_report.md
git commit -m "docs(migration): Phase 1h Rabbit 파일럿 최종 리포트"
```

---

### Task 19: 브랜치 마무리 + ProjectPlan 반영 + 머지

**Files:**
- Modify: `docs/ProjectPlan.md`

- [ ] **Step 1: 전체 테스트 통과 확인**

```bash
pytest tests/ -v
```
Expected: 전체 PASS. 실패 시 원인 조사 후 수정 후 재실행.

- [ ] **Step 2: ruff 통과 확인**

```bash
ruff check scripts/ tests/ tools/
```
Expected: no errors.

- [ ] **Step 3: `docs/ProjectPlan.md` Unity 이주 상태 업데이트**

Unity 이주 섹션 찾아서 (또는 없으면 추가):

```markdown
## Unity 프로젝트 이주

- [x] 설계 (2026-04-16 `docs/superpowers/specs/2026-04-16-unity-migration-design.md`)
- [x] Phase 0 인벤토리 — `docs/MigrationInventory.csv`, in_scope NN
- [x] pre-pilot 도구 — `tools/build_migration_inventory.py`, `tools/fbx_to_blend.py`
- [x] Phase 1 Rabbit 파일럿 — 리포트 `docs/superpowers/pilot/rabbit_report.md` (결과: 통과/부분/실패)
- [ ] Phase 2 도구화 결정 게이트 — Task 18 리포트 기준 별도 계획 분기
- [ ] Phase 3 배치 20마리
- [ ] Phase 4 마무리
```

- [ ] **Step 4: ProjectPlan 커밋**

```bash
git add docs/ProjectPlan.md
git commit -m "docs(projectplan): Unity 이주 Phase 0-1 완료 상태 반영"
```

- [ ] **Step 5: master로 fast-forward 머지 (CLAUDE.md ff-only 규칙)**

```bash
git checkout master
git merge --ff-only feat/unity-migration-p0-p1
```

실패 시(not fast-forward) → master에 먼저 들어온 변경을 rebase하거나 사유 파악 후 조치.

- [ ] **Step 6: 브랜치 정리**

```bash
git branch -d feat/unity-migration-p0-p1
```

---

## 자가 점검

### 스펙 커버리지 매핑

| 스펙 섹션 | 대응 Task |
|-----------|-----------|
| Phase 0 `build_migration_inventory.py` (13 컬럼) | Task 2~7 |
| Phase 0 CSV 42 rows | Task 8 |
| Phase 0 locomotion 수동 확정 (in_scope 21) | Task 8 |
| Pre-pilot `tools/fbx_to_blend.py` (60~80줄) | Task 9~10 |
| Phase 1a Pre-change 스냅샷 (**녹화 생략** — 구조 baseline만) | Task 11 |
| Phase 1b FBX → Blender 재구성 | Task 12 |
| Phase 1c BlenderRigConvert 5단계 | Task 13 |
| Phase 1d ARP 익스포트 → Unity sandbox | Task 14 |
| Phase 1e Diagnosis | Task 15 |
| Phase 1f 실제 교체 (.meta 유지) | Task 16 |
| Phase 1g Play mode 4가지 통과 기준 | Task 17 |
| Phase 1h 파일럿 리포트 (자동화 후보 리스트 포함) | Task 18 |
| 완료 기준 (pytest + ruff + ProjectPlan) | Task 19 |

### 주요 산출물 정합성

- `tools/build_migration_inventory.py` → CSV에 정확히 13 컬럼 (CSV_COLUMNS 상수)
- `tools/fbx_to_blend.py` → `lookup_row` 반환 dict의 `model_fbx_paths`/`clip_names`가 리스트로 디코딩됨 (Task 9 `test_lookup_row_by_id_finds_rabbit`에서 검증)
- Phase 1 수작업 산출물 3종: `rabbit_baseline.md`, `rabbit_diagnosis.md`, `rabbit_report.md` — 각자 Task 11/15/18에서 전수 템플릿 + 채움 지시

### 브랜치 구분

- BlenderRigConvert 레포 (`feat/unity-migration-p0-p1`): Task 1~15, 18, 19 (코드 + 문서)
- Unity 레포 (`migration/pilot-rabbit`): Task 16, 17 (FBX swap, `.meta` 유지, sandbox 정리)

# Blend Inventory Match Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unity `docs/MigrationInventory.csv` 의 `in_scope=22` 엔트리에 대해 `source_blend_hint` 컬럼을 `Asset/Blender/animal_blend_inventory.csv` 와의 매칭 결과로 채운다.

**Architecture:** 단일 one-off 스크립트 `scripts/_oneoff_match_blend_inventory.py`. 3단계 fallback(정규화 이름 / 경로 substring / 수동 alias) 후 파일 존재 검증. 결과는 in-place CSV 업데이트 + stdout 감사 리포트.

**Tech Stack:** Python 3.11 표준 라이브러리만 (`csv`, `re`, `pathlib`). 테스트 없음 (Tier 2, 22회 육안 확인이 검증).

**Spec:** `docs/superpowers/specs/2026-04-17-blend-inventory-match-design.md`

---

## File Structure

```
scripts/
  _oneoff_match_blend_inventory.py   <- NEW (삭제 후보)
docs/
  MigrationInventory.csv              <- MODIFY (source_blend_hint 컬럼만)
```

---

## Task 1: 스크립트 작성 (전체 구현)

스크립트 크기가 작아 단일 작업으로 처리한다. 이후 실행/반복은 Task 2 이후.

**Files:**
- Create: `scripts/_oneoff_match_blend_inventory.py`

- [ ] **Step 1: 스크립트 파일 전체 작성**

작성할 내용 (그대로 복사):

```python
"""One-off: match Unity in_scope rows to Blender inventory rows.

Fills docs/MigrationInventory.csv `source_blend_hint` column with the
matching `Relative_Path` from Asset/Blender/animal_blend_inventory.csv.

Delete this script after use. Re-running is idempotent.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ASSET_ROOT = Path(r"C:\Users\manag\Desktop\BlenderRigConvert\Asset\Blender")
MIGRATION_CSV = Path(r"C:\Users\manag\Desktop\BlenderRigConvert\docs\MigrationInventory.csv")
BLEND_CSV = ASSET_ROOT / "animal_blend_inventory.csv"

# Fill after 1st run as needed. Key = normalized Unity id, value = normalized Animal_EN.
ALIAS_TABLE: dict[str, str] = {}


def normalize(name: str) -> str:
    """Lowercase, drop whitespace, drop parens content, drop slash-tail, keep alnum only."""
    s = re.sub(r"\([^)]*\)", "", name)
    s = s.split("/")[0]
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def match_by_normalized(unity_id: str, blend_rows: list[dict]) -> dict | None:
    target = normalize(unity_id)
    for row in blend_rows:
        if normalize(row["Animal_EN"]) == target:
            return row
    return None


def match_by_path(unity_id: str, blend_rows: list[dict]) -> dict | None:
    needle = unity_id.lower()
    for row in blend_rows:
        if needle in row["Relative_Path"].lower():
            return row
    return None


def match_by_alias(unity_id: str, blend_rows: list[dict]) -> dict | None:
    alias = ALIAS_TABLE.get(normalize(unity_id))
    if not alias:
        return None
    for row in blend_rows:
        if normalize(row["Animal_EN"]) == alias:
            return row
    return None


def verify_file_exists(relative_path: str) -> bool:
    return (ASSET_ROOT / relative_path).is_file()


def forward_slash(path: str) -> str:
    return path.replace("\\", "/")


def main() -> None:
    with BLEND_CSV.open(encoding="utf-8") as f:
        blend_rows = list(csv.DictReader(f))

    with MIGRATION_CSV.open(encoding="utf-8") as f:
        unity_rows = list(csv.DictReader(f))
        unity_fieldnames = list(unity_rows[0].keys()) if unity_rows else []

    counters = {"normalized": 0, "path": 0, "alias": 0, "unresolved": 0}
    details: list[tuple[str, str, str]] = []  # (id, tag, path-or-message)

    for row in unity_rows:
        if row.get("scope") != "in_scope":
            continue
        uid = row["id"]

        hit = match_by_normalized(uid, blend_rows)
        tag = "normalized"
        if not hit:
            hit = match_by_path(uid, blend_rows)
            tag = "path"
        if not hit:
            hit = match_by_alias(uid, blend_rows)
            tag = "alias"

        if hit and verify_file_exists(hit["Relative_Path"]):
            rel = forward_slash(hit["Relative_Path"])
            row["source_blend_hint"] = rel
            counters[tag] += 1
            details.append((uid, tag, rel))
        else:
            row["source_blend_hint"] = "???"
            counters["unresolved"] += 1
            reason = "file missing" if hit else "no match"
            details.append((uid, "???", reason))

    with MIGRATION_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=unity_fieldnames)
        writer.writeheader()
        writer.writerows(unity_rows)

    print(f"Matched (normalized): {counters['normalized']}")
    print(f"Matched (path fallback): {counters['path']}")
    print(f"Matched (alias): {counters['alias']}")
    print(f"Unresolved: {counters['unresolved']}")
    print()
    print("=== Per-entry detail ===")
    for uid, tag, info in details:
        print(f"{uid:16} [{tag:10}] {info}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 기본 syntax 확인**

Run: `python -c "import ast; ast.parse(open('scripts/_oneoff_match_blend_inventory.py', encoding='utf-8').read())"`
Expected: 아무 출력 없음 (syntax OK)

- [ ] **Step 3: 커밋 (실행 전 상태)**

```bash
git add scripts/_oneoff_match_blend_inventory.py
git commit -m "feat(migration): blend inventory 매칭 one-off 스크립트 추가"
```

---

## Task 2: 1차 실행 및 리포트 확인

**Files:**
- Read-only: stdout 리포트
- Side-effect: `docs/MigrationInventory.csv` 업데이트됨

- [ ] **Step 1: 스크립트 실행**

Run: `python scripts/_oneoff_match_blend_inventory.py`
Expected: 4개 카운터 + 22개 엔트리 per-entry detail. (Unresolved 개수는 사전 예측 불가)

- [ ] **Step 2: diff 확인**

Run: `git diff docs/MigrationInventory.csv`
Expected: `source_blend_hint` 컬럼에만 변경. 각 in_scope 행마다 경로 또는 `???` 기록됨. out_of_scope 행은 변경 없음.

- [ ] **Step 3: 성공 비율 확인**

`unresolved` 가 3개 이하면 Task 3(alias iteration)는 사용자 판단. 전부 매칭됐거나 `???`가 의도된 누락이면 Task 4로 바로 진행.

---

## Task 3: Unresolved 항목 해결 (조건부)

Task 2 결과 `???` 가 있고 그 원인이 alias 부재면 수행. 아니면 스킵.

**Files:**
- Modify: `scripts/_oneoff_match_blend_inventory.py:19` (`ALIAS_TABLE` 딕셔너리)
- Side-effect: `docs/MigrationInventory.csv` 재업데이트

- [ ] **Step 1: 각 unresolved 항목별 원인 파악**

Task 2 리포트에서 `???` 가 나온 Unity id 확인. 각각에 대해:
- `animal_blend_inventory.csv`를 열어 의미적으로 대응할 것 같은 `Animal_EN` 찾기
- 예: Unity `Lopear` 가 `???` 로 나왔다면 inventory의 `Holland Lop` (Relative_Path에 `lopear` 포함)가 대응

경로 substring 매칭은 이미 fallback 2단계에서 시도했으므로, 이 단계까지 `???` 로 남았다는 건:
(a) 이름도 경로도 안 맞음 → alias 필요 OR
(b) inventory에 정말 없음 → 수동 채움 or 공란 유지

- [ ] **Step 2: ALIAS_TABLE 편집**

`scripts/_oneoff_match_blend_inventory.py`의 `ALIAS_TABLE` 항목 추가. 키는 Unity id의 normalize 결과, 값은 Blender Animal_EN의 normalize 결과.

예시:
```python
ALIAS_TABLE: dict[str, str] = {
    "lopear": "hollandlop",
    # ...
}
```

- [ ] **Step 3: 재실행**

Run: `python scripts/_oneoff_match_blend_inventory.py`
Expected: alias 카운터가 증가, unresolved 감소.

- [ ] **Step 4: unresolved가 여전히 있다면 수동 채움 판단**

남은 `???` 가 진짜 inventory에 없는 동물이면:
- 사용자가 `docs/MigrationInventory.csv` 를 직접 열어 `source_blend_hint` 에 경로 수동 입력 (또는 공란 유지)
- 또는 해당 동물을 `out_of_scope` 로 재분류 (이건 별도 판단 후 CSV 수정)

- [ ] **Step 5: 중간 커밋 (script iteration)**

alias 추가가 있었다면:
```bash
git add scripts/_oneoff_match_blend_inventory.py
git commit -m "chore(migration): ALIAS_TABLE 에 <id> 추가"
```

---

## Task 4: 최종 결과 커밋

**Files:**
- Modify: `docs/MigrationInventory.csv`

- [ ] **Step 1: 최종 diff 재확인**

Run: `git diff docs/MigrationInventory.csv`
Expected: `source_blend_hint` 컬럼이 `in_scope` 행 22개에 대해 채워짐. out_of_scope 행은 변경 없음. 헤더 순서 보존.

- [ ] **Step 2: 커밋**

```bash
git add docs/MigrationInventory.csv
git commit -m "docs(migration): source_blend_hint 매칭 결과 반영"
```

- [ ] **Step 3: ProjectPlan.md 업데이트**

`docs/ProjectPlan.md` 의 "Unity 프로젝트 이주 > 다음 트랙: blend-first" 섹션 갱신:
- "아트 팀에 21마리 원본 `.blend` 확보 가능 여부 확인" 체크박스에 진행 메모 추가
- `source_blend_hint` 기반으로 1차 매핑 확정됨을 명시

Run: `git add docs/ProjectPlan.md && git commit -m "docs(migration): ProjectPlan 에 blend 매핑 확정 반영"`

---

## Task 5: (선택) 스크립트 정리

blend-first 파이프라인이 자리잡히고 이 스크립트가 더 이상 필요 없으면 삭제.

**Files:**
- Delete: `scripts/_oneoff_match_blend_inventory.py`

- [ ] **Step 1: 삭제 결정**

다음 세션(blend-first 파이프라인 설계)에서 "이 매핑 스크립트를 재실행할 일이 있는가?" 판단. 없으면 삭제, 있으면 보존.

- [ ] **Step 2: 삭제 커밋 (결정 시)**

```bash
git rm scripts/_oneoff_match_blend_inventory.py
git commit -m "chore(migration): 일회성 blend 매칭 스크립트 제거"
```

**이 태스크는 지금 실행하지 않는다. 다음 세션에서 판단.**

---

## Self-Review Notes

- 스펙의 3단계 fallback / 파일 존재 검증 / in-place CSV 업데이트 / stdout 리포트 전부 Task 1에 포함됨
- 스펙의 `ALIAS_TABLE` 1차 실행 후 iterate 패턴은 Task 3로 분리됨
- 스펙이 pytest 없음으로 명시했으므로 TDD 스텝 제외
- `.blend` 경로 forward slash 정규화(스펙 "값") 구현됨 (`forward_slash` 함수)
- CSV 헤더 순서 보존은 `DictWriter(fieldnames=unity_fieldnames)`로 보장
- Out-of-scope 행 미변경은 `scope != "in_scope"` 가드로 보장

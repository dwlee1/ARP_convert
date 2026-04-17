"""Unity FBX → blend 재구성 단계의 pre-processing 순수 헬퍼.

Phase 2 후보 A 구현. Blender 의존성 없이 단위 테스트 가능.

A-1: 컨트롤러 본 식별 (suffix 기반) + 제거 계획 (자식 reparent)
A-2: 보조 root 본 식별 (primary root 외 parent=None 본). **자동 삭제 금지** —
     Food처럼 의도된 어태치먼트 본일 수 있어 호출자가 보고만 받는다.
A-3: leaf 본 tail 길이 정규화 (Blender FBX importer leaf bone tail 손실 보정)

Blender 통합부는 `fbx_to_blend.py`의 `_reconstruct_in_blender`에서 호출.
"""

from __future__ import annotations

import re

CONTROLLER_SUFFIXES = ("_FK", "_IK", "_nomove", "_ctrl", "_pole")
_SIDE_SUFFIX_RE = re.compile(r"[._][LRlr]$")


def _strip_side_suffix(name: str) -> str:
    return _SIDE_SUFFIX_RE.sub("", name)


# ──────────────────────────────────────────────────────────────────────
# A-1
# ──────────────────────────────────────────────────────────────────────


def is_controller_bone(name: str) -> bool:
    """이름이 컨트롤러 패턴(`*_FK`, `*_IK`, `*_nomove`, `*_ctrl`, `*_pole`)인가.

    side suffix(`.l/.r/_L/_R`)는 비교 전 제거한다.
    """
    base = _strip_side_suffix(name)
    return base.endswith(CONTROLLER_SUFFIXES)


def _mirror_deform_name(controller_name: str, deform_names: set[str]) -> str | None:
    """컨트롤러 이름의 suffix를 벗긴 이름이 deform 본으로 존재하면 그 이름 반환.

    side suffix(`.l/.r/_L/_R`)는 보존한다.
    예: `chest_nomove` → `chest`, `leg_pole.l` → `leg.l`, `hand_IK_L` → `hand_L`.
    """
    side_match = _SIDE_SUFFIX_RE.search(controller_name)
    side = side_match.group(0) if side_match else ""
    base = controller_name[: -len(side)] if side else controller_name
    for suffix in CONTROLLER_SUFFIXES:
        if base.endswith(suffix):
            candidate = base[: -len(suffix)] + side
            if candidate in deform_names:
                return candidate
    return None


def plan_controller_removal(bones: dict[str, dict]) -> dict:
    """컨트롤러 본 제거 + 자식 reparent 계획을 반환.

    Args:
        bones: `{name: {"parent": parent_name | None, ...}}` 형태.

    Returns:
        `{"remove": [name, ...], "reparent": {child_name: new_parent | None}}`.

        `new_parent` 결정 우선순위:
        1. 부모 컨트롤러의 mirror deform 본 (예: `chest_nomove` → `chest`)
        2. 가장 가까운 비-컨트롤러 조상
        3. 위 둘 다 없으면 None (top-level)
    """
    controllers = {n for n in bones if is_controller_bone(n)}
    deform_names = set(bones) - controllers
    reparent: dict[str, str | None] = {}

    for name, info in bones.items():
        if name in controllers:
            continue
        parent = info.get("parent")
        if parent is None or parent not in controllers:
            continue
        mirror = _mirror_deform_name(parent, deform_names)
        if mirror is not None:
            reparent[name] = mirror
            continue
        cur: str | None = parent
        while cur is not None and cur in controllers:
            cur = bones[cur].get("parent")
        reparent[name] = cur

    return {"remove": sorted(controllers), "reparent": reparent}


# ──────────────────────────────────────────────────────────────────────
# A-2
# ──────────────────────────────────────────────────────────────────────


def find_orphan_bones(bones: dict[str, dict]) -> list[str]:
    """parent=None인 본이 2개 이상이면 primary root를 제외한 나머지를 orphan으로 반환.

    Primary root 결정 우선순위:
    1. 이름이 정확히 `root` 또는 `Root`인 본
    2. 자손 수가 가장 많은 본 (동률은 이름순)
    """
    top_level = [n for n, info in bones.items() if info.get("parent") is None]
    if len(top_level) <= 1:
        return []

    named_root = next((n for n in top_level if n in ("root", "Root")), None)
    if named_root:
        primary = named_root
    else:
        descendant_counts = {n: _count_descendants(bones, n) for n in top_level}
        primary = max(top_level, key=lambda n: (descendant_counts[n], -ord(n[0]) if n else 0))

    return sorted(n for n in top_level if n != primary)


def _count_descendants(bones: dict[str, dict], root: str) -> int:
    children_map: dict[str, list[str]] = {}
    for name, info in bones.items():
        parent = info.get("parent")
        if parent is not None:
            children_map.setdefault(parent, []).append(name)

    count = 0
    stack = [root]
    while stack:
        node = stack.pop()
        for child in children_map.get(node, []):
            count += 1
            stack.append(child)
    return count


# ──────────────────────────────────────────────────────────────────────
# A-3
# ──────────────────────────────────────────────────────────────────────


def compute_leaf_tail_shrink(
    bones: dict[str, dict], ratio: float = 0.1, tolerance: float = 1e-4
) -> dict[str, float]:
    """leaf 본 중 parent와 length가 거의 같은 본을 `parent.length * ratio`로 축소 권고.

    Blender FBX importer가 leaf bone tail을 자식 head 위치로 재계산하지 못해
    parent 본 length를 그대로 승계하는 케이스 보정.

    Args:
        ratio: 새 길이 = parent length * ratio. 기본 0.1.
        tolerance: parent length와 동일한지 판정할 절대 오차.

    Returns:
        `{leaf_name: new_length}` — Blender 적용은 호출자 책임.
    """
    has_child = {n: False for n in bones}
    for info in bones.values():
        parent = info.get("parent")
        if parent in has_child:
            has_child[parent] = True

    result: dict[str, float] = {}
    for name, info in bones.items():
        if has_child[name]:
            continue
        parent = info.get("parent")
        if parent is None or parent not in bones:
            continue
        parent_length = bones[parent].get("length")
        own_length = info.get("length")
        if parent_length is None or own_length is None:
            continue
        if abs(own_length - parent_length) <= tolerance:
            result[name] = parent_length * ratio
    return result

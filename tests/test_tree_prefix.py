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
    # Root children: Spine (not last), Tail (last)
    # Spine children: Neck (only child → last)
    # Neck children: Head (only child → last)
    assert prefixes[1] == "├─ "  # Spine: not last child of Root
    assert prefixes[2] == "│  └─ "  # Neck: last child of Spine; Spine not last → │
    assert prefixes[3] == "│     └─ "  # Head: last child of Neck; Spine not last → │
    assert prefixes[4] == "└─ "  # Tail: last child of Root


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

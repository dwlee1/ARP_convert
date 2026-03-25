import pytest

import weight_transfer_rules as wtr


def _source(name, role, side="L", head=(0.0, 0.0, 0.0), length=1.0):
    return {
        "name": name,
        "role": role,
        "side": side,
        "head": head,
        "tail": (head[0], head[1] + length, head[2]),
        "length": length,
    }


def _arp(
    name,
    owner_ref,
    family_kind="main",
    side="L",
    head=(0.0, 0.0, 0.0),
    length=1.0,
    is_auxiliary=False,
):
    return {
        "name": name,
        "owner_ref": owner_ref,
        "owner_role": "",
        "segment_index": 0,
        "family_kind": family_kind,
        "side": side,
        "head": head,
        "tail": (head[0], head[1] + length, head[2]),
        "length": length,
        "is_auxiliary": is_auxiliary,
    }


def _build(
    source_meta,
    arp_meta,
    roles,
    deform_to_ref=None,
    arp_chains=None,
    cc_bone_map=None,
    logs=None,
):
    return wtr.build_weight_map(
        source_meta=source_meta,
        arp_meta=arp_meta,
        cc_bone_map=cc_bone_map or {},
        roles=roles,
        deform_to_ref=deform_to_ref or {},
        arp_chains=arp_chains or {},
        log=(logs.append if logs is not None else None),
    )


def test_leg_family_splits_by_owned_lengths_only():
    source_meta = {
        "upper_leg.l": _source("upper_leg.l", "back_leg_l"),
    }
    arp_meta = {
        "thigh.l": _arp("thigh.l", "thigh_ref.l", length=2.0),
        "thigh_twist.l": _arp("thigh_twist.l", "thigh_ref.l", family_kind="twist", length=1.0),
        "thigh_stretch.l": _arp(
            "thigh_stretch.l", "thigh_ref.l", family_kind="stretch", length=1.0
        ),
    }

    weight_map = _build(
        source_meta,
        arp_meta,
        roles={"back_leg_l": ["upper_leg.l"]},
        deform_to_ref={"upper_leg.l": "thigh_ref.l"},
    )

    assert weight_map["upper_leg.l"] == [
        ("thigh.l", 0.5),
        ("thigh_twist.l", 0.25),
        ("thigh_stretch.l", 0.25),
    ]


def test_leg_mapping_does_not_leak_to_adjacent_segment_family():
    source_meta = {
        "upper_leg.l": _source("upper_leg.l", "back_leg_l"),
    }
    arp_meta = {
        "thigh.l": _arp("thigh.l", "thigh_ref.l", length=2.0),
        "thigh_twist.l": _arp("thigh_twist.l", "thigh_ref.l", family_kind="twist", length=1.0),
        "leg.l": _arp("leg.l", "leg_ref.l", head=(0.0, 0.2, 0.0), length=4.0),
        "leg_twist.l": _arp(
            "leg_twist.l", "leg_ref.l", family_kind="twist", head=(0.0, 0.2, 0.0), length=1.0
        ),
    }

    weight_map = _build(
        source_meta,
        arp_meta,
        roles={"back_leg_l": ["upper_leg.l"]},
        deform_to_ref={"upper_leg.l": "thigh_ref.l"},
    )

    mapped_targets = {name for name, _ in weight_map["upper_leg.l"]}
    assert mapped_targets == {"thigh.l", "thigh_twist.l"}


def test_two_bone_foot_maps_foot_and_toe_families_separately():
    source_meta = {
        "foot_src.l": _source("foot_src.l", "back_foot_l"),
        "toe_src.l": _source("toe_src.l", "back_foot_l", head=(0.0, 1.0, 0.0)),
    }
    arp_meta = {
        "foot.l": _arp("foot.l", "foot_ref.l", length=2.0),
        "foot_stretch.l": _arp("foot_stretch.l", "foot_ref.l", family_kind="stretch", length=1.0),
        "toes.l": _arp("toes.l", "toes_ref.l", family_kind="toe", head=(0.0, 1.0, 0.0), length=3.0),
    }

    weight_map = _build(
        source_meta,
        arp_meta,
        roles={"back_foot_l": ["foot_src.l", "toe_src.l"]},
        arp_chains={"back_foot_l": ["foot_ref.l", "toes_ref.l"]},
    )

    assert weight_map["foot_src.l"] == [
        ("foot.l", pytest.approx(2.0 / 3.0)),
        ("foot_stretch.l", pytest.approx(1.0 / 3.0)),
    ]
    assert weight_map["toe_src.l"] == [("toes.l", 1.0)]


def test_single_bone_foot_splits_between_foot_and_toe_by_family_length():
    source_meta = {
        "foot_src.l": _source("foot_src.l", "back_foot_l"),
    }
    arp_meta = {
        "foot.l": _arp("foot.l", "foot_ref.l", length=3.0),
        "toes.l": _arp("toes.l", "toes_ref.l", family_kind="toe", head=(0.0, 1.0, 0.0), length=1.0),
    }

    weight_map = _build(
        source_meta,
        arp_meta,
        roles={"back_foot_l": ["foot_src.l"]},
        arp_chains={"back_foot_l": ["foot_ref.l", "toes_ref.l"]},
    )

    assert weight_map["foot_src.l"] == [
        ("foot.l", pytest.approx(0.75)),
        ("toes.l", pytest.approx(0.25)),
    ]


def test_auxiliary_heel_and_bank_bones_are_excluded():
    source_meta = {
        "misc.l": _source("misc.l", "root"),
    }
    arp_meta = {
        "spine.l": _arp("spine.l", "spine_01_ref.l", length=1.0),
        "foot_heel.l": _arp(
            "foot_heel.l", "foot_ref.l", head=(0.0, 0.0, 0.0), length=5.0, is_auxiliary=True
        ),
        "foot_bank_01.l": _arp(
            "foot_bank_01.l", "foot_ref.l", head=(0.0, 0.0, 0.0), length=5.0, is_auxiliary=True
        ),
    }

    weight_map = _build(
        source_meta,
        arp_meta,
        roles={"root": ["misc.l"]},
    )

    assert weight_map["misc.l"] == [("spine.l", 1.0)]


def test_unresolved_family_falls_back_to_generic_mapping_with_reason():
    logs = []
    source_meta = {
        "foot_src.l": _source("foot_src.l", "back_foot_l"),
    }
    arp_meta = {
        "fallback.l": _arp("fallback.l", "spine_01_ref.l", head=(0.0, 0.0, 0.0), length=1.0),
    }

    weight_map = _build(
        source_meta,
        arp_meta,
        roles={"back_foot_l": ["foot_src.l"]},
        arp_chains={"back_foot_l": ["foot_ref.l", "toes_ref.l"]},
        logs=logs,
    )

    assert weight_map["foot_src.l"] == [("fallback.l", 1.0)]
    assert any("role-aware fallback: foot_src.l" in entry for entry in logs)

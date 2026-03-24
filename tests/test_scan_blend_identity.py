import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = PROJECT_ROOT / "tools" / "blend_identity"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import scan_blend_identity as sbi


def test_assign_group_ids_only_marks_duplicates():
    records = [
        {"rig_action_name_signature": "A", "same": ""},
        {"rig_action_name_signature": "A", "same": ""},
        {"rig_action_name_signature": "B", "same": ""},
    ]

    sbi.assign_group_ids(records, lambda rec: rec["rig_action_name_signature"], "same", "GRP")

    assert records[0]["same"] == "GRP_001"
    assert records[1]["same"] == "GRP_001"
    assert records[2]["same"] == ""


def test_enrich_records_marks_diff_mesh_group():
    results = [
        sbi.ScanResult(
            "a.blend",
            True,
            "ok",
            {
                "blend_name": "a.blend",
                "source_armature": {"name": "Arm", "bone_count": 10, "deform_bone_count": 8},
                "actions": [{"name": "Walk"}],
                "bound_meshes": [{"object_name": "MeshA"}],
                "fingerprints": {
                    "source_bone_signature": "bone",
                    "action_name_signature": "actname",
                    "action_detail_signature": "actdetail",
                    "mesh_name_signature": "mesh1",
                    "mesh_detail_signature": "mesh1d",
                    "rig_action_name_signature": "ran",
                    "rig_action_detail_signature": "rad",
                },
            },
        ),
        sbi.ScanResult(
            "b.blend",
            True,
            "ok",
            {
                "blend_name": "b.blend",
                "source_armature": {"name": "Arm", "bone_count": 10, "deform_bone_count": 8},
                "actions": [{"name": "Walk"}],
                "bound_meshes": [{"object_name": "MeshB"}],
                "fingerprints": {
                    "source_bone_signature": "bone",
                    "action_name_signature": "actname",
                    "action_detail_signature": "actdetail",
                    "mesh_name_signature": "mesh2",
                    "mesh_detail_signature": "mesh2d",
                    "rig_action_name_signature": "ran",
                    "rig_action_detail_signature": "rad",
                },
            },
        ),
    ]

    records = sbi.enrich_records(results)

    assert records[0]["same_rig_action_name_group"] == "RAN_001"
    assert records[1]["same_rig_action_name_group"] == "RAN_001"
    assert records[0]["same_rig_action_name_diff_mesh_group"] == "RAM_001"
    assert records[1]["same_rig_action_name_diff_mesh_group"] == "RAM_001"

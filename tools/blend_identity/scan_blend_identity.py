"""
scan_blend_identity.py
======================
Asset/BlenderFile 하위 .blend 파일을 Blender로 열어 내부 메타데이터를 추출하고,
같은 리그/애니메이션을 공유하는 후보를 CSV/JSON으로 저장한다.

사용법:
  python tools/blend_identity/scan_blend_identity.py
  python tools/blend_identity/scan_blend_identity.py --filter normal/fox
  python tools/blend_identity/scan_blend_identity.py --limit 5
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def get_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_bundle_dir() -> Path:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir)
    return Path(__file__).resolve().parent


def find_project_root(start_dir: Path) -> Path:
    current = start_dir.resolve()
    for candidate in (current, *current.parents):
        if (candidate.parent / "Asset" / "BlenderFile").exists():
            return candidate
    return current


RUNTIME_DIR = get_runtime_dir()
BUNDLE_DIR = get_bundle_dir()
PROJECT_ROOT = find_project_root(RUNTIME_DIR)
ASSET_ROOT = str(PROJECT_ROOT.parent / "Asset" / "BlenderFile")
EXTRACT_SCRIPT = str(BUNDLE_DIR / "extract_blend_identity.py")
OUTPUT_DIR = str(RUNTIME_DIR / "output")
DEFAULT_JSON = os.path.join(OUTPUT_DIR, "blend_identity_report.json")
DEFAULT_CSV = os.path.join(OUTPUT_DIR, "blend_identity_report.csv")
DEFAULT_TIMEOUT = 180
DEFAULT_BLENDER_CANDIDATES = [
    "/mnt/c/Program Files/Blender Foundation/Blender 4.5/blender.exe",
    r"C:\Program Files\Blender Foundation\Blender 4.5\blender.exe",
]


@dataclass
class ScanResult:
    rel_path: str
    success: bool
    message: str
    metadata: dict | None = None


def find_blender_exe(override: str | None) -> str:
    if override:
        if os.path.exists(override):
            return override
        if override.lower().endswith(".exe"):
            return override
        if not os.path.exists(override):
            raise FileNotFoundError(f"Blender를 찾을 수 없습니다: {override}")
        return override

    for candidate in DEFAULT_BLENDER_CANDIDATES:
        if os.path.exists(candidate):
            return candidate

    raise FileNotFoundError("Blender 실행 파일을 찾을 수 없습니다. --blender 옵션으로 지정하세요.")


def to_blender_path(path: str, blender_exe: str) -> str:
    if os.name == "nt":
        return path
    if not blender_exe.lower().endswith(".exe"):
        return path

    try:
        proc = subprocess.run(
            ["wslpath", "-w", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()
    except Exception:
        return path


def find_blend_files(filter_path: str | None, limit: int | None) -> list[str]:
    targets: list[str] = []

    for root, _, files in os.walk(ASSET_ROOT):
        rel_root = os.path.relpath(root, ASSET_ROOT).replace("\\", "/")
        if filter_path and not rel_root.startswith(filter_path.replace("\\", "/")):
            continue

        for filename in sorted(files):
            if not filename.endswith(".blend"):
                continue
            full_path = os.path.join(root, filename)
            targets.append(full_path)
            if limit and len(targets) >= limit:
                return targets

    return targets


def run_extract(blender_exe: str, blend_path: str, timeout: int) -> ScanResult:
    rel_path = os.path.relpath(blend_path, ASSET_ROOT).replace("\\", "/")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".json", dir=PROJECT_ROOT) as temp_handle:
        output_json = temp_handle.name

    cmd = [
        blender_exe,
        "--background",
        to_blender_path(blend_path, blender_exe),
        "--python",
        to_blender_path(EXTRACT_SCRIPT, blender_exe),
        "--",
        "--output",
        to_blender_path(output_json, blender_exe),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=PROJECT_ROOT,
        )
        if proc.returncode != 0:
            return ScanResult(
                rel_path,
                False,
                proc.stderr[-500:] if proc.stderr else f"returncode={proc.returncode}",
            )

        with open(output_json, encoding="utf-8") as handle:
            metadata = json.load(handle)
        return ScanResult(rel_path, True, "ok", metadata)
    except subprocess.TimeoutExpired:
        return ScanResult(rel_path, False, f"timeout ({timeout}s)")
    except Exception as exc:
        return ScanResult(rel_path, False, str(exc))
    finally:
        if os.path.exists(output_json):
            os.remove(output_json)


def normalize_list(values: Iterable[str]) -> str:
    return "; ".join(values)


def assign_group_ids(records: list[dict], key_fn, field_name: str, prefix: str) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        key = key_fn(record)
        if key:
            groups[key].append(record)

    group_index = 1
    for _, items in sorted(groups.items(), key=lambda pair: pair[0]):
        if len(items) < 2:
            continue
        group_id = f"{prefix}_{group_index:03d}"
        for record in items:
            record[field_name] = group_id
        group_index += 1


def enrich_records(results: list[ScanResult]) -> list[dict]:
    records: list[dict] = []
    for result in results:
        if not result.success or not result.metadata:
            continue

        metadata = result.metadata
        source_armature = metadata.get("source_armature") or {}
        fingerprints = metadata.get("fingerprints") or {}
        actions = metadata.get("actions") or []
        meshes = metadata.get("bound_meshes") or []

        record = {
            "rel_path": result.rel_path,
            "blend_name": metadata.get("blend_name", ""),
            "source_armature": source_armature.get("name", ""),
            "bone_count": source_armature.get("bone_count", 0),
            "deform_bone_count": source_armature.get("deform_bone_count", 0),
            "action_names": [item.get("name", "") for item in actions],
            "mesh_names": [item.get("object_name", "") for item in meshes],
            "source_bone_signature": fingerprints.get("source_bone_signature", ""),
            "action_name_signature": fingerprints.get("action_name_signature", ""),
            "action_detail_signature": fingerprints.get("action_detail_signature", ""),
            "mesh_name_signature": fingerprints.get("mesh_name_signature", ""),
            "mesh_detail_signature": fingerprints.get("mesh_detail_signature", ""),
            "rig_action_name_signature": fingerprints.get("rig_action_name_signature", ""),
            "rig_action_detail_signature": fingerprints.get("rig_action_detail_signature", ""),
            "same_rig_action_name_group": "",
            "same_rig_action_detail_group": "",
            "same_rig_action_name_diff_mesh_group": "",
        }
        records.append(record)

    assign_group_ids(
        records, lambda rec: rec["rig_action_name_signature"], "same_rig_action_name_group", "RAN"
    )
    assign_group_ids(
        records,
        lambda rec: rec["rig_action_detail_signature"],
        "same_rig_action_detail_group",
        "RAD",
    )

    grouped_by_name_sig: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record["same_rig_action_name_group"]:
            grouped_by_name_sig[record["rig_action_name_signature"]].append(record)

    diff_mesh_index = 1
    for _key, items in sorted(grouped_by_name_sig.items(), key=lambda pair: pair[0]):
        mesh_signatures = {item["mesh_detail_signature"] for item in items}
        if len(items) < 2 or len(mesh_signatures) < 2:
            continue
        group_id = f"RAM_{diff_mesh_index:03d}"
        for record in items:
            record["same_rig_action_name_diff_mesh_group"] = group_id
        diff_mesh_index += 1

    return records


def write_csv(records: list[dict], output_csv: str) -> None:
    fieldnames = [
        "rel_path",
        "blend_name",
        "source_armature",
        "bone_count",
        "deform_bone_count",
        "same_rig_action_name_group",
        "same_rig_action_detail_group",
        "same_rig_action_name_diff_mesh_group",
        "action_names",
        "mesh_names",
        "source_bone_signature",
        "action_name_signature",
        "action_detail_signature",
        "mesh_name_signature",
        "mesh_detail_signature",
    ]

    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = dict(record)
            row["action_names"] = normalize_list(row["action_names"])
            row["mesh_names"] = normalize_list(row["mesh_names"])
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_json(results: list[ScanResult], records: list[dict], output_json: str) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(),
        "total_files": len(results),
        "success_count": sum(1 for item in results if item.success),
        "fail_count": sum(1 for item in results if not item.success),
        "records": records,
        "failures": [
            {"rel_path": item.rel_path, "message": item.message}
            for item in results
            if not item.success
        ],
    }

    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def print_summary(
    records: list[dict], results: list[ScanResult], output_csv: str, output_json: str
) -> None:
    same_name_groups = sorted(
        {
            item["same_rig_action_name_group"]
            for item in records
            if item["same_rig_action_name_group"]
        }
    )
    same_detail_groups = sorted(
        {
            item["same_rig_action_detail_group"]
            for item in records
            if item["same_rig_action_detail_group"]
        }
    )
    diff_mesh_groups = sorted(
        {
            item["same_rig_action_name_diff_mesh_group"]
            for item in records
            if item["same_rig_action_name_diff_mesh_group"]
        }
    )

    print("=" * 60)
    print("blend identity scan 완료")
    print(f"  대상 파일: {len(results)}개")
    print(f"  성공: {sum(1 for item in results if item.success)}개")
    print(f"  실패: {sum(1 for item in results if not item.success)}개")
    print(f"  같은 rig+action 이름 그룹: {len(same_name_groups)}개")
    print(f"  같은 rig+action 상세 그룹: {len(same_detail_groups)}개")
    print(f"  같은 rig+action 이름 + 다른 mesh 그룹: {len(diff_mesh_groups)}개")
    print(f"  CSV: {output_csv}")
    print(f"  JSON: {output_json}")
    print("=" * 60)


def main() -> int:
    parser = argparse.ArgumentParser(description="blend 내부 메타데이터 기반 동일 자산 후보 스캔")
    parser.add_argument("--blender", type=str, default=None, help="Blender 실행 파일 경로")
    parser.add_argument("--filter", type=str, default=None, help="특정 하위 경로만 스캔")
    parser.add_argument("--limit", type=int, default=None, help="최대 파일 수 제한")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="파일당 타임아웃(초)")
    parser.add_argument("--json", type=str, default=DEFAULT_JSON, help="JSON 결과 경로")
    parser.add_argument("--csv", type=str, default=DEFAULT_CSV, help="CSV 결과 경로")
    args = parser.parse_args()

    blender_exe = find_blender_exe(args.blender)
    targets = find_blend_files(args.filter, args.limit)

    print("=" * 60)
    print("blend identity scan 시작")
    print(f"  Blender: {blender_exe}")
    print(f"  대상 파일: {len(targets)}개")
    print(f"  필터: {args.filter or '없음'}")
    print(f"  제한: {args.limit or '없음'}")
    print("=" * 60)

    results: list[ScanResult] = []
    for index, path in enumerate(targets, start=1):
        rel_path = os.path.relpath(path, ASSET_ROOT).replace("\\", "/")
        print(f"[{index}/{len(targets)}] {rel_path}")
        result = run_extract(blender_exe, path, args.timeout)
        results.append(result)
        status = "OK" if result.success else "FAIL"
        print(f"  {status} {result.message}")

    records = enrich_records(results)
    write_csv(records, args.csv)
    write_json(results, records, args.json)
    print_summary(records, results, args.csv, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

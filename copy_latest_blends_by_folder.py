"""
copy_latest_blends_by_folder.py — 최신 .blend 파일만 기준에 맞게 별도 폴더로 복사

기본 모드:
- `Asset/BlenderFile`를 재귀 탐색
- `.blend` 파일이 직접 들어있는 각 디렉터리마다 최신 `.blend` 1개만 선택
- `Asset/latest_blends_by_folder`에 원본 상대 경로를 유지해 복사

animal 모드:
- 특정 보조 폴더(`포트레이트`, `UI`, `BackUp`, `Backup`, `참고`, `원화`)를 제외
- 파일명에서 동물명을 추정해 같은 동물끼리 그룹핑
- 동물별 최신 `.blend` 1개만 `Asset/latest_blends_by_animal`에 평탄하게 복사
"""

from __future__ import annotations

import argparse
import re
import shutil
from collections.abc import Iterable, MutableSet, Sequence
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT_DIR / "Asset" / "BlenderFile"
DEFAULT_DEST_BY_GROUP = {
    "folder": ROOT_DIR / "Asset" / "latest_blends_by_folder",
    "animal": ROOT_DIR / "Asset" / "latest_blends_by_animal",
}
DEFAULT_EXCLUDED_DIRS_FOR_ANIMAL = (
    "포트레이트",
    "UI",
    "BackUp",
    "Backup",
    "참고",
    "원화",
)
FILE_PURPOSE_TOKENS = {
    "allani",
    "animation",
    "animtion",
    "aniamtion",
    "ani",
    "rig",
    "rigging",
    "retarget",
    "remap",
    "timeline",
    "modeling",
    "model",
    "statue",
    "final",
    "props",
    "portrait",
    "ui",
    "ex",
    "test",
    "backup",
    "old",
    "new",
    "copy",
    "idle",
    "walk",
    "run",
    "sit",
    "sleep",
    "stand",
    "jump",
    "look",
    "swim",
    "wash",
    "shake",
    "trot",
    "hunt",
    "eat",
    "fly",
    "flight",
    "land",
    "pose",
    "turn",
    "down",
    "up",
    "zero",
    "special",
    "attack",
    "skill",
    "bark",
    "howl",
    "dig",
    "drink",
    "play",
    "stretch",
    "yawn",
    "scratch",
    "death",
    "happy",
    "angry",
    "sad",
    "interact",
    "glide",
    "flap",
    "dive",
    "roll",
    "growl",
    "sniff",
    "wag",
    "peck",
    "hop",
    "crawl",
    "sprint",
    "roar",
}
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
SAMPLE_LIMIT = 10


def is_blend_file(path: Path) -> bool:
    """정식 .blend 파일만 허용하고 Blender 백업 파일은 제외한다."""
    return path.is_file() and path.suffix == ".blend"


def normalize_names(names: Iterable[str]) -> set[str]:
    """비교용 폴더명을 casefold 집합으로 정규화한다."""
    return {name.casefold() for name in names}


def path_contains_excluded_dir(path: Path, excluded_dir_names: set[str]) -> bool:
    """경로 어딘가에 제외 대상 디렉터리명이 포함되는지 확인한다."""
    return any(part.casefold() in excluded_dir_names for part in path.parts)


def iter_blend_files(source_root: Path, excluded_dir_names: Iterable[str] = ()) -> Iterable[Path]:
    """source_root 아래의 모든 .blend 파일을 반환한다."""
    excluded = normalize_names(excluded_dir_names)
    for path in source_root.rglob("*"):
        if not is_blend_file(path):
            continue
        if excluded and path_contains_excluded_dir(path, excluded):
            continue
        yield path


def select_latest_by_parent(files: Iterable[Path]) -> dict[Path, Path]:
    """
    부모 디렉터리별 최신 .blend 파일을 선택한다.

    수정 시간이 같으면 전체 경로 문자열 기준으로 마지막 항목을 선택해 결과를 결정적으로 만든다.
    """
    grouped: dict[Path, list[Path]] = {}

    for file_path in files:
        grouped.setdefault(file_path.parent, []).append(file_path)

    selected: dict[Path, Path] = {}
    for parent_dir, group in grouped.items():
        selected[parent_dir] = max(group, key=lambda path: (path.stat().st_mtime, str(path)))

    return selected


def guess_animal_name(filename: str) -> str:
    """파일명에서 동물명만 남도록 정규화한다."""
    name = Path(filename).stem
    name = re.sub(r"^\d{3,4}_", "", name)
    name = re.sub(r"\(.*?\)", "", name)

    tokens = re.split(r"[_ ]+", name)
    result: list[str] = []
    for token in tokens:
        stripped = token.strip()
        if not stripped:
            continue

        lower = stripped.lower()
        if re.fullmatch(r"\d+", lower):
            break
        if any(lower.startswith(stop) for stop in FILE_PURPOSE_TOKENS):
            break

        result.append(lower)

    if result:
        return "_".join(result).strip("_")
    return Path(filename).stem.lower()


def select_latest_by_animal(files: Iterable[Path]) -> dict[str, Path]:
    """동물명 기준으로 최신 .blend 파일을 선택한다."""
    grouped: dict[str, list[Path]] = {}

    for file_path in files:
        grouped.setdefault(guess_animal_name(file_path.name), []).append(file_path)

    selected: dict[str, Path] = {}
    for animal_name, group in grouped.items():
        selected[animal_name] = max(group, key=lambda path: (path.stat().st_mtime, str(path)))

    return selected


def validate_paths(source_root: Path, dest_root: Path) -> tuple[Path, Path]:
    """입력 경로를 정규화하고 위험한 목적지 경로를 차단한다."""
    source_root = source_root.resolve()
    dest_root = dest_root.resolve()

    if not source_root.exists():
        raise FileNotFoundError(f"source가 존재하지 않습니다: {source_root}")
    if not source_root.is_dir():
        raise NotADirectoryError(f"source가 디렉터리가 아닙니다: {source_root}")
    if source_root == dest_root:
        raise ValueError("dest는 source와 같을 수 없습니다.")
    if source_root in dest_root.parents:
        raise ValueError("dest는 source 내부에 만들 수 없습니다.")
    if dest_root in source_root.parents:
        raise ValueError("dest는 source의 상위 경로로 지정할 수 없습니다.")
    if dest_root.parent == dest_root:
        raise ValueError("dest로 루트 디렉터리를 사용할 수 없습니다.")

    return source_root, dest_root


def _atomic_replace(tmp_dir: Path, dest_root: Path) -> None:
    """임시 디렉터리를 dest_root 위치로 atomic하게 교체한다."""
    if dest_root.exists():
        if not dest_root.is_dir():
            raise NotADirectoryError(f"dest가 디렉터리가 아닙니다: {dest_root}")
        shutil.rmtree(dest_root)
    tmp_dir.rename(dest_root)


def sanitize_filename_part(value: str) -> str:
    """파일명 prefix로 안전하게 쓸 수 있게 정리한다."""
    sanitized = INVALID_FILENAME_CHARS.sub("_", value).strip(" ._")
    return sanitized or "group"


def unique_dest_path(
    dest_root: Path, src_path: Path, group_key: str, used_names: MutableSet[str]
) -> Path:
    """평탄한 출력 폴더에서 파일명 충돌을 피한다."""
    candidate = src_path.name
    if candidate not in used_names:
        used_names.add(candidate)
        return dest_root / candidate

    prefix = sanitize_filename_part(group_key)
    candidate = f"{prefix}__{src_path.name}"
    if candidate not in used_names:
        used_names.add(candidate)
        return dest_root / candidate

    stem = src_path.stem
    suffix = src_path.suffix
    counter = 2
    while True:
        candidate = f"{prefix}__{stem}_{counter}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return dest_root / candidate
        counter += 1


def copy_latest_blends(
    source_root: Path,
    dest_root: Path,
    group_by: str = "folder",
    excluded_dir_names: Iterable[str] = (),
) -> list[tuple[Path, Path]]:
    """기준에 맞는 최신 .blend를 복사하고 원본/대상 경로 목록을 반환한다.

    임시 디렉터리에 먼저 복사한 뒤, 성공하면 dest_root로 교체한다.
    복사 실패 시 기존 dest_root 데이터는 보존된다.
    """
    source_root, dest_root = validate_paths(source_root, dest_root)
    blend_files = list(iter_blend_files(source_root, excluded_dir_names))

    if not blend_files:
        raise FileNotFoundError(f"source에서 .blend 파일을 찾을 수 없습니다: {source_root}")

    tmp_dir = dest_root.parent / f".tmp_{dest_root.name}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    try:
        copied: list[tuple[Path, Path]] = []
        if group_by == "folder":
            selected = select_latest_by_parent(blend_files)
            for parent_dir in sorted(selected):
                src_path = selected[parent_dir]
                relative_parent = parent_dir.relative_to(source_root)
                dst_path = tmp_dir / relative_parent / src_path.name
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dst_path)
                copied.append((src_path, dest_root / relative_parent / src_path.name))

        elif group_by == "animal":
            selected = select_latest_by_animal(blend_files)
            used_names: set[str] = set()
            for animal_name in sorted(selected):
                src_path = selected[animal_name]
                dst_path = unique_dest_path(tmp_dir, src_path, animal_name, used_names)
                shutil.copy2(src_path, dst_path)
                copied.append((src_path, dest_root / dst_path.name))
        else:
            raise ValueError(f"지원하지 않는 group_by 값입니다: {group_by}")

        if not copied:
            raise RuntimeError("선택된 파일이 없어 복사를 중단합니다.")

        _atomic_replace(tmp_dir, dest_root)
        return copied

    except BaseException:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        raise


def format_copy_sample(
    pairs: Sequence[tuple[Path, Path]], source_root: Path, dest_root: Path
) -> list[str]:
    """출력용 샘플 경로 문자열을 생성한다."""
    samples: list[str] = []
    for src_path, dst_path in pairs[:SAMPLE_LIMIT]:
        src_rel = src_path.relative_to(source_root).as_posix()
        dst_rel = dst_path.relative_to(dest_root).as_posix()
        samples.append(f"  {src_rel} -> {dst_rel}")
    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기준에 맞는 최신 .blend 파일만 선택해 별도 폴더로 복사합니다.",
    )
    parser.add_argument(
        "--source",
        default=str(DEFAULT_SOURCE),
        help="원본 .blend 루트 디렉터리",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="복사 결과를 저장할 대상 디렉터리",
    )
    parser.add_argument(
        "--group-by",
        choices=("folder", "animal"),
        default="folder",
        help="최신 파일을 고르는 그룹 기준",
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="이름이 일치하는 디렉터리가 경로에 포함되면 제외",
    )
    return parser.parse_args()


def get_excluded_dir_names(args: argparse.Namespace) -> tuple[str, ...]:
    """CLI 옵션에서 실제 제외 폴더 목록을 계산한다."""
    if args.group_by == "animal":
        return DEFAULT_EXCLUDED_DIRS_FOR_ANIMAL + tuple(args.exclude_dir)
    return tuple(args.exclude_dir)


def main() -> int:
    args = parse_args()
    source_root = Path(args.source)
    dest_root = Path(args.dest) if args.dest else DEFAULT_DEST_BY_GROUP[args.group_by]
    excluded_dir_names = get_excluded_dir_names(args)

    copied = copy_latest_blends(
        source_root,
        dest_root,
        group_by=args.group_by,
        excluded_dir_names=excluded_dir_names,
    )
    source_root = source_root.resolve()
    dest_root = dest_root.resolve()

    print("=" * 60)
    if args.group_by == "animal":
        print("  동물명 기준 최신 .blend 복사 완료")
    else:
        print("  디렉터리별 최신 .blend 복사 완료")
    print("=" * 60)
    print(f"\n  그룹 기준: {args.group_by}")
    print(f"  스캔된 결과 수: {len(copied)}개")
    print(f"  실제 복사된 파일 수: {len(copied)}개")
    print(f"  대상 루트: {dest_root}")
    if excluded_dir_names:
        print(f"  제외 폴더: {', '.join(excluded_dir_names)}")

    if copied:
        print("\n  복사 샘플:")
        for sample in format_copy_sample(copied, source_root, dest_root):
            print(sample)

    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
scan_blend_files.py — 블렌더 파일 현황 CSV 생성 스크립트

전체 폴더를 재귀 탐색하여 모든 .blend 파일의 정보를 CSV로 정리합니다.
- 경로, 파일명, 동물명(추정), 파일명 날짜 접미사, 실제 수정일, 파일 크기
- 동물명별로 그룹핑하여 중복 파일 표시
"""

import os
import re
import csv
import datetime

# ── 설정 ──
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(ROOT_DIR, "blend_files_report.csv")

# 파일명에서 날짜 접미사(YYMMDD)를 추출하는 패턴
# 예: Bear_AllAni_240311.blend → 240311
#     Penguin_Baby_AllAni_241121_ex.blend → 241121
DATE_SUFFIX_PATTERN = re.compile(r'_(\d{6})(?:[_.]|$)')

# 파일명에서 동물명을 추정하기 위한 패턴
# 숫자 접두사(3082_ 등), 날짜 접미사, _AllAni, _animation 등을 제거
ANIMAL_NAME_CLEANUP = [
    (re.compile(r'^\d{3,4}_'), ''),           # 숫자 접두사 제거 (3082_duck → duck)
    (re.compile(r'_?AllAni.*', re.I), ''),     # _AllAni 이후 제거
    (re.compile(r'_?animation.*', re.I), ''),  # _animation 이후 제거
    (re.compile(r'_?Ani_.*', re.I), ''),       # _Ani_ 이후 제거
    (re.compile(r'_?\d{6}.*'), ''),            # 날짜 접미사 이후 제거
    (re.compile(r'_?EX$', re.I), ''),          # EX 접미사 제거
    (re.compile(r'_?\d{2,4}$'), ''),           # 끝 숫자 제거 (cat_black_01 → cat_black)
]


def parse_date_suffix(filename):
    """파일명에서 YYMMDD 날짜 접미사를 추출하여 날짜 문자열로 변환"""
    match = DATE_SUFFIX_PATTERN.search(filename)
    if match:
        raw = match.group(1)
        yy, mm, dd = raw[:2], raw[2:4], raw[4:6]
        year = int(yy)
        year_full = 2000 + year
        try:
            datetime.date(year_full, int(mm), int(dd))
            return f"20{yy}-{mm}-{dd}"
        except ValueError:
            return f"20{yy}-{mm}-{dd}(?)"  # 유효하지 않은 날짜
    return ""


def guess_animal_name(filename):
    """파일명에서 동물명을 추정"""
    name = os.path.splitext(filename)[0]
    for pattern, replacement in ANIMAL_NAME_CLEANUP:
        name = pattern.sub(replacement, name)
    name = name.strip('_').strip()
    return name.lower() if name else filename


def get_top_folder(rel_path):
    """상대 경로에서 최상위 폴더명 추출"""
    parts = rel_path.replace('\\', '/').split('/')
    return parts[0] if len(parts) > 1 else "(root)"


def format_size(size_bytes):
    """파일 크기를 읽기 좋은 형태로 변환"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def scan_blend_files():
    """모든 .blend 파일을 스캔하여 정보 수집"""
    files = []

    for dirpath, dirnames, filenames in os.walk(ROOT_DIR):
        # .git 폴더 등 제외
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

        for filename in filenames:
            # .blend 파일만 (.blend1, .blend2 등 제외)
            if not filename.endswith('.blend'):
                continue
            if re.search(r'\.blend\d+$', filename):
                continue

            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, ROOT_DIR)
            stat = os.stat(filepath)

            mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)
            mod_date_str = mod_time.strftime("%Y-%m-%d %H:%M")

            files.append({
                'filename': filename,
                'rel_path': rel_path.replace('\\', '/'),
                'top_folder': get_top_folder(rel_path.replace('\\', '/')),
                'animal_name': guess_animal_name(filename),
                'filename_date': parse_date_suffix(filename),
                'mod_date': mod_date_str,
                'mod_timestamp': stat.st_mtime,
                'size_bytes': stat.st_size,
                'size_display': format_size(stat.st_size),
            })

    # 동물명 → 수정일 순 정렬
    files.sort(key=lambda f: (f['animal_name'], -f['mod_timestamp']))

    return files


def find_duplicates(files):
    """동물명 기준으로 그룹핑하여 중복 여부 표시"""
    groups = {}
    for f in files:
        key = f['animal_name']
        if key not in groups:
            groups[key] = []
        groups[key].append(f)

    for f in files:
        key = f['animal_name']
        group = groups[key]
        if len(group) > 1:
            # 같은 동물명으로 여러 파일이 있으면 중복 표시
            if f['mod_timestamp'] == max(g['mod_timestamp'] for g in group):
                f['duplicate_status'] = "최신"
            else:
                f['duplicate_status'] = "이전 버전"
        else:
            f['duplicate_status'] = ""


def write_csv(files):
    """CSV 파일 출력"""
    fieldnames = [
        'animal_name',      # 추정 동물명
        'filename',         # 파일명
        'top_folder',       # 최상위 폴더
        'rel_path',         # 상대 경로
        'filename_date',    # 파일명 날짜 접미사
        'mod_date',         # 실제 수정일
        'size_display',     # 파일 크기
        'duplicate_status', # 중복 상태
    ]

    header_display = {
        'animal_name': '동물명(추정)',
        'filename': '파일명',
        'top_folder': '최상위 폴더',
        'rel_path': '상대 경로',
        'filename_date': '파일명 날짜',
        'mod_date': '실제 수정일',
        'size_display': '파일 크기',
        'duplicate_status': '중복 상태',
    }

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([header_display[f] for f in fieldnames])

        for f in files:
            writer.writerow([f[field] for field in fieldnames])

    return OUTPUT_CSV


def print_summary(files):
    """콘솔 요약 출력"""
    total = len(files)
    by_folder = {}
    for f in files:
        folder = f['top_folder']
        by_folder[folder] = by_folder.get(folder, 0) + 1

    duplicates = [f for f in files if f['duplicate_status']]
    animal_groups = {}
    for f in files:
        animal_groups.setdefault(f['animal_name'], []).append(f)
    dup_animals = {k: v for k, v in animal_groups.items() if len(v) > 1}

    print("=" * 60)
    print(f"  블렌더 파일 스캔 결과")
    print("=" * 60)
    print(f"\n  총 .blend 파일 수: {total}개")
    print(f"\n  폴더별 파일 수:")
    for folder, count in sorted(by_folder.items()):
        print(f"    {folder}: {count}개")

    print(f"\n  동물명 기준 중복 그룹: {len(dup_animals)}개")
    if dup_animals:
        print(f"  (같은 동물명으로 추정되는 파일이 2개 이상인 경우)")
        for animal, group in sorted(dup_animals.items()):
            print(f"\n    [{animal}] ({len(group)}개 파일)")
            for g in group:
                status = f" ← {g['duplicate_status']}" if g['duplicate_status'] else ""
                print(f"      {g['mod_date']}  {g['top_folder']}/{g['filename']}{status}")

    print(f"\n  CSV 저장 위치: {OUTPUT_CSV}")
    print("=" * 60)


if __name__ == '__main__':
    print("블렌더 파일 스캔 중...")
    files = scan_blend_files()
    find_duplicates(files)
    output_path = write_csv(files)
    print_summary(files)

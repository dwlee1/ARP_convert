# Plan: blend 파일 메시 스캐너

**날짜**: 2026-04-14
**Tier**: 2 (인라인 계획)
**목적**: 동물 폴더별/전체 기준으로 최신 .blend 파일을 판별하고, 내부 메시 오브젝트명(스킨 변형)을 추출하여 CSV로 정리. ARP 변환 대상 파일 선정을 쉽게 하기 위함.

## 산출물

| 파일 | 역할 |
|------|------|
| `tools/scan_blend_meshes.py` | 메인 스캐너 스크립트 (순수 Python, Blender 불필요) |
| `tools/blend_sdna_parser.py` | .blend SDNA 파서 모듈 (Object 블록에서 메시명 추출) |
| `folder_latest_animals.csv` | 동물 폴더별 최신 파일 + 메시 목록 |
| `global_latest_animals.csv` | 전체 기준 동물별 최신 파일 + 메시 목록 |

## 아키텍처

```
scan_blend_meshes.py
├── blend_sdna_parser.py    ← 신규: SDNA 파서
├── scan_arp_status.py      ← 재활용: read_blend_data(), guess_animal_name()
└── I2Loc CSV               ← 읽기 전용: 동물 영문/한글 이름 사전
```

## Step 1: blend_sdna_parser.py — SDNA 파서 모듈

.blend 파일 포맷 구조:
```
[Header 12B] → pointer_size(4/8), endian(LE/BE), version
[FileBlock]* → code(4B), size(4B), old_ptr, sdna_index, count, data...
[DNA1 block] → SDNA 스키마 (struct 이름, field 이름, field 크기/오프셋)
[ENDB block] → 파일 끝
```

### 구현할 함수

```python
def parse_blend_header(data: bytes) -> dict:
    """
    .blend 헤더 12바이트 파싱.
    Returns: {pointer_size: 4|8, endian: '<'|'>', version: '405'}
    """

def parse_sdna(data: bytes, header: dict) -> dict:
    """
    DNA1 블록을 찾아서 SDNA 스키마 파싱.
    Returns: {
        structs: [{name, fields: [{name, type, size, offset}]}],
        struct_index: {name: index},
    }
    """

def iter_file_blocks(data: bytes, header: dict):
    """
    파일 블록을 순회하는 제너레이터.
    Yields: (code, size, sdna_index, count, block_data)
    """

def extract_mesh_names(data: bytes) -> list[str]:
    """
    최상위 함수. .blend 바이너리 데이터에서 MESH 타입 Object의 이름 리스트 추출.
    1. parse_blend_header()
    2. parse_sdna() → Object struct의 id.name 오프셋, type 오프셋 확인
    3. iter_file_blocks() → 'OB' 코드 블록 순회
    4. 각 Object의 type == OB_MESH(1)이면 id.name[2:] 수집 (앞 2바이트 'OB' 접두사 제거)
    Returns: ['Fox_A', 'Fox_Silver', 'Fox_Corsac', ...]
    """
```

### .blend Object.type 상수
- 0: EMPTY
- 1: MESH ← 이것만 수집
- 2: CURVE
- 5: ARMATURE
- 등등

### 핵심 주의점
- pointer_size가 4(32bit) / 8(64bit)에 따라 블록 헤더 크기가 다름 (20B / 24B)
- endian에 따라 struct.unpack 포맷 다름
- id.name은 `ID` struct의 `name` 필드 — char[66] (Blender 3.0+) 또는 char[24] (구버전)
- Object struct 첫 필드가 `ID id`이므로 name 오프셋은 ID struct 내 name 오프셋과 동일
- 압축 해제는 `scan_arp_status.py`의 `read_blend_data()` 그대로 사용

### 폴백 전략
SDNA 파싱 실패 시 (corrupt 파일 등):
- 바이너리에서 `\x00OB` 패턴 + 인접 문자열 휴리스틱 탐색
- 실패하면 mesh_names = [] 반환, 에러 플래그 세팅

## Step 2: scan_blend_meshes.py — 메인 스캐너

### 2-1. 동물 이름 사전 로드

```python
def load_animal_names(csv_path: str) -> dict:
    """
    I2Loc CSV에서 Name_* 행을 읽어 동물 이름 사전 생성.
    Returns: {
        'rabbit': {'en': 'Rabbit', 'kr': '토끼', 'csv_id': '0_0'},
        'spotted_rabbit': {'en': 'Spotted Rabbit', 'kr': '점박이 토끼', 'csv_id': '0_1'},
        ...
    }
    키는 영문명을 normalize한 값 (소문자, 공백→_, 특수문자 제거)
    """
```

### 2-2. 동물 폴더 탐지

```python
def discover_animal_folders(root: str) -> list[dict]:
    """
    Asset/Blender/ 하위에서 동물 폴더를 탐지.
    동물 폴더 = .blend 파일이 직접 또는 blender/ 서브폴더에 존재하는 리프 폴더.

    폴더 구조 패턴:
    - normal/fox/blender/*.blend    → 동물 폴더 = normal/fox
    - sea/turtle/blender/*.blend    → 동물 폴더 = sea/turtle
    - Sup_01/04_Panda/*.blend       → 동물 폴더 = Sup_01/04_Panda
    - 2026/.../동물/캥거루/*.blend   → 동물 폴더 = 2026/.../캥거루
    - bird/eagle/*.blend            → 동물 폴더 = bird/eagle

    old/, BackUp/, Backup/, 포트레이트/, UI/ 등은 제외.

    Returns: [{
        'folder_path': 'normal/fox',
        'blend_files': [
            {'path': 'normal/fox/blender/fox_AllAni_240311.blend', 'mod_time': 1761545105.7, ...},
            ...
        ],
    }]
    """
```

### 2-3. 메시명 ↔ 동물명 매칭

```python
def match_mesh_to_animals(mesh_names: list[str], animal_dict: dict, folder_name: str) -> list[dict]:
    """
    메시 오브젝트명을 동물 이름 사전과 매칭.

    매칭 전략 (우선순위):
    1. 정확 매칭: mesh명 normalize → 사전 키와 일치
    2. 부분 매칭: mesh명에 사전 키가 포함됨 (예: 'Fox_Silver' contains 'fox')
    3. 폴더명 기반: 폴더명에서 추출한 동물명으로 그룹핑 (기존 guess_animal_name 활용)
    4. 미매칭: csv_id 없이 메시명만 기록

    Returns: [{'mesh_name': 'Fox_A', 'matched_en': 'Fox', 'matched_kr': '여우', 'csv_id': '1_0'}, ...]
    """
```

### 2-4. 폴더별 최신 파일 판별

```python
def find_folder_latest(folders: list[dict]) -> list[dict]:
    """
    각 동물 폴더에서 수정일 기준 최신 .blend 파일 선택.

    선택 기준 (우선순위):
    1. 파일명에 'AllAni' 또는 'animation'이 포함된 파일 중 최신
       (이런 파일이 보통 모든 애니메이션 + 모든 스킨을 포함)
    2. 위 조건 없으면 단순 수정일 최신

    Returns: 폴더별 최신 파일 + 메시 목록 리스트
    """
```

### 2-5. 전체 기준 동물별 최신 판별

```python
def find_global_latest(folder_results: list[dict]) -> list[dict]:
    """
    모든 폴더의 결과를 통합, 같은 동물(CSV 매칭 기준)끼리 그룹핑 후
    가장 최신 파일 선택.

    같은 동물 판별:
    - csv_id가 같은 것 (정확)
    - csv_id가 없으면 guess_animal_name 결과가 같은 것 (휴리스틱)
    - 스킨 변형(이벤트 스킨 등)은 별도 행으로 분리
      (예: 기본 여우 vs 박쥐귀여우 vs 벚꽃여우 — 다른 동물로 취급)

    Returns: 동물별 전체 최신 파일 리스트
    """
```

### 2-6. CSV 출력

**folder_latest_animals.csv 컬럼:**
```
동물폴더, 최신파일명, 수정일, 폴더내_파일수, 메시목록, CSV_ID, 동물명_EN, 동물명_KR
```

**global_latest_animals.csv 컬럼:**
```
동물명_EN, 동물명_KR, CSV_ID, 최신파일명, 파일경로, 수정일, 메시목록(스킨변형), 소속폴더
```

## Step 3: 테스트

- `pytest tests/test_blend_sdna_parser.py` — 파서 단위 테스트
  - 테스트 픽스처: `normal/fox/blender/fox_AllAni_EX240311.blend` 1개를 파싱해서 메시명이 나오는지 확인
  - corrupt 데이터 대응 테스트
- 실행 검증: `python tools/scan_blend_meshes.py` → CSV 2개 생성 확인
- `ruff check tools/` 통과

## Step 4: 문서 갱신

- 이전 `animal_blend_inventory.csv` 삭제 (수동 작성본, 이제 자동 생성으로 대체)
- CLAUDE.md 파일 맵에 새 스크립트 추가

## 구현 순서

1. `tools/blend_sdna_parser.py` 작성 + 단위 테스트
2. `tools/scan_blend_meshes.py` 작성 (Step 2-1 ~ 2-6)
3. 전체 스캔 실행 + 결과 확인
4. 문서 갱신

## 예상 소요

- SDNA 파서: 핵심 구현 ~150줄
- 메인 스캐너: ~200줄
- 테스트: ~50줄
- 전체 스캔 시간: 915개 파일 × ~0.05초 ≈ **1분 이내**

## 리스크

| 리스크 | 대응 |
|--------|------|
| 일부 .blend가 Blender 4.5 zstd 압축 → zstandard 미설치 시 스킵 | `pip install zstandard` 안내 + 스킵 카운트 표시 |
| SDNA 구조가 Blender 버전마다 미세 차이 | ID.name 오프셋은 안정적, Object.type 오프셋만 SDNA로 동적 계산 |
| 메시명 ↔ CSV 동물명 매칭률이 낮을 수 있음 | 폴더명 기반 폴백 + 미매칭 항목 별도 표시 |
| 프랍/UI/석상 등 비동물 파일도 섞임 | 결과 CSV에 포함하되 동물명 매칭 없으면 '기타'로 표시 |

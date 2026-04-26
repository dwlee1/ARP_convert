# Blend Inventory Matching — Unity in_scope → Asset/Blender

**날짜**: 2026-04-17
**상태**: 설계 완료
**Tier**: 2 (인라인 계획 — one-off 스크립트, 테스트 없음)

## 배경

2026-04-17 세션에서 Unity 이주 FBX 경로가 Rabbit GUI 품질 미달로 중단되고
blend-first (후보 C) 경로로 전환됨. 전환의 전제조건은 **Unity 프로젝트의
각 동물에 대응하는 원본 `.blend` 파일 위치 확정**이다.

다행히 `Asset/Blender/animal_blend_inventory.csv` (137행, 수동 큐레이션)가
이미 존재해서 최신 `.blend` → 동물명 매핑이 준비돼 있다. 그러나 Unity
`docs/MigrationInventory.csv`의 `source_blend_hint` 컬럼은 비어있어 두
CSV를 연결해야 한다.

## 목표

`docs/MigrationInventory.csv`의 `scope == in_scope` 22개 엔트리에 대해
`source_blend_hint` 컬럼을 채운다. 값은 `Asset/Blender/` 루트 기준 상대 경로
(예: `normal/rabbit/blender/rabbit_AllAni_EX240311.blend`).

블렌드 파일 존재 여부도 함께 검증한다.

## 비목표

- `out_of_scope` (새, 물고기 등) 엔트리는 건드리지 않음
- 재사용 가능한 정식 도구화 — 한 번 실행 후 버림
- pytest 커버리지 — 22회 육안 확인이 검증
- Unity 애니메이션 클립 ↔ blend 액션 매핑 — 이후 단계

## 입력

### 1. `docs/MigrationInventory.csv` (47행, 현재 상태)
핵심 컬럼:
- `id` — 예: `Lopear`, `Rabbit`, `BabyFox`, `BlackCat`
- `scope` — `in_scope` | `out_of_scope`
- `source_blend_hint` — 비어있음 (이번 작업 타겟)

### 2. `Asset/Blender/animal_blend_inventory.csv` (137행, 수동 큐레이션)
핵심 컬럼:
- `Animal_EN` — 예: `Rabbit`, `Holland Lop`, `Deer (Doe)`, `Llama / Alpaca`
- `Relative_Path` — 예: `normal/rabbit/blender/rabbit_AllAni_EX240311.blend`
- `Latest_Blend_File`, `Modified_Date`, `Variants`

## 매칭 알고리즘

다음 3단계 fallback 순서로 매칭 시도. 가장 앞 단계에서 성공하면 그 결과 사용.

### 단계 1. 정규화 이름 매칭

양측 이름을 다음 규칙으로 정규화 후 동등 비교:
- 소문자화
- 공백 제거
- 괄호 내용 제거: `Deer (Doe)` → `Deer`
- 슬래시 이후 제거: `Llama / Alpaca` → `Llama`
- 알파벳/숫자 외 문자 제거

예시:
- Unity `BlackCat` → `blackcat`, Blender `Black Cat` → `blackcat` ✓
- Unity `Deer` → `deer`, Blender `Deer (Doe)` → `deer` ✓
- Unity `Llama` → `llama`, Blender `Llama / Alpaca` → `llama` ✓
- Unity `BabyRabbit` → `babyrabbit`, Blender `Baby Rabbit` → `babyrabbit` ✓

### 단계 2. 경로 substring 매칭

단계 1 실패 시, Unity `id`를 소문자화한 값이 Blender `Relative_Path`에
substring으로 포함되는지 검사.

예시:
- Unity `Lopear` → `lopear`. Blender 엔트리 `Holland Lop`의 `Relative_Path`
  `normal/lopear/lopear_AllAni_EX240311.blend`에 `lopear` 포함 ✓

### 단계 3. 수동 alias 테이블

단계 1·2 모두 실패 시 하드코딩된 alias dict 참조.

기본값 빈 dict로 시작한다. 1차 실행 결과 unresolved가 나오면 그때
필요한 alias만 추가해 재실행.

## 파일 존재 검증

매칭 성공한 각 엔트리에 대해 `<ASSET_ROOT>/<Relative_Path>` (ASSET_ROOT =
`C:\Users\manag\Desktop\BlenderRigConvert\Asset\Blender`)가 실제
존재하는지 `os.path.isfile()`로 확인. 없으면 매칭 실패 처리 (`???`).

## 출력

### 1. `docs/MigrationInventory.csv` 업데이트 (in-place)

`source_blend_hint` 컬럼에 다음 중 하나 기록:
- 매칭 성공: `Relative_Path` 값 그대로 (forward slash 정규화)
- 매칭 실패: `???`

### 2. stdout 감사 리포트

```
Matched (normalized): 18
Matched (path fallback): 1
Matched (alias): 0
Unresolved: 3

=== Per-entry detail ===
Lopear          [path]       normal/lopear/lopear_AllAni_EX240311.blend
Rabbit          [normalized] normal/rabbit/blender/rabbit_AllAni_EX240311.blend
...
BabyTurtle      [???]        (no match)
```

## 구현

### 파일
`scripts/_oneoff_match_blend_inventory.py`

(언더스코어 접두어 = one-off 표시. 다음 세션 시작 시 필요 없으면 삭제)

### 의존성
표준 라이브러리만: `csv`, `os`, `re`, `pathlib`

### 구조
- `normalize(name: str) -> str` — 정규화 함수
- `match_by_normalized(unity_id, blend_rows) -> row | None`
- `match_by_path(unity_id, blend_rows) -> row | None`
- `match_by_alias(unity_id, blend_rows, alias_table) -> row | None`
- `verify_file_exists(relative_path, asset_root) -> bool`
- `main()` — CSV 읽고, 매칭 돌리고, 업데이트하고, 리포트 출력

### 상수 (모듈 상단)
```python
ASSET_ROOT = Path(r"C:\Users\manag\Desktop\BlenderRigConvert\Asset\Blender")
MIGRATION_CSV = Path(r"C:\Users\manag\Desktop\BlenderRigConvert\docs\MigrationInventory.csv")
BLEND_CSV = ASSET_ROOT / "animal_blend_inventory.csv"
ALIAS_TABLE = {}  # 1차 실행 후 필요하면 채움
```

## 사용자 워크플로

1. `python scripts/_oneoff_match_blend_inventory.py` 실행
2. stdout 리포트에서 unresolved 개수와 per-entry detail 확인
3. `???` 항목이 있으면 둘 중 하나:
   - 원인이 알리아스 부재면 `ALIAS_TABLE`에 추가 후 재실행
   - 원인이 진짜 누락이면 수동으로 `docs/MigrationInventory.csv` 열어
     `source_blend_hint`에 대응 `.blend` 경로를 직접 입력 (또는 공란 유지)
4. 모든 `source_blend_hint`가 채워지면 종료 — 다음 세션에서 blend-first
   파이프라인 설계로 넘어감

## 완료 기준

- `docs/MigrationInventory.csv`의 22개 `in_scope` 엔트리 중 최대 가능한
  수가 `source_blend_hint`에 채워져 있음 (남은 건 사용자가 수동 확인 후
  유지 or 채움)
- stdout 리포트가 깔끔하게 나옴
- 변경 사항 커밋됨 (`docs(migration):` scope)

## 재개 시 참고

향후 아트 팀이 Unity에 새 동물을 추가하거나 기존 동물의 blend가 업데이트되면:
- `animal_blend_inventory.csv`를 먼저 갱신 (수동 큐레이션)
- 이 스크립트를 다시 커밋 로그에서 찾아 실행

스크립트를 `tools/`로 승격시키는 건 2회차 요구가 실제로 발생했을 때만.

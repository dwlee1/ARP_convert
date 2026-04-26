# MCP 피드백 루프 확장 설계 (Sub-project ②)

> 작성일: 2026-04-05
> Sub-project: 3개 통합 개선의 2/3 (작업 프로세스 → **MCP 피드백 루프** → 코드 건강)
> 연관: `scripts/mcp_bridge.py`, 2026-04-05 F12 back_leg shoulder 작업에서 검증된 패턴
> 전제: Sub-project ①(작업 프로세스 규칙)의 브랜치/커밋/완료 기준 적용

## 문제 요약

`scripts/mcp_bridge.py`는 8개의 고수준 함수(scene summary, create preview, build rig, run regression, bone roles, weights, bake)를 제공하지만, 2026-04-05 F12 작업에서 **반복 사용했는데 브릿지에 없는 패턴**이 세 가지 식별되었다.

| 패턴 | F12에서의 사용 | 현재 우회 방식 |
|------|----------------|---------------|
| bone_pairs 역할별 조회 | `DEF-thigh_L → c_thigh_b.l` 매핑 확인 | raw `execute_blender_code`로 `arp_obj["arpconv_bone_pairs"]` 매번 직접 디코드 |
| 프레임별 월드 위치 비교 | 소스 vs ARP 본을 샘플 프레임에서 거리 측정 (0.186m → 0.00000m 검증) | 즉석 루프 작성 |
| dog 프리셋 본 이름 조회 | `c_toes` vs `c_toes_fk` 확정 | `bpy.data.libraries.load`로 즉석 코드 작성 |

패턴 자체는 효과적이었지만(F12 블로커를 MCP로 끝까지 해결 가능했음) 매번 재작성하면 일관성이 떨어지고 재현성이 낮다. 함수화 + 예시 문서화가 필요하다.

또한 `mcp_bridge.py`에는 현재 pytest가 전혀 없다. Blender 런타임 의존이 주된 이유지만, 순수 데이터 가공 로직까지 테스트 불가로 남기는 것은 과도하다.

## 목표

- F12 작업에서 반복 사용된 3가지 패턴을 브릿지 함수로 승격한다.
- 순수 Python 로직을 별도 모듈(`scripts/mcp_verify.py`)로 분리하고 pytest로 검증한다.
- 사용 예시와 F12-style 조합 레시피를 `docs/MCP_Recipes.md`에 정리한다.
- 함수 단위는 **작은 프리미티브**를 다수 만들고, 조합은 레시피 문서에서 제공한다(시나리오 함수로 뭉치지 않음).

Non-goals:
- 기존 8개 브릿지 함수 수정(`mcp_scene_summary`, `mcp_create_preview`, `mcp_build_rig`, `mcp_run_regression`, `mcp_get_bone_roles`, `mcp_set_bone_role`, `mcp_validate_weights`, `mcp_bake_animation`)
- `ensure_object_mode` / `get_3d_viewport_context` 중복 호출 리팩터링 (Sub-project ③ 범위)
- `mcp_bridge.py` 전체 리팩터링 또는 모듈 분할 (Sub-project ③ 범위)
- Addon 내부의 reload 오퍼레이터 추가 (Sub-project ③ 범위)
- Fixture 기반 회귀 테스트 확장
- mcp 브릿지의 외부 프로세스 자동화(CI 등)

## 변경 사항

### 1. `scripts/mcp_verify.py` (신규)

`bpy` import 없는 순수 Python 헬퍼. pytest로 직접 호출 가능. 바디가 자명한 한 줄짜리는 넣지 않는다 ─ "pytest로 값 검증할 가치가 있는 로직"만 분리한다.

```python
"""
mcp_bridge에서 분리한 순수 데이터 가공 로직.

bpy 의존 없이 단위 테스트 가능. mcp_bridge의 각 함수는
(1) bpy 호출로 raw 데이터 수집 → (2) 이 모듈의 헬퍼로 가공 → (3) JSON 출력
구조를 가진다.
"""

def filter_pairs_by_role(bone_pairs, ref_to_role_idx, role_filter=None):
    """bone_pairs를 역할별로 필터링한다.

    Args:
        bone_pairs: [(src, tgt, is_custom), ...] 리스트
        ref_to_role_idx: {ref_name: (role, idx)} 매핑 (호출부에서 구성하여 전달)
        role_filter: None이면 전체. 문자열이면 정확 매칭. 리스트/set이면 포함 매칭.

    Returns:
        [{"source": src, "target": tgt, "is_custom": bool, "role": role_or_None}, ...]
    """


def compute_position_stats(distances):
    """거리 float 리스트에서 min/max/mean을 집계한다.

    빈 리스트는 {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'count': 0}을 반환한다.
    """


def format_comparison_report(pair_results):
    """프레임 비교 결과를 읽기 쉬운 멀티라인 문자열로 변환한다.

    입력: [{"src": str, "arp": str, "max_err": float, "mean_err": float, ...}, ...]
    출력: 정렬된 테이블 문자열 (print용)
    """


def match_bone_names(bone_names, pattern):
    """본 이름 리스트에서 정규식 매칭되는 항목을 정렬된 리스트로 반환한다.

    pattern이 None이면 전체 정렬 반환. 잘못된 정규식은 re.error를 그대로 전파한다
    (호출부에서 처리).
    """
```

**바디는 plan 단계에서 작성.** 이 스펙은 인터페이스와 의미만 고정한다.

### 2. `tests/test_mcp_verify.py` (신규)

```python
"""
mcp_verify 순수 헬퍼 pytest.
"""

import pytest
import mcp_verify as mv


class TestFilterPairsByRole:
    def test_none_filter_returns_all(self): ...
    def test_string_filter_exact_match(self): ...
    def test_list_filter_multi_role(self): ...
    def test_empty_pairs_returns_empty(self): ...
    def test_pair_without_ref_mapping_has_none_role(self): ...


class TestComputePositionStats:
    def test_empty_returns_zero_stats(self): ...
    def test_uniform_distances_min_equals_max_equals_mean(self): ...
    def test_mixed_distances(self): ...
    def test_single_element(self): ...


class TestFormatComparisonReport:
    def test_report_contains_all_pair_names(self): ...
    def test_report_shows_max_error(self): ...
    def test_empty_results_returns_header_only(self): ...


class TestMatchBoneNames:
    def test_none_pattern_returns_sorted_all(self): ...
    def test_prefix_match(self): ...
    def test_regex_alternation(self): ...
    def test_escape_dot(self): ...
    def test_no_match_returns_empty(self): ...
```

**목표 테스트 수**: 약 17개 (filter=5, stats=4, format=3, match=5). 기존 103 + 17 = **120 passed**.

각 테스트의 입력/출력 구체값은 plan 단계에서 정한다.

### 3. `scripts/mcp_bridge.py` (수정) — 신규 함수 3개 추가

기존 8개 함수 뒤, 파일 끝에 새 섹션으로 추가. `_reload()`에 `mcp_verify` 추가.

#### 3a. `mcp_inspect_bone_pairs(role_filter=None)`

```python
def mcp_inspect_bone_pairs(role_filter=None):
    """ARP 리그의 arpconv_bone_pairs를 디코드하고 역할 정보와 함께 반환.

    Args:
        role_filter: None | str | list — 역할 필터 (mcp_verify.filter_pairs_by_role 참조)

    사용 예: F12 bake 이후 특정 역할(예: back_leg_l)이 어느 컨트롤러에 매핑됐는지 확인.
    """
```

구현 개요:
1. `find_arp_armature()` 호출
2. `arp_obj[BAKE_PAIRS_KEY]` 디코드 (`deserialize_bone_pairs`)
3. `skeleton_analyzer.ARP_REF_MAP` 기준으로 `ref_to_role_idx` 구성
4. `mcp_verify.filter_pairs_by_role(...)` 호출
5. `_result(True, {...})`로 출력

#### 3b. `mcp_compare_frames(pairs, frames, action_name=None)`

```python
def mcp_compare_frames(pairs, frames, action_name=None):
    """소스와 ARP 본의 월드 위치를 지정한 프레임에서 비교.

    Args:
        pairs: [(src_bone_name, arp_bone_name), ...] — 비교할 본 쌍
        frames: [int, ...] — 샘플 프레임 리스트
        action_name: None이면 현재 액션 유지. 문자열이면 소스/ARP 양쪽에 같은 base 액션을
                     세팅 (ARP는 "<name>_arp" 규칙).

    사용 예: F12 Task 6에서 walk 액션 8프레임 샘플로 leg 오차 0.186m → 0.00000m 검증.
    """
```

구현 개요:
1. 소스/ARP 아마추어 찾기
2. `action_name` 주어지면 양쪽에 설정 (`<name>` / `<name>_arp`)
3. 각 프레임에서 `bpy.context.scene.frame_set(f)` 후 `obj.matrix_world @ pose_bone.head`로 월드 위치 계산, 거리 측정
4. `mcp_verify.compute_position_stats(...)`로 통계 집계
5. `mcp_verify.format_comparison_report(...)`로 보고서 생성
6. 결과를 `_result`로 출력

주의: MCP 컨텍스트에서는 `bpy.ops`를 피하고 `bpy.data`/`bpy.context.scene.frame_set` 직접 사용.

#### 3c. `mcp_inspect_preset_bones(preset='dog', pattern=None)`

```python
def mcp_inspect_preset_bones(preset='dog', pattern=None):
    """ARP 애드온의 armature_presets/<preset>.blend를 libraries.load로 읽고 본 이름을 반환.

    Args:
        preset: 프리셋 이름 (기본 'dog')
        pattern: 정규식 문자열. None이면 전체 반환.

    사용 예: F12에서 c_toes vs c_toes_fk 확정, c_thigh_b.l 실존 확인.
    """
```

구현 개요:
1. ARP 애드온 경로 탐색 (`bl_ext.user_default.auto_rig_pro` 모듈 기준)
2. `<addon>/armature_presets/<preset>.blend` 경로 확인
3. `bpy.data.libraries.load(path, link=False)`로 armature data만 로드
4. armature data의 본 이름 수집
5. `mcp_verify.match_bone_names(...)`로 필터
6. **cleanup**: 로드된 armature data가 고아로 남지 않도록 `bpy.data.armatures.remove(...)` 호출
7. `_result`로 출력

**`_append_arp` 대신 `libraries.load`를 쓰는 이유**: F12 작업 중 MCP 환경에서 `_append_arp`가 `'NoneType' object has no attribute 'overlay'` 에러로 실패. `libraries.load`는 viewport context 없이 동작한다(이번 세션에서 검증 완료).

### 4. `docs/MCP_Recipes.md` (신규)

구조:

```markdown
# MCP 브릿지 사용 레시피

## 언제 MCP 브릿지를 쓰는가

- GUI 클릭-수정-재시도 사이클의 비용이 크다고 느껴질 때
- Blender 상태를 즉석에서 조회·수정·검증하고 싶을 때
- 숫자 기반 검증(프레임별 위치 비교, 통계)을 원할 때
- 반복적 확인 작업 자동화

## 함수 인덱스

| 함수 | 용도 | 주요 파라미터 |
|------|------|-------------|
| `mcp_scene_summary()` | 씬 요약 | 없음 |
| `mcp_create_preview()` | Preview 생성 | 없음 |
| `mcp_build_rig()` | Build Rig 실행 | 없음 |
| `mcp_run_regression(fixture)` | 회귀 테스트 | fixture 경로 |
| `mcp_get_bone_roles()` | 본 역할 조회 | 없음 |
| `mcp_set_bone_role(bone, role)` | 본 역할 변경 | 본명, 역할 |
| `mcp_validate_weights()` | 웨이트 커버리지 | 없음 |
| `mcp_bake_animation()` | F12 베이크 | 없음 |
| `mcp_inspect_bone_pairs(role_filter)` | **신규**: bone_pairs 조회 | 역할 필터 |
| `mcp_compare_frames(pairs, frames, action)` | **신규**: 월드 위치 비교 | 본 쌍, 프레임, 액션 |
| `mcp_inspect_preset_bones(preset, pattern)` | **신규**: 프리셋 본 이름 | 프리셋명, 정규식 |

## 단일 함수 예시

각 함수별로 `execute_blender_code` 호출 스니펫 + 예상 출력 1개씩.

## 조합 레시피

### 레시피 A: Bake 결과 정확성 검증 (F12 Task 6 재현)

[mcp_inspect_bone_pairs → mcp_compare_frames 조합 예시. 실제 F12 walk 액션 결과를 인용하여 뒷다리 0.00000m / 앞다리 dupli 3.64mm가 나오는 예상 출력 포함.]

### 레시피 B: 새 버그 패턴 발견 시 프리셋 실존 확인 (F12 c_toes_fk 발견 재현)

[mcp_inspect_preset_bones 예시. pattern="^c_toes"로 조회하면 c_toes.l이 없고 c_toes_fk.l만 있는 실제 출력 인용.]

### 레시피 C: 코드 수정 후 빠른 재검증

[_reload 동작 + mcp_build_rig + mcp_inspect_bone_pairs 조합. "수정 → 1분 내 검증" 사이클 설명.]

## F12 사례 요약

2026-04-05 F12 back_leg shoulder 작업에서 이 레시피들이 실제로 어떻게 쓰였는지 1페이지 이내 요약. 링크: `docs/ProjectPlan.md`, 커밋 2a07d78 / 8dce2a0 / 5d6b301.
```

**레시피 내 코드 스니펫과 예상 출력은 plan 단계에서 MCP로 실제 실행해 snapshot**한다(허구 값 금지).

## 검증 절차

1. **순수 헬퍼 테스트**: `pytest tests/test_mcp_verify.py -v` → 17 passed
2. **전체 회귀**: `pytest tests/ -v` → **120 passed** (103 + 17)
3. **Ruff**: `ruff check scripts/ tests/` → clean
4. **브릿지 수동 스모크 테스트** (Blender + BlenderMCP 필요):
   - `mcp_inspect_bone_pairs(role_filter="back_leg_l")` → 2개 이상 결과
   - `mcp_compare_frames([("DEF-thigh_L", "c_thigh_b.l")], [0, 12, 24])` → 0.00000m 전후
   - `mcp_inspect_preset_bones("dog", "^c_thigh_b")` → 4개 본(.l/.r/dupli) 확인
5. **레시피 문서의 모든 스니펫 실행**: 문서에 포함된 모든 `execute_blender_code` 스니펫을 실제로 돌리고 결과를 문서의 "예상 출력" 블록에 삽입
6. **완료 기준 (Sub-project ①)**: pytest+ruff 통과, `docs/ProjectPlan.md`의 우선순위 섹션에 MCP 피드백 루프 완료 반영, `fix/feat/mcp-feedback-loop` 브랜치를 master에 fast-forward 머지

## 위험 및 주의

- **순수 함수 분리의 과도한 추상화**: `compute_position_stats`는 `min`/`max`/`sum` 조합이라 거의 자명하다. 그럼에도 pytest로 "빈 리스트 0.0 반환" 같은 엣지 케이스를 고정하는 가치가 있어 분리. 한 줄짜리 자명한 로직은 분리 대상에서 제외한다.
- **`libraries.load` 고아 데이터**: `mcp_inspect_preset_bones`가 호출될 때마다 `rig.002`, `rig.003`… 같은 armature data가 쌓일 수 있다. 반드시 cleanup 포함.
- **MCP 컨텍스트에서 `bpy.ops` 제약**: 신규 3개 함수는 가능한 한 `bpy.data` 직접 접근. `frame_set`은 안전.
- **모듈 리로드 타이밍**: `mcp_bridge._reload()`가 `mcp_verify`를 새 엔트리로 포함해야 함. 기존 `_reload` 함수 수정 필요.
- **`action_name` 시맨틱**: `mcp_compare_frames`의 `action_name` 파라미터는 "base name"을 받아 소스에는 `<name>`, ARP에는 `<name>_arp`를 자동 할당. 이 네이밍 규칙(`_arp` 접미사)은 F12 베이크 구현에서 이미 쓰이는 규칙이므로 그대로 차용. 규칙이 바뀌면 이 함수도 따라 바뀌어야 함.

## 기대 효과

- F12 같은 장기 디버그 작업의 검증 사이클이 "즉석 코드 → 실행 → 해석" 3단계에서 "함수 호출 → 해석" 2단계로 단축.
- `docs/MCP_Recipes.md`가 있으면 새 세션이 시작되어도 "지난번에 어떻게 했더라" 검색 비용이 0.
- 순수 헬퍼 pytest는 향후 mcp_bridge 리팩터링 시 행동 고정(golden test) 역할.
- Sub-project ③(코드 건강)의 addon 리팩터링에서 이 함수들을 검증 도구로 재사용 가능.

## Sub-project 연결

- 이 sub-project의 산출물(`mcp_inspect_bone_pairs`, `mcp_compare_frames`, `MCP_Recipes.md`)은 **Sub-project ③ 실행 중 검증 도구**로 사용된다. addon 분할 후 "기존과 동일하게 동작하는가"를 이 함수들로 매 체크포인트마다 확인.
- Sub-project ①의 커밋 컨벤션과 브랜치 전략을 이 sub-project의 구현에도 적용한다 (브랜치: `feat/mcp-feedback-loop` 권장).

## 스펙 범위 밖

- 기존 8개 함수 수정/리팩터링
- `ensure_object_mode` / `get_3d_viewport_context` 헬퍼 중복 호출 제거
- `mcp_bridge.py`의 모듈 분할
- Addon 내부 reload 오퍼레이터
- Fixture 생성/관리 자동화
- CI, 외부 실행 파이프라인

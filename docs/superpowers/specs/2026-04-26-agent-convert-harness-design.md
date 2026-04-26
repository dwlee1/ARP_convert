# Agent Convert Harness 설계

> 작성일: 2026-04-26
> 범위: 현재 Blender에 열린 단일 사족보행 `.blend` 파일을 AI 에이전트가 ARP 리그로 변환하고 리타겟까지 진행하는 MCP 중심 하네스
> 브랜치: `feat/agent-convert-harness`
> 우선순위 조정: Unity 이주 Phase 3은 보류하고, 일반 사족보행 리깅 컨버팅 자동화 하네스를 먼저 안정화한다.

## 문제 요약

현재 프로젝트에는 아래 기반이 이미 있다.

- `scripts/mcp_bridge.py`: Claude/Codex가 Blender를 제어할 수 있는 MCP 브릿지 함수 묶음
- `docs/MCP_Recipes.md`: MCP 함수 사용 레시피
- `.claude/skills/arp-quadruped-convert/SKILL.md`: Claude Code용 실제 변환 절차서
- `scripts/arp_ops_preview.py`, `scripts/arp_ops_build.py`, `scripts/arp_ops_bake_regression.py`: Preview, Build Rig, Retarget 오퍼레이터

하지만 현재 자동화는 "에이전트가 여러 MCP 함수를 올바른 순서로 호출한다"는 운영 지식에 의존한다. 이 방식은 다음 문제가 있다.

1. Claude 전용 스킬에는 절차가 있지만 Codex나 다른 에이전트는 같은 상태 판단을 공유하지 않는다.
2. 단계 실패 시 반환 형식이 일정하지 않아 사용자가 어떤 본/역할/환경을 고쳐야 하는지 바로 알기 어렵다.
3. 모든 진단 데이터를 대화로 출력하면 토큰 사용량이 커지고, 반대로 너무 적게 출력하면 원인 파악이 어렵다.
4. Build Rig와 Retarget은 시간이 오래 걸리므로 실패할 가능성이 높은 상태를 앞에서 걸러야 한다.

## 목표

단일 MCP 진입점으로 현재 Blender 씬을 변환한다.

```python
from mcp_bridge import mcp_agent_convert_current_file
mcp_agent_convert_current_file()
```

이 함수는 현재 열린 `.blend`를 대상으로 다음을 수행한다.

1. 씬 사전 검사
2. Preview 생성
3. 역할/신뢰도 게이트
4. ARP Build Rig
5. 웨이트 및 bone_pairs 검증
6. Setup Retarget
7. ARP native retarget 실행
8. Custom scale 복사
9. 샘플 프레임 검증
10. 요약 JSON 반환 및 상세 리포트 파일 저장

문제가 생기면 무리하게 다음 단계로 가지 않고 즉시 중단한다. 중단 결과는 사용자가 Blender UI나 MCP 역할 수정으로 고칠 수 있도록 `problem`, `evidence`, `recommended_fix`, `retry_from`을 포함한다.

## Non-goals

- Unity 이주 배치 처리
- 폴더 단위 대량 큐 처리
- `scripts/03_batch_convert.py` 개선
- Blender N-panel 신규 UI
- headless Blender 완전 자동화 보장
- Auto-Rig Pro 내부 동작 재구현
- 모든 본/모든 프레임에 대한 exhaustive 검증
- Cleanup 자동 실행 기본값 변경

## 설계 원칙

### 1. 단일 고수준 진입점

에이전트별 지침은 얇게 유지하고, 판단 로직은 `mcp_agent_convert_current_file()`에 둔다. Claude, Codex, 다른 에이전트는 같은 함수를 호출하고 같은 JSON 계약을 읽는다.

### 2. Compact-first 진단

기본 반환은 대화에 바로 넣어도 되는 작은 JSON이다.

- 현재 단계
- 최종 상태
- 진행된 단계 목록
- warnings
- 다음 행동
- 상세 리포트 경로

본 목록, 전체 매핑, 프레임별 raw 결과처럼 큰 데이터는 기본 반환하지 않는다. 대신 `agent_reports/<blend_name>_<timestamp>.json`에 저장한다.

### 3. 실패 단계만 상세 진단

모든 단계에서 상세 검사를 항상 돌리지 않는다. 기본은 저렴한 성공 조건만 확인하고, 문제가 발견된 단계에서만 상세 진단을 확장한다.

예시:

- Preview confidence가 낮을 때만 전체 역할/미매핑 본 목록을 포함
- bone_pairs 핵심 역할 누락 시에만 누락 역할과 가능한 ref/controller 이름을 포함
- 프레임 검증 오차가 클 때만 top offenders를 포함

### 4. 사용자 수정 가능 상태와 시스템 실패 구분

반환 상태는 다음 네 가지로 고정한다.

| 상태 | 의미 | 다음 행동 |
|------|------|----------|
| `complete` | 요청 범위 완료 | 결과 확인 |
| `blocked` | 사용자가 고치면 재시도 가능한 상태 | `recommended_fix` 수행 후 하네스 재실행 |
| `failed` | 코드/환경/ARP 호출 실패 | 오류 로그 확인 또는 코드 수정 |
| `partial` | Build Rig는 됐지만 Retarget은 진행하지 못함 | 중단 사유 확인 |

## MCP API

### `mcp_agent_convert_current_file`

```python
def mcp_agent_convert_current_file(
    *,
    include_retarget=True,
    allow_cleanup=False,
    confidence_threshold=0.80,
    verbosity="summary",
    report_dir=None,
):
    """Run the current-scene agent conversion pipeline and print a standard JSON result."""
```

#### 파라미터

| 파라미터 | 기본값 | 의미 |
|----------|--------|------|
| `include_retarget` | `True` | 액션이 있으면 Retarget까지 진행 |
| `allow_cleanup` | `False` | `True`일 때만 소스/프리뷰 삭제 Cleanup 실행 |
| `confidence_threshold` | `0.80` | Preview 자동 역할 추론 통과 기준 |
| `verbosity` | `"summary"` | `"summary"` 또는 `"diagnostic"` |
| `report_dir` | `None` | None이면 repo 루트의 `agent_reports/` 사용 |

Cleanup은 비가역성이 있으므로 기본 실행하지 않는다. 사용자가 명시적으로 원할 때만 `allow_cleanup=True`로 실행한다.

`retry_from`은 v1에서 실제 부분 재시작 파라미터가 아니라 사용자가 어느 단계를
수정해야 하는지 알려주는 진단 라벨이다. 수정 후에는
`mcp_agent_convert_current_file()`을 다시 실행한다.

## 반환 JSON 계약

### 완료 예시

```json
{
  "success": true,
  "status": "complete",
  "stage": "complete",
  "data": {
    "blend_file": "C:/path/fox.blend",
    "source_armature": "Armature",
    "arp_armature": "rig",
    "preview_confidence": 0.92,
    "steps_completed": [
      "preflight",
      "preview",
      "build_rig",
      "weights",
      "bone_pairs",
      "setup_retarget",
      "arp_retarget",
      "copy_custom_scale",
      "frame_verify"
    ],
    "warnings": [],
    "summary": {
      "bound_meshes": 3,
      "actions": 12,
      "bone_pairs": 28,
      "unweighted_vertices": 0,
      "frame_verify_pass_rate": 0.94,
      "max_position_error_mm": 2.4,
      "max_rotation_error_deg": 1.1
    },
    "report_path": "C:/repo/agent_reports/fox_20260426_154233.json"
  }
}
```

### 중단 예시

```json
{
  "success": false,
  "status": "blocked",
  "stage": "preview_roles",
  "error": {
    "problem": "Preview role confidence is below threshold.",
    "evidence": {
      "confidence": 0.63,
      "threshold": 0.8,
      "missing_roles": ["front_leg_l", "front_leg_r"],
      "unmapped_count": 17
    },
    "recommended_fix": "Open ARP Convert > Source Hierarchy, assign the missing front leg roles, then rerun from preview_roles.",
    "retry_from": "preview_roles"
  },
  "report_path": "C:/repo/agent_reports/rabbit_20260426_154400.json"
}
```

## 파이프라인 단계

### Stage 1. Preflight

검사:

- Blender 파일이 열려 있는지
- 소스 아마추어가 1개 이상 있는지
- 이미 ARP 리그가 있는지
- 메시가 아마추어 modifier로 바인딩되어 있는지
- 액션이 있는지
- ARP Convert 애드온 프로퍼티 접근 가능한지

중단:

- 소스 아마추어 없음 → `blocked`
- ARP 리그 이미 있음 → `blocked`
- 애드온 미등록 → `failed`
- 3D View context 없음 → `failed`

경고:

- 바인딩 메시 없음 → 계속 가능하지만 weight 검증은 제한됨
- 액션 없음 → Build Rig까지만 진행하고 `partial` 또는 `complete` 반환

### Stage 2. Preview

실행:

- `bpy.ops.arp_convert.create_preview()`

검사:

- operator가 `FINISHED` 반환
- `scene.arp_convert_props.is_analyzed == True`
- Preview armature 존재
- confidence 수집

중단:

- operator 실패 → `failed`
- confidence < threshold → `blocked`

진단 확장:

- confidence가 낮을 때 `mcp_get_bone_roles(compact=False)` 수준의 역할 목록과 unmapped 목록을 상세 리포트에 저장한다.

### Stage 3. Build Rig

실행:

- `bpy.ops.arp_convert.build_rig()`

검사:

- operator가 `FINISHED` 반환
- ARP armature 존재
- dog preset 기반 `c_` controller 본이 생성됨
- `arpconv_bone_pairs` 커스텀 프로퍼티 존재

중단:

- ARP 생성 실패 → `failed`
- bone_pairs 없음 → `failed`

### Stage 4. Weight Verify

실행:

- 기존 `mcp_validate_weights(summary=True)` 로직 재사용

검사:

- bound mesh 수
- unweighted vertex 수
- 비어 있는 vertex group 요약

중단:

- unweighted vertex가 0보다 크고 실제 deform mesh에 해당하면 `blocked`

경고:

- 컨트롤/도우미성 빈 그룹은 계속 진행 가능

### Stage 5. Bone Pairs Verify

검사:

- root 또는 trajectory 매핑 존재
- spine/head/leg/foot 주요 역할 매핑 존재
- `leg` 3본 역할은 `thigh_b` 컨트롤러로 연결됨
- foot 역할은 `foot/toes` 계열 컨트롤러로 연결됨
- custom bone은 `custom_bone` 프로퍼티 또는 `cc_` 대상에 연결됨

중단:

- 핵심 역할 매핑 누락 → `blocked`
- dog preset에 없는 컨트롤러명으로 매핑 → `failed`

진단 확장:

- 누락 역할, 해당 source bone, 가능한 ARP ref/controller 패턴을 상세 리포트에 저장한다.

### Stage 6. Setup Retarget

실행:

- `mcp_setup_retarget()` 내부 로직 재사용

검사:

- `bones_map_v2`가 채워짐
- batch retarget 플래그가 설정됨
- source/target armature가 올바르게 지정됨

중단:

- 액션이 없으면 Retarget 단계는 건너뛰고 `complete` 반환
- setup 실패 → `failed`

### Stage 7. ARP Retarget

실행:

- `bpy.ops.arp.retarget()`

검사:

- `_remap` 액션 생성 여부
- remap 액션이 최소 1개 생성되었는지
- source action 수와 remap action 수를 상세 리포트에 함께 기록

중단:

- ARP operator 실패 → `failed`
- remap 액션 0개 → `blocked`

주의:

- 기존 Claude 스킬은 사용자가 ARP Re-Retarget 버튼을 수동 클릭하도록 중단한다. 이번 하네스는 MCP에서 `bpy.ops.arp.retarget()`을 직접 시도한다. Blender/ARP 컨텍스트 문제로 실패하면 `blocked`로 반환하고 수동 클릭 안내를 제공한다.

### Stage 8. Copy Custom Scale

실행:

- `bpy.ops.arp_convert.copy_custom_scale()`

검사:

- operator 반환값
- custom scale fcurve 복사 개수

경고:

- custom bone이 없으면 스킵 가능

### Stage 9. Frame Verify

기본 검증은 작게 유지한다.

- 핵심 pair 최대 8개
- 액션당 5프레임 샘플
- 기본은 대표 액션 1개

검사:

- 위치 오차 max/mean
- 회전 오차 max/mean
- pass count
- top offenders

기본 임계값:

- 위치 max 10mm 초과 시 `blocked`
- 회전 max 5도 초과 시 `blocked`
- pass rate 80% 미만 시 `blocked`

진단 확장:

- 실패 시에만 offending pair별 프레임 상세를 리포트에 저장한다.

### Stage 10. Optional Cleanup

기본값 `allow_cleanup=False`에서는 실행하지 않는다.

`allow_cleanup=True`일 때:

- `bpy.ops.arp_convert.cleanup()`
- 삭제된 armature 목록
- rename된 action 목록

Cleanup 실패는 Build/Retarget 결과 자체를 실패로 보지 않고 `warning`에 남긴다.

## 상세 리포트 파일

기본 위치:

```text
agent_reports/<blend_stem>_<YYYYMMDD_HHMMSS>.json
```

리포트에는 다음을 저장한다.

- 입력 파일 경로
- 각 단계 시작/종료 시간
- 단계별 compact result
- warnings
- failure diagnostic
- role summary
- weight summary
- bone_pairs summary
- retarget action summary
- frame verification summary
- 필요 시에만 상세 role/unmapped/pair/frame data

`agent_reports/`는 실행 산출물이므로 `.gitignore`에 추가한다.

## 에이전트 사용 규약

Claude/Codex 공통 지침은 다음 수준으로 줄인다.

```python
import sys
repo_scripts = r"<repo-root>\scripts"
if repo_scripts not in sys.path:
    sys.path.insert(0, repo_scripts)
from mcp_bridge import mcp_agent_convert_current_file
mcp_agent_convert_current_file(include_retarget=True)
```

에이전트는 반환 JSON만 해석한다.

- `complete`: 요약 보고
- `blocked`: `problem`, `evidence`, `recommended_fix`를 사용자에게 보여주고 중단
- `failed`: 오류와 report path를 보여주고 중단
- `partial`: 완료된 범위와 진행하지 못한 범위를 보고

에이전트가 raw Blender 코드를 즉석 작성하는 것은 fallback으로만 허용한다.

## 테스트 전략

### 순수 Python 테스트

새 모듈:

- `scripts/agent_convert_contract.py`

역할:

- stage result 생성
- status 분류
- compact/diagnostic payload 크기 제어
- frame sample 선택
- threshold 판정
- report path 생성

테스트:

- blocked result에는 `problem`, `evidence`, `recommended_fix`, `retry_from`이 항상 있다
- summary verbosity에서는 큰 리스트를 반환하지 않는다
- diagnostic verbosity에서는 실패 단계 상세만 포함한다
- frame sampling은 긴 액션에서도 5개 프레임만 고른다
- threshold 초과 시 상태가 `blocked`가 된다

### Blender/MCP 스모크

수동 Blender 세션에서 실행한다.

1. 테스트 `.blend` 열기
2. `mcp_reload_addon()`
3. `mcp_agent_convert_current_file(include_retarget=True)`
4. 반환 JSON 확인
5. 생성된 `agent_reports/*.json` 확인

### 기존 검증

코드 수정 완료 후 실행한다.

```bash
python -m pytest tests/ -v
python -m ruff check scripts/ tests/
```

현재 작업 환경에서 `pytest`, `ruff`, `uv`, `python`이 PATH에 없을 수 있으므로, 구현 계획에는 실행 가능한 Python 환경 확인 단계를 포함한다.

## 문서 변경

수정 대상:

- `docs/MCP_Recipes.md`: 새 단일 함수 사용법과 반환 상태 해석 추가
- `.claude/skills/arp-quadruped-convert/SKILL.md`: 기존 긴 단계별 raw MCP 호출을 단일 함수 중심으로 축소
- `.agents/skills/arp-quadruped-convert/SKILL.md`: Codex가 같은 MCP 진입점을 쓰도록 Claude 스킬과 동기화
- `AGENTS.md`: Codex/Claude 공통 MCP 진입점 규약 추가
- `docs/ProjectPlan.md`: Unity 이주 보류와 agent convert harness 우선순위 반영

## 성공 기준

1. 현재 열린 단일 `.blend`에서 에이전트가 `mcp_agent_convert_current_file()` 하나로 Build Rig + Retarget까지 진행할 수 있다.
2. 문제가 생기면 다음 단계로 진행하지 않고 `blocked` 또는 `failed`로 중단한다.
3. 중단 결과는 사용자가 수정할 수 있는 구체적 항목을 포함한다.
4. 기본 반환 JSON은 compact하며 전체 상세는 리포트 파일에 저장된다.
5. Claude/Codex 모두 같은 MCP 진입점과 같은 상태 계약을 사용한다.
6. 순수 Python 테스트와 기존 pytest/ruff 검증 경로가 마련된다.

## 구현 순서 제안

1. 순수 계약/리포트 헬퍼를 추가한다.
2. `mcp_bridge.py`에 `mcp_agent_convert_current_file()` skeleton을 추가하고 preflight만 연결한다.
3. Preview + confidence gate를 연결한다.
4. Build Rig + weight/bone_pairs 검증을 연결한다.
5. Setup Retarget + ARP retarget + custom scale을 연결한다.
6. compact frame verification을 연결한다.
7. 리포트 파일 저장과 문서/스킬 업데이트를 마무리한다.

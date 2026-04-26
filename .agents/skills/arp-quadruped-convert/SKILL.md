---
name: arp-quadruped-convert
description: >
  사족보행 동물 리그를 Auto-Rig Pro(ARP) 리그로 변환하는 자동 워크플로우.
  Blender MCP를 통해 파이프라인을 자동 실행하고, 문제 발생 시만 중단한다.
  다음 표현을 언급할 때 사용: "리그 변환 실행", "ARP로 변환", "동물 리그 컨버트",
  "사족보행 변환", "여우 변환", "quadruped convert", "rig convert 실행",
  "변환 파이프라인 실행", "리타겟 실행", "애니메이션 옮기기".
  개발/코드 수정이 아닌 실제 변환 작업을 실행할 때 이 스킬을 사용한다.
---

# 사족보행 동물 리그 → ARP 변환

Blender에 현재 열린 단일 사족보행 `.blend` 파일을 공통 MCP 하네스로 변환한다.
판단 로직은 `mcp_agent_convert_current_file()`에 있으며, 에이전트는 반환 JSON만 해석한다.

## 전제 조건

- Blender 실행 중 + BlenderMCP 연결
- ARP Rig Convert 애드온 활성화
- 소스 아마추어가 있는 `.blend` 파일이 열려 있음

## 기본 실행

```python
import sys
repo_scripts = r"C:\Users\DWLEE\ARP_convert\scripts"
if repo_scripts not in sys.path:
    sys.path.insert(0, repo_scripts)

from mcp_bridge import mcp_agent_convert_current_file

mcp_agent_convert_current_file(include_retarget=True)
```

기본값은 Cleanup을 실행하지 않는다. 사용자가 명시적으로 원할 때만
`allow_cleanup=True`를 전달한다.

## 결과 해석

- `complete`: 변환 완료. `summary`와 `report_path`를 사용자에게 보고한다.
- `partial`: 일부 단계만 완료됐다. 완료된 단계, 경고, 다음 행동을 보고한다.
- `blocked`: 사용자가 수정 가능한 상태다. `problem`, `evidence`, `recommended_fix`,
  `retry_from`, `report_path`를 보고하고 중단한다.
- `failed`: 환경/코드/ARP 호출 실패다. `error`와 `report_path`를 보고하고 중단한다.

`blocked`에서 임의로 다음 단계로 진행하지 않는다. `recommended_fix`를 수행한 뒤
`mcp_agent_convert_current_file()`을 다시 실행한다. `retry_from`은 v1에서 부분 재시작
파라미터가 아니라 진단 라벨이다.

## 원칙

- ARP 프리셋은 `dog` 고정이다.
- ARP ref 본 추가/삭제에 `edit_bones.new()`를 사용하지 않는다.
- 얼굴 본은 기본 face rig가 아니라 unmapped/`cc_` 커스텀 본 흐름으로 처리한다.
- raw Blender Python 작성은 하네스가 `failed`를 반환했고 원인 확인이 필요한 경우에만 사용한다.
- 상세 role, bone_pairs, frame verification 데이터는 `agent_reports/*.json`에서 확인한다.

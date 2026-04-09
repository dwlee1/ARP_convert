---
name: blender-rig-dev
description: >
  BlenderRigConvert (Blender 4.5 + Auto-Rig Pro 변환 애드온) Tier 2 개발 워크플로우.
  다음 표현을 언급할 때 사용: "ARP 변환", "Auto-Rig Pro 변환", "arp convert", "리그 변환",
  "ref 본", "bone role", "역할 매핑", "Preview Armature", "mcp_build_rig",
  "mcp_compare_frames", "BlenderRigConvert", "rig convert".
  Tier 1(1-3줄 수정)은 바로 구현. Tier 3(새 서브시스템/아키텍처 결정)은 superpowers:brainstorming.
---

# BlenderRigConvert 개발 워크플로우 (Tier 2)

Tier 2: 3-10개 파일 변경, 기존 아키텍처 범위 내. spec/plan 파일 없이 한 세션에서 완결.

---

## 1. 사전 확인 (코드 수정 전)

- [ ] `docs/ProjectPlan.md` 읽기 — 현재 우선순위 확인
- [ ] Hard Rules 체크:
  - `edit_bones.new()` 금지 → ARP 네이티브 함수 사용
  - ARP 프리셋 `dog` 고정
  - face 역할 → unmapped (커스텀 본으로 처리)
  - leg 3본 → `thigh_b_ref` 포함
  - foot 1개 → `foot_ref + toes_ref` 분할
  - 코드 수정 시 addon / pipeline / batch 경로 모두 확인

---

## 2. 인라인 계획 (대화 내, 파일 저장 안 함)

- [ ] 변경 파일 목록 나열
- [ ] ARP 네이티브 API 필요 여부 (`set_spine` / `set_neck` / `set_tail` / `set_ears`)
- [ ] 테스트 방식: 순수 Python → pytest / Blender 연동 → MCP 스모크
- [ ] 브랜치 생성: `feat/<name>` 또는 `fix/<name>`

---

## 3. 구현 참고

| 역할 | 파일 |
|------|------|
| 분석 / Preview | `skeleton_analyzer.py` |
| BuildRig 헬퍼 | `arp_build_helpers.py` |
| cc 본 / 제약 | `arp_cc_bones.py` |
| 웨이트 전송 | `arp_weight_xfer.py` |
| Foot 가이드 | `arp_foot_guides.py` |
| MCP 브릿지 | `mcp_bridge.py` |
| 공통 유틸 | `arp_utils.py` |

**ARP 체인 함수** (ARP 아마추어 활성 + Edit Mode + 해당 ref 본 선택 필요):

| 함수 | 용도 |
|------|------|
| `set_spine(count=N)` | spine ref 본 수 |
| `set_neck(neck_count=N)` | neck ref 본 수 |
| `set_tail(tail_count=N)` | tail ref 본 수 |
| `set_ears(ears_amount=N, side_arg='.l')` | 귀 ref 수 (L/R 개별) |

호출 후 `match_to_rig` 필수.

---

## 4. 검증 (모두 통과해야 "완료")

```bash
pytest tests/ -v
ruff check scripts/ tests/
```

이후 `/sync-addon` 실행 후 MCP 스모크:

```python
import sys; sys.path.insert(0, r'C:\Users\manag\Desktop\BlenderRigConvert\scripts')
from mcp_bridge import mcp_reload_addon, mcp_inspect_bone_pairs, mcp_compare_frames
mcp_reload_addon()
```

**변경 종류별 추가 검증:**

| 변경 종류 | 추가 MCP 검증 |
|-----------|--------------|
| 역할/ref 본 | `mcp_build_rig()` → `mcp_inspect_bone_pairs()` |
| 애니메이션/bake | `mcp_compare_frames(pairs, frames, detailed=False)` |
| UI/패널 | Blender N-panel 탭 육안 확인 |

---

## 5. 완료 처리

- [ ] 커밋: `feat(scope): 설명` / `fix(scope): 설명` (scope = F12, addon, mcp 등)
- [ ] `docs/ProjectPlan.md` 상태 업데이트
- [ ] `git merge --ff-only` → master

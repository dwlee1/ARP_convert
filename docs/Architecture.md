# Architecture (참조)

`AGENTS.md`에서 분리한 구현 디테일·내부 API 레퍼런스. 작업 중 필요할 때만 펼친다.

## 핵심 데이터 구조

- **analysis**: `analyze_skeleton(armature) → {bone_data, chains: {role: {bones, confidence}}, unmapped, confidence}`
- **roles**: `read_preview_roles(preview) → {role: [bone_names]}`
- **bone_pairs**: `[(src_bone, arp_ctrl, is_custom)]` — ARP 아마추어에 JSON 저장 (`arpconv_bone_pairs`)
- **ref_meta**: `{ref_name: {head, tail, mid, length, side, role, segment_index}}`

## 파이프라인 흐름

Source → `analyze_skeleton()` → Analysis → `create_preview_armature()` → Preview
→ 역할 편집 → `read_preview_roles()` → roles
→ `BuildRig`: append ARP(dog) → `discover_arp_ref_chains()` → `_adjust_chain_counts()`
→ `map_role_chain()` → `match_to_rig()` → cc bones → weight transfer → 완료

## ARP 네이티브 체인 조정 함수

체인 개수 매칭은 `edit_bones.new()` 방식이 아닌 ARP 내부 함수를 사용한다.

- 모듈: `bl_ext.user_default.auto_rig_pro.src.auto_rig`
- `set_spine(count=N)` — spine ref 본 선택 필요
- `set_neck(neck_count=N)` — neck ref 본 선택 필요
- `set_tail(tail_count=N)` — tail ref 본 선택 필요
- `set_ears(ears_amount=N, side_arg='.l'|'.r')` — L/R 개별 호출
- 호출 조건: ARP 아마추어 활성 + Edit Mode + 해당 ref 본 선택
- 호출 후 ref 본 위치 수정 가능, 이후 `match_to_rig` 호출

## 현재 메인 구현 경로 (디테일)

- Preview는 분석/역할 수정/UI용으로 유지
- Build Rig까지 구현 완료 (분석 → Preview → 역할 수정 → ARP 리그 생성)
- **리타게팅 구현 완료** — ARP 네이티브 리타겟 위임 방식 (`arp_retarget.py`, `arp_ops_bake_regression.py`)
  - Setup Retarget: bone_pairs → bones_map_v2 자동 변환
  - Re-Retarget: `bpy.ops.arp.retarget('INVOKE_DEFAULT')` 호출
  - Copy Custom Scale: cc_ 커스텀 본 스케일 fcurve 별도 복사
  - Cleanup: 소스/프리뷰 삭제 + _remap 액션 rename
- 이전 리타게팅 구현(F10/F11, rest-delta bake)은 git history 참조 (`8d49a91` 커밋 이전) — 폐기된 설계 문서는 `docs/archive/` 참조

## blender-mcp 호출 패턴

Blender가 실행 중이고 BlenderMCP 애드온이 연결되어 있으면 AI에서 직접 Blender를 제어할 수 있다.
브릿지: `scripts/mcp_bridge.py` — 상세 함수 목록과 사용법은 `docs/MCP_Recipes.md` 참조.

```python
import sys; sys.path.insert(0, r'C:\Users\DWLEE\ARP_convert\scripts')
from mcp_bridge import mcp_scene_summary
mcp_scene_summary()
```

## 애드온 반영 / Blender 동기화

- `arp_utils.py` 또는 재수출 경로(`arp_retarget.py` 포함)를 수정했을 때는 일반 module reload만으로 현재 Blender 세션에 반영되지 않을 수 있다
- 이 경우 `mcp_reload_addon()` 기준으로 전체 애드온 재등록 후 확인하거나 Blender를 재시작한다
- addons 폴더를 하드링크로 운영 중이면 파일 수정 후 링크가 끊길 수 있으므로 필요 시 `.claude/skills/sync-addon/skill.md` 절차에 따라 다시 동기화한다

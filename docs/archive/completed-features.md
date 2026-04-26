# 완료된 후속 기능 기록 (Archive)

`docs/ProjectPlan.md`의 *후속 기능* 섹션에 누적되어 있던 완료 기록을 분리 보존한다. 현재 진행 중·보류 작업은 ProjectPlan.md 본문에서 다룬다.

## F12. 애니메이션 베이크 (ARP 네이티브 리타겟 위임 방식) — 2026-04-06 설계 확정 / Round 6 검증 완료

현행 기준 문서는 `docs/F12_ARP_NativeRetarget.md`이며,
`docs/archive/F12_ExactMatch.md` 의 rest-delta offset bake 방식은 폐기되었다.

**현재 방식**: Build Rig까지만 우리 애드온이 담당하고, 애니메이션 베이크는 ARP 리타겟 UI에 위임한다.

- Build Rig 시 `arp_obj["arpconv_bone_pairs"]`에 매핑 저장 (역할 본 + cc_ 커스텀 본, `is_custom` 플래그 포함)
- `Setup Retarget`이 bone_pairs를 `bones_map_v2`로 변환하고 리타겟 씬 설정을 자동 구성
- 베이크 자체는 사용자가 ARP Remap 패널에서 확인 후 `Re-Retarget`으로 실행
- `Cleanup`은 소스/프리뷰 삭제 + `_remap` 액션 rename 담당
- `Copy Custom Scale`은 ARP 리타겟이 무시하는 커스텀 본 스케일 fcurve를 후처리로 복사
- pipeline_runner는 `--retarget` 플래그로 setup → ARP retarget → scale copy → cleanup 경로를 실행

**구현 상태**:
- [x] Setup Retarget + Cleanup + Copy Custom Scale 오퍼레이터 구현
- [x] root 매핑 보정: `c_root_master.x` 대신 `c_root.x`, `set_as_root=True`
- [x] root 외 매핑 본 `ik=True` 월드 스페이스 매칭 적용
- [x] tail master COPY_ROTATION constraint mute 적용
- [x] 커스텀 본 DEF 소스 통일 및 scale fcurve 후처리 구현
- [x] 여우 리그 수동 검증에서 FK/IK/root/pole/batch_retarget 정상 확인
- [x] ARP 단일 root 슬롯 대응 — trajectory가 있으면 `c_traj` 행만 `set_as_root=True`
- [x] 여우 Round 6 기준 전체 흐름 재검증 및 체크리스트 반영

## MCP 피드백 루프 확장 완료 (2026-04-05)

`scripts/mcp_bridge.py`에 3개 함수 추가 + 순수 헬퍼 모듈 + 사용 레시피.

- 신규 브릿지 함수: `mcp_inspect_bone_pairs`, `mcp_compare_frames`, `mcp_inspect_preset_bones`
- 순수 로직 모듈: `scripts/mcp_verify.py` (pytest 17개 커버)
- 레시피 문서: `docs/MCP_Recipes.md` — 11개 함수 인덱스 + 3개 조합 레시피 + F12 사례 요약
- 총 테스트 수: 103 → 120 (신규 +17)
- MCP 스모크 검증: 여우 walk 액션 기준 back_leg 오차 2.9e-07 m 재현 (F12 해결 상태 유지)

이 함수들은 Sub-project ③(addon.py 분할) 실행 중 체크포인트 도구로 사용되었다.

## arp_convert_addon.py 분할 완료 (2026-04-05)

2969줄 단일 파일을 12개 모듈로 분할 + 레거시 스크립트 5개 삭제.

- 엔트리: `arp_convert_addon.py` (~148줄, bl_info + register/unregister만)
- PropertyGroup: `arp_props.py`
- UI: `arp_ui.py`
- 오퍼레이터 5개: `arp_ops_preview.py`, `arp_ops_roles.py`, `arp_ops_build.py`, `arp_ops_bake_regression.py`
- 헬퍼 5개: `arp_build_helpers.py`, `arp_cc_bones.py`, `arp_weight_xfer.py`, `arp_foot_guides.py`, `arp_fixture_io.py`
- 삭제된 레거시: `01_create_arp_rig.py`, `rigify_to_arp.py`, `bone_mapping.py`, `diagnose_arp_operators.py`, `inspect_rig.py` (1501줄)
- MCP 체크포인트: Phase별 11개 커밋 후 매번 bone_pairs + 프레임별 위치 비교 검증. F12 back_leg 오차 2.897e-07m 유지.

3개 통합 개선(Workflow / MCP / 코드 건강) 전체 완료.

이전 경로 실패 이유 (참고용):
- Preview bake 경로: 2026-03-30 실험에서 품질 불충분으로 폐기
- FBX clean armature 경로: Blender 4.5 Action Slot 문제 등 복잡성이 높아 삭제

## F8. 전체 웨이트 전송 — 검증 완료

구현과 실제 검증이 완료됐다. 위치 기반 매칭 + 사이드 필터 + 본 길이 비율 분할 + stretch/twist 정점별 proximity 분배까지 구현했고, 여우/너구리 리그 weight paint 검증에서 문제없음을 확인했다.

- stretch/twist 본은 proximity 기반으로 정점별 웨이트를 분배 (2026-04-09)
- 비-다리 역할 본(ear/spine/neck 등) deform_to_ref 직접 매핑 수정 완료

## F6. bank / heel 자동 배치 보정 — 동작 계약

기본 위치 가이드는 foot 방향/길이 비율로 자동 보정하고, 사용자가 이동한 가이드는 유지한다.

## UX 전면 개선 완료 (2026-04-16)

프리뷰 본 시인성, 역할 UI 가독성, 패널 구조를 상용 애드온 수준으로 개선.
스펙: `docs/superpowers/specs/archive/2026-04-15-ux-overhaul-design.md`
계획: `docs/superpowers/plans/archive/2026-04-15-ux-overhaul.md`

- [x] 색상 팔레트 재설계 — 17 역할 고유색, L/R 쌍 구분
- [x] ROLE_LABELS 한국어 라벨 딕셔너리
- [x] 프로퍼티 툴팁 한국어화 + 상태 추적 프로퍼티 (build_completed, mapped_bone_count 등)
- [x] ROLE_ITEMS 라벨 한국어 풀네임
- [x] 역할별 색상 아이콘 모듈 (`arp_role_icons.py`, `bpy.utils.previews` 기반)
- [x] 계층 트리 연결선 접두사 (`compute_tree_prefixes`)
- [x] 서브패널 구조 분리 — 단일 패널 → 7개 (MainPanel + Step 1~5 + 도구)
- [x] 뷰포트 부모 체인 하이라이트 핸들러 (`arp_viewport_handler.py`)
- [x] 애드온 등록 업데이트 (아이콘/핸들러 register/unregister)
- [x] 오퍼레이터 상태 플래그 + bone count 캐시

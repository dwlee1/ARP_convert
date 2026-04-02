# BlenderRigConvert

동물 캐릭터 리그를 Auto-Rig Pro 기반으로 통일하고, 리그 생성을 자동화한다.
리타게팅은 2026-04-02 전면 삭제 후 재설계 예정.

## 환경

- Blender 4.5 LTS + Auto-Rig Pro
- Python 3.11, Windows 11

## 기준 문서

- **`docs/ProjectPlan.md`** — 단일 기준 문서 (상태, 체크리스트, 남은 기능). 작업 전 반드시 읽을 것
- `docs/FoxTestChecklist.md` — 여우 파일 테스트 기록
- `docs/RegressionRunner.md` — 대표 샘플 GUI 회귀 테스트 (대량 처리 전략 아님)

## 파일 맵

| 파일 | 역할 |
|------|------|
| `scripts/skeleton_analyzer.py` | 구조 분석, Preview Armature 생성, ref 체인 탐색 |
| `scripts/arp_convert_addon.py` | Preview UI, BuildRig 오퍼레이터, 회귀 테스트 패널 |
| `scripts/arp_utils.py` | Blender / ARP 공통 유틸 |
| `scripts/weight_transfer_rules.py` | 웨이트 전송 (Blender 없이 테스트 가능) |
| `scripts/pipeline_runner.py` | 비대화형 단일 실행 경로 (Build Rig까지) |
| `scripts/03_batch_convert.py` | 배치 실행 경로 |
| `scripts/01_create_arp_rig.py` | [레거시] |
| `scripts/rigify_to_arp.py` | [레거시] |

레거시 파일은 현재 메인 경로와 실제 사용 여부를 확인한 뒤 수정한다.

## 위반 금지 규칙 (HARD RULES)

1. ARP ref 본 추가/삭제에 `edit_bones.new()` 사용 금지 → ARP 네이티브 `set_*` 함수 사용
2. ARP 프리셋은 `dog` 고정
3. face 역할은 unmapped에 통합, 커스텀 본으로 처리 (원본 이름 유지, `custom_bone` 프로퍼티 태깅)
4. `leg` 역할 본이 3개면 ARP도 3본 다리 체인 (`thigh_b_ref` 포함)
5. `foot` 역할 본이 1개면 `foot_ref + toes_ref`로 분할
6. 코드 수정 시 addon / pipeline / batch 경로 모두 확인

## 핵심 규칙

- ARP ref 본은 실제 리그에서 동적 탐색
- `foot` 역할 본이 2개면 `foot_ref`, `toes_ref`에 1:1 매핑
- toe 본이 없으면 `virtual toe` 사용
- ear는 `ear_01_ref / ear_02_ref`에 직접 매핑
- Preview Armature는 원본 이름 유지, 역할은 색상과 커스텀 프로퍼티로 표시

## ARP 네이티브 체인 조정 함수

- **중요**: 체인 개수 매칭은 `edit_bones.new()` 방식이 아닌 ARP 내부 함수를 사용해야 함
- 모듈: `bl_ext.user_default.auto_rig_pro.src.auto_rig`
- `set_spine(count=N)` — spine ref 본 선택 필요
- `set_neck(neck_count=N)` — neck ref 본 선택 필요
- `set_tail(tail_count=N)` — tail ref 본 선택 필요
- `set_ears(ears_amount=N, side_arg='.l'|'.r')` — L/R 개별 호출
- 호출 조건: ARP 아마추어 활성 + Edit Mode + 해당 ref 본 선택
- 호출 후 ref 본 위치 수정 가능, 이후 `match_to_rig` 호출

## 현재 메인 구현 경로

정확한 상태값과 우선순위는 항상 `docs/ProjectPlan.md`를 기준으로 본다.

- Preview는 분석/역할 수정/UI용으로 유지한다
- Build Rig까지 구현 완료 (분석 → Preview → 역할 수정 → ARP 리그 생성)
- **리타게팅 코드는 2026-04-02 전면 삭제됨** — 깨끗한 상태에서 재설계 예정
- 이전 리타게팅 구현(F10/F11)은 git history 참조 (`8d49a91` 커밋 이전)

## 검증

코드 수정 후 반드시 실행:
```
pytest tests/ -v
```
`.blend` 기준 검증 항목이 있으면 커밋 메시지에 명시한다.

## 작업 원칙

- 별도 진단 스크립트 단계를 기본 경로로 가정하지 않는다
- 우선순위 기능은 현재 메인 구현 경로를 직접 읽고 수정한다
- ARP 내부 동작 확인이 꼭 필요한 항목만 최소 범위 실험으로 검증한다
- 실행 경로가 여러 갈래이므로 한 경로만 고치고 끝내지 않는다
- fixture/회귀 도구를 늘리는 것보다 자동 역할 추론 정확도 개선을 우선한다

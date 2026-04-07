# DEF 본 분리 기능 통합 설계

> 설계 확정: 2026-04-07 (grill-me 세션)

## 1. 배경

원본 아마추어에서 deform 본이 컨트롤러 본 하위에 배치된 경우, ARP 리타겟 시
계층 구조 때문에 움직임이 왜곡되는 문제가 있다. DEF 본을 분리하여 독립적인
해부학적 계층을 만들면 ARP 리타겟이 깨끗한 계층에서 읽을 수 있다.

참조: `def_ctrl_separator.py` (여우 전용 하드코딩 버전, 이 설계의 원본)

## 2. 핵심 결정 사항

| # | 결정 |
|---|---|
| 1 | 모든 소스 아마추어에 무조건 적용 |
| 2 | 이미 `DEF-` 접두사인 본은 스킵 (중복 생성 안 함) |
| 3 | 하드코딩 테이블 없음 — 역할 기반 자동 계층 |
| 4 | 실행 시점: Build Rig 첫 단계 (역할 확정 후) |
| 5 | DEF 계층: 항상 역할 기반 강제 부착 |
| 6 | DEF 본: `use_deform=False` (리타겟 전용) |
| 7 | 원본 본: `use_deform` 유지 (메시 변형 담당) |
| 8 | VG rename 안 함 |
| 9 | Copy Transforms: DEF → 원본 (WORLD space) |
| 10 | Bone Collection: DEF 컬렉션만 생성, CTRL 안 건드림 |
| 11 | bone_pairs src_name: `DEF-{원본이름}` |

## 3. DEF 계층 역할 기반 부착 규칙

| 역할 | DEF 부모 |
|---|---|
| `root` | None (최상위) |
| `spine` 첫 본 | `DEF-{root본}` |
| `spine` 나머지 | 이전 spine DEF 본 |
| `neck` 첫 본 | spine 마지막 DEF 본 |
| `head` | neck 마지막 DEF 본 |
| `back_leg_l/r` 첫 본(thigh) | `DEF-{root본}` (pelvis) |
| `front_leg_l/r` 첫 본(shoulder) | spine 마지막 DEF 본 (chest) |
| `back_foot_l/r` | back_leg 마지막 DEF 본 |
| `front_foot_l/r` | front_leg 마지막 DEF 본 |
| `tail` 첫 본 | `DEF-{root본}` (pelvis) |
| `tail` 나머지 | 이전 tail DEF 본 |
| `ear_l/r` | `DEF-{head본}` |
| 커스텀 본 (eye, jaw 등) | `DEF-{head본}` 또는 가장 가까운 deform 조상 |

## 4. 실행 순서 (Build Rig 내부)

```
Build Rig execute():
  1. Preview 역할 읽기 (기존)
  2. ★ DEF 본 생성 (신규)
     - deform 본마다 DEF-{name} 생성 (DEF- 접두사 본은 스킵)
     - 역할 기반 부모-자식 계층 강제 적용
     - Copy Transforms constraint (DEF → 원본, WORLD space)
     - DEF bone collection 생성
     - DEF 본 use_deform=False
  3. ARP 리그 생성 (기존)
  4. bone_pairs 생성 — src_name이 DEF-{원본} (수정)
```

## 5. 영향 범위

### 수정 대상

| 파일 | 변경 |
|---|---|
| 신규 `scripts/arp_def_separator.py` | DEF 본 생성 + 계층 구축 + constraint + collection |
| `scripts/arp_ops_build.py` | Build Rig execute() 첫 단계에 DEF 생성 호출 추가 |
| `scripts/arp_ops_build.py` | bone_pairs 생성 시 src_name에 `DEF-` 접두사 반영 |
| `scripts/arp_convert_addon.py` | 신규 모듈 import 및 reload 등록 |
| `tests/` | DEF 생성 로직 단위 테스트 |

### 영향 없음

| 파일 | 이유 |
|---|---|
| `scripts/arp_utils.py` | Setup Retarget / Cleanup 변경 불필요 |
| `scripts/arp_weight_xfer.py` | VG rename 안 하므로 웨이트 전송 변경 불필요 |
| `scripts/skeleton_analyzer.py` | 분석은 DEF 생성 전에 완료됨 |

## 6. 기존 `def_ctrl_separator.py`와의 차이

| 항목 | def_ctrl_separator.py | 이 설계 |
|---|---|---|
| 계층 구조 | 하드코딩 (`DEF_HIERARCHY`) | 역할 기반 자동 생성 |
| 적용 대상 | 여우 전용 | 모든 동물 |
| VG rename | O (`DEF-` 접두사) | X (원본 유지) |
| 원본 deform | `use_deform=False` | `use_deform` 유지 |
| DEF deform | `use_deform=True` | `use_deform=False` (리타겟 전용) |
| Bone Collection | CTRL.* 하드코딩 정리 | DEF 컬렉션만 생성 |
| 실행 시점 | 독립 애드온 (수동) | Build Rig 내부 (자동) |

## 7. 검증 계획

- `pytest tests/ -v` 통과
- `ruff check scripts/ tests/` 통과
- MCP: `mcp_build_rig()` → bone_pairs에 `DEF-` 접두사 확인
- MCP: `mcp_setup_retarget()` → bones_map_v2에서 DEF- 소스 본 매핑 확인
- Blender에서 ARP 리타겟 실행 → 리타겟 품질 확인

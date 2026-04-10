# IK Pole Vector 문제 — 보류 및 논의 기록

## Status

**보류** (2026-04-10). 모든 저장소 옵션에 risk가 있고 현재 워크플로와의 정합성이
확인되지 않아 아키텍처 재검토 후 진행.

이 문서는 2026-04-09~10 사이의 논의를 보존하기 위한 기록이다. 실제 pole vector
수정 코드는 구현되지 않았고, 실패한 시도만 master에 주석과 함께 남아 있다.

## Context

ARP `match_to_rig`가 자동 결정하는 IK pole vector(`c_leg_pole.l/r`,
`c_leg_pole_dupli_001.l/r`) 위치가 사족보행 리그에서 무릎 굽힘 방향과 맞지 않는
경우가 발생한다. 사용자가 Build Rig 후 수동 조정해도 리빌드하면 초기화된다.

너구리(raccoon) 리그 테스트 중 앞다리 pole이 몸통 쪽으로 배치되는 현상이
관찰되었다. 뒷다리는 정상.

## 시도한 접근 (실패)

### Step 3.5 — `thigh_ref` roll 보정

`scripts/arp_ops_build.py`에 잠시 commit됐다가(5f9ac5e) 제거된 코드 블록.
현재 master에는 없고 reflog `5f9ac5e` 커밋에서만 참조 가능.
2026-04-10 Capybara 재현 테스트(0ff67cf 직전)에서 이 코드가 ARP 내부
`_align_leg_limbs`의 knee 재정렬을 유발한 원인으로 확정되어 최종 제거됨.

```python
# ARP의 auto_ik_roll=True 기본 경로가 앞다리에서 pole을 몸통 쪽으로 밀어내는
# 문제를 해결하려고 시도
thigh_eb.align_roll(z_target)
thigh_eb["leg_auto_ik_roll"] = 0
```

**실패 현상**:

```text
=== Pole Vector 결과 ===
  뒷다리 L: pole_Y=0.441 knee_Y=0.166 → 정상
  뒷다리 R: pole_Y=0.441 knee_Y=0.166 → 정상
  앞다리 L: pole_Y=0.138 knee_Y=-0.129 → 잘못됨
  앞다리 R: pole_Y=0.138 knee_Y=-0.129 → 잘못됨
```

**시도한 수정**:

- cross product 순서 정정 (`bone_dir.cross(bend_perp)` → `bend_perp.cross(bone_dir)`)
- `align_roll`이 Z축을 정렬하는 점 반영
- 프로퍼티 키 수정 (`auto_ik_roll` → `leg_auto_ik_roll`)
- 직선 다리 fallback 임계값 조정

**실패 원인 추정**: `leg_auto_ik_roll=0` 프로퍼티가 설정되었음에도 ARP 내부의
`_align_leg_limbs` 로직이 앞다리에서 `thigh_ref_dupli_001`의 roll을 제대로
참조하지 않거나, `auto_ik_roll` 대신 다른 경로로 pole 방향을 계산.

### Preview `_pole` 가이드 본 접근

foot guide(heel/bank) 패턴을 그대로 따라 Preview에 pole 가이드 본을 생성하고,
Build Rig Step 4c에서 가이드 위치를 `c_leg_pole`에 직접 적용하는 설계.

**세부 설계는 완료**했으나 구현 전 보류:

- `compute_geometric_pole` 복원 (commit `15bd4e3` 기반, `pole_distance` 0.5 → 0.35)
- `_create_pole_guides_for_role` 함수 (`arp_foot_guides.py`에 추가)
- CreatePreview + SetRole 양쪽에서 가이드 자동 생성
- Step 4c를 "가이드 우선 → 소스 pole → match_to_rig 기본값" 순서로 재작성
- `_detect_guide_kind` 확장 + foot 로직 조건 좁히기 (`guide_kind in ("heel","bank")`)
- `TestGeometricPole` 테스트 복원

## 검토한 저장소 옵션 (모두 risk)

| # | 옵션 | Preview 삭제 후 | 주요 risk |
|---|------|----------------|-----------|
| A | Preview `_pole` 가이드 본만 | 커스터마이제이션 손실 | Preview 의존 강함, 최종 deliverable에서 Preview 제거 시 문제 |
| B | ARP 아마추어 JSON 커스텀 프로퍼티 | 유지됨 | UI가 간접적 — 사용자가 `c_leg_pole` 직접 편집 후 "Save Pole" 오퍼레이터 필요, 편집 경로 혼동 가능 |
| C | 하이브리드 (Preview guide + ARP backup JSON) | 유지됨 | 로직 복잡, Preview↔ARP 동기화 버그 여지 |
| D | Source armature에 JSON | Source 필요 | 사용자가 Source를 직접 편집하는 경우가 드물어 접근성 낮음 |

**사용자 판단 (2026-04-10)**: "전부 위험해 보인다. 일단 넘어갈게."

## 워크플로 맥락

사용자 확인 사항:

- Preview armature는 **Build Rig 후 삭제 가능**한 중간 산출물로 간주
- 최종 deliverable은 ARP 리그 + 원본 메시
- 리빌드가 필요하면 Source에서 다시 변환

이 워크플로에서 Option A(Preview guide)는 "Build Rig 한 번으로 끝나는" 경우에는
문제없지만, pole 위치 수정이 필요하면 Preview를 다시 복원해야 함 → 실질적
아키텍처 불일치.

## 재검토 트리거

다음 조건 중 하나 이상 만족 시 재검토:

- 사용자가 pole vector 문제로 다시 리포트
- 신규 사족보행 변환에서 앞다리 pole이 몸통 관통하는 사례 2건 이상 누적
- ARP 업데이트에 pole vector 제어 API 개선 (release notes 확인 필요)
- F-series 리타게팅 재설계 (2026-04-02 이후 예정)와 함께 아키텍처 재정립 시
- 사용자가 Preview lifecycle을 재정의할 때 (Build Rig 후 삭제 가능 여부 등)

## 관련 파일 (재검토 시 참조)

- `scripts/arp_ops_build.py` (1a19ebd 기준)
  - Step 3.5 실패 코드는 reflog `5f9ac5e`에만 존재 (current master에는 없음)
  - Step 4c 기존 로직: `find_pole_vectors` 기반 pole vector 매칭
  - custom bone 필터: `GUIDE_SUFFIX_HEEL/BANK` 제외 로직
- `scripts/arp_foot_guides.py` — foot guide(heel/bank) 패턴 (pole guide 설계 시 기준)
- `scripts/skeleton_detection.py`
  - `compute_geometric_pole`은 commit `9899da4`에서 revert됨
  - 이전 구현은 `git show 15bd4e3:scripts/skeleton_detection.py`
- `tests/test_skeleton_analyzer.py`
  - `TestGeometricPole` 클래스도 `9899da4`에서 제거됨

## 커밋 히스토리 (참조)

- `15bd4e3` — feat(pole): IK pole vector 기하학 기반 자동 계산 + 소스 pole 검증
- `66c1a78` — fix(pole): collinear 임계값 2%→15% 보정
- `9899da4` — revert(pole): IK pole vector 기하학 자동 계산 되돌림
  (사유: "pole 위치 결과가 이상하여 재검토 필요")

## 재검토 시 첫 단계 제안

1. ARP 최신 버전에서 pole vector 제어 API 확인
2. `leg_auto_ik_roll=0`이 앞다리 `thigh_ref_dupli_001`에서 왜 무시되는지
   ARP 내부 소스 추적 (bl_ext.user_default.auto_rig_pro.src.auto_rig)
3. 사용자가 수동 편집한 `c_leg_pole` 위치가 어느 시점에 초기화되는지 추적
4. 저장소 옵션을 Preview lifecycle 결정 후 재평가 (Preview 유지 / 삭제 선택 따라)

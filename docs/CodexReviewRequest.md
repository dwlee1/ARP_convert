# 코드 리뷰 및 구현 방향 검토 요청

## 프로젝트 개요

동물 캐릭터 리그를 Auto-Rig Pro(ARP) `dog` 프리셋 기반으로 통일하고, 리그 생성과 애니메이션 리타게팅을 자동화하는 Blender 애드온 프로젝트.

## 기준 문서

- `docs/ProjectPlan.md` — 통합 기준 문서 (구현 상태, 검증 체크리스트, 남은 기능)
- `CLAUDE.md` — 프로젝트 규칙 및 현재 상태 요약

## 핵심 파일

- `scripts/skeleton_analyzer.py` — 구조 분석, 역할 추론, Preview 생성, `.bmap` 생성
- `scripts/arp_convert_addon.py` — Blender UI, BuildRig, Retarget 오퍼레이터

## 검토 요청 사항

### 1. 치명적 발견: 체인 매칭 방식 교체 필요

현재 `arp_convert_addon.py`의 BuildRig Step 3에서 소스와 ARP의 체인 개수가 다를 때 `edit_bones.new()`로 ARP ref 본을 직접 추가/제거하고 있음 (line ~1057-1117의 `_ADJUSTABLE_CHAINS` 블록).

**Blender에서 테스트한 결과, 이 방식은 동작하지 않음:**
- `edit_bones.new()`로 추가한 ref 본을 ARP `match_to_rig`가 무시함
- `bpy.ops.arp.show_limb_params('EXEC_DEFAULT', spine_count=5)` 호출도 실효 없음 (`invoke()`를 건너뛰어 `limb_type`이 설정되지 않음)

**검증된 해결 방법:**
ARP 내부 함수를 직접 호출하면 정상 동작함:

```python
from bl_ext.user_default.auto_rig_pro.src.auto_rig import set_spine, set_neck, set_tail, set_ears

# 각 함수는 해당 ref 본이 선택된 Edit Mode에서 호출
set_spine(count=5)      # spine ref 본 선택 필요
set_neck(neck_count=2)  # neck ref 본 선택 필요
set_tail(tail_count=6)  # tail ref 본 선택 필요
set_ears(ears_amount=3, side_arg='.l')  # L/R 개별 호출
```

- `set_spine(count=5)` 실행 시 ref/ctrl/deform 본 5개 정상 생성 확인됨
- 호출 후 ref 본 위치 수동 수정 가능 확인됨

**새 BuildRig 흐름:**

```
append_arp('dog')
→ set_spine/set_neck/set_tail/set_ears (소스 체인 개수에 맞춤)
→ ref 본 위치 설정 (소스 본 위치 복사)
→ match_to_rig
```

### 2. 연관 영향 — 컨트롤러 이름 추측 제거

`skeleton_analyzer.py`의 `_dynamic_ctrl_names()`와 `_dynamic_ref_names()`는 ARP 컨트롤러/ref 이름을 패턴으로 추측하고 있음. ARP 네이티브 함수로 교체하면 ARP가 직접 생성한 이름을 탐색할 수 있으므로 추측이 불필요해짐.

### 3. 검토해야 할 코드 영역

| 파일 | 위치 | 내용 |
|------|------|------|
| `arp_convert_addon.py` | line ~1033-1119 | `_ADJUSTABLE_CHAINS` + `edit_bones.new()`/`remove()` — 제거 대상 |
| `arp_convert_addon.py` | line ~1121-1147 | 매핑 생성 — set_* 호출 후 ref 이름 재탐색 필요 |
| `skeleton_analyzer.py` | line ~866-921 | `_dynamic_ref_names()`, `_dynamic_ctrl_names()` — 교체 또는 제거 대상 |
| `skeleton_analyzer.py` | line ~924-953 | `generate_bmap_content()` — 실제 ARP 컨트롤러 이름 사용으로 변경 |

### 4. 자동 추론 정확도

`skeleton_analyzer.py`에 최근 추가된 추론 개선:
- `trace_spine_chain()` — 후손 수 반영 스코어링
- `split_leg_foot()` — 다리/발 자동 분리
- `find_head_features()` — 구조적 귀 감지
- `analyze_skeleton()` — 멀티본 넥 감지

이 변경들은 Blender에서 실제 동물 리그로 테스트된 적이 없음. 로직의 건전성을 검토해주세요.

### 5. 질문

1. `set_spine/set_neck/set_tail/set_ears` 호출을 BuildRig에 통합할 때, 각 함수 호출 전 해당 ref 본을 자동 선택하는 가장 안정적인 방법은?
2. `_dynamic_ctrl_names()`를 제거한 후, `.bmap` 생성 시 ARP 컨트롤러 이름을 어떻게 탐색하는 것이 가장 안전한가?
3. 다중 실행 경로(`pipeline_runner.py`, `03_batch_convert.py`)에도 같은 변경을 적용해야 하는데, 코드 중복을 최소화하는 구조는?
4. 자동 추론 로직에서 명백한 엣지 케이스 버그가 보이는가?

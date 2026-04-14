# Controller Auto-Size v2: 체형 기반 균일 절대 크기

Date: 2026-04-14
Branch: feat/controller-auto-size-impl (worktree)

---

## 문제

### 기술적 제약

- ARP 컨트롤러는 `use_custom_shape_bone_size = True` — `custom_shape_scale_xyz`가 본 길이의 배수로 작동
- `match_to_rig` 이후 ARP ctrl 본 길이 = preview 본 길이 (항상 동일)
- 따라서 `scale = preview_len / ctrl_len = 1.0` → 균일 크기 불가능

### 기존 구현의 실패

- v1 비율 방식: ratio = 1.0 → max clamp 0.6으로 모두 잘림 → 구버전과 동일
- 구버전 (체인 합계 × multiplier): head 컨트롤러가 동물 크기에 비례해 지나치게 커짐
- 두 방식 모두 scale = 0.6 (max clamp)로 수렴

---

## 설계 목표

1. 모든 컨트롤러를 **동일한 절대 크기**로 통일
2. 동물 스케일에 자동 적응 (여우 ≠ 사슴)
3. 조정 가능한 상수가 **하나** (BODY_FRACTION)
4. 역할별 magic multiplier 없음

---

## 핵심 공식

```
body_ref  = Σ preview_bone_length(spine 역할 본들)
target    = body_ref × BODY_FRACTION        # 기본값: 0.10
scale     = target / arp_ctrl_bone_length
```

### 예시 (현재 테스트 동물, spine_total ≈ 0.78m)

| 컨트롤러 | ctrl 본 길이 | scale | 실제 표시 크기 |
|---------|------------|-------|-------------|
| c_head.x | 0.67m | 0.117 | ~7.8cm |
| c_spine_01.x | 0.39m | 0.203 | ~7.8cm |
| c_neck.x | 0.10m | 0.755 | ~7.5cm |
| c_ear_01.l | 0.23m | 0.339 | ~7.8cm |
| c_foot_fk.l | ~0.37m | ~0.21 | ~7.8cm |
| c_foot_ik.l | ~0.37m | ~0.21 | ~7.8cm |

IK 컨트롤러는 특별 취급 없이 동일 공식 적용.

---

## 구현 변경 사항

### `scripts/arp_build_helpers.py`

**상수 변경:**
```python
BODY_FRACTION = 0.10    # 추가: spine 대비 컨트롤러 크기 비율
AUTO_SIZE_MIN = 0.05    # 유지
AUTO_SIZE_MAX = 2.0     # 0.6 → 2.0 (neck 등 짧은 본도 허용)
AUTO_SIZE_FALLBACK = 0.12  # 유지
```

**추가 함수:**
```python
def _compute_body_reference(roles, preview_positions):
    """spine 체인 전체 길이를 body scale reference로 반환.

    spine이 없으면 할당된 모든 preview 본의 평균 길이 사용.
    Returns: float (> 0)
    """
```

**변경 함수:**
```python
def _build_controller_size_targets_per_bone(roles, ctrl_map, preview_positions, arp_bone_lengths):
    """
    body_ref = _compute_body_reference(roles, preview_positions)
    target   = body_ref × BODY_FRACTION
    scale    = target / arp_ctrl_bone_length  (없으면 target 직접)
    """
```

인터페이스(함수 시그니처) 변경 없음.

### `scripts/arp_ops_build.py`

변경 없음. 호출 코드 그대로 유지.

### `tests/test_controller_auto_size.py`

- `test_per_bone_ratio_scale()` → `test_body_reference_uniform_size()` 교체
  - spine_total 기반 target이 모든 컨트롤러에 동일하게 적용되는지 검증
- `test_per_bone_index_pairing()` 제거 (더 이상 인덱스 페어링 없음)
- `test_ik_ctrl_uses_first_preview_bone()` 제거 (IK 특별 취급 없음)
- `test_fallback_when_no_arp_length()` 유지 (target 직접 사용 fallback)
- `test_fallback_when_no_spine_role()` 추가 (spine 없을 때 평균 fallback)
- `test_clamp_enforces_bounds()` 유지

---

## Fallback 처리

| 상황 | 처리 |
|------|------|
| spine 역할 본 없음 | 할당된 모든 preview 본의 평균 길이를 body_ref로 사용 |
| 할당된 본 아예 없음 | AUTO_SIZE_FALLBACK (0.12) |
| ctrl 본 길이 없음 | target을 scale로 직접 사용 (world unit) |

---

## 검증

```bash
pytest tests/ -v
ruff check scripts/ tests/
```

Blender 수동 확인:
1. fox Build Rig → 모든 컨트롤러 크기가 비슷한지
2. deer/raccoon Build Rig → 동물 스케일 따라 자동 조정되는지
3. Build Rig 재실행 시 크기 재적용되는지
4. BODY_FRACTION을 0.08 / 0.12로 바꿔 반응 확인

---

## 향후 고려 (이번 범위 외)

- BODY_FRACTION을 UI 패널에서 노출 (사용자 튜닝)
- 역할별 micro-correction (현재 설계에서 의도적으로 제외)

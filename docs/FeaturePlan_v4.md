# Feature Plan v4 — 리그 변환 품질 개선

최종 수정: 2026-03-25

> 이 문서는 4개 신규 기능의 설계·구현 계획을 정리한다.
> 전체 프로젝트 상태는 `docs/ProjectPlan.md` 참조.

---

## 기능 목록

| # | 기능 | 우선순위 | 난이도 | 상태 |
|---|------|----------|--------|------|
| F1 | 웨이트 0 본 프리뷰 제외 | 1 | 낮음 | 완료 |
| F2 | IK pole vector 위치 매칭 | 2 | 중간 | 완료 |
| F3 | Shape key 드라이버 보존 | 3 | 높음 | 완료 |
| F4 | 리타게팅 IK 모드 | 4 | 높음 | 완료 |

---

## F1. 웨이트 0 본 프리뷰 제외

### 문제

- deform 체크가 되어 있지만 실제 메시에 웨이트가 없는 본(예: 폴 벡터, 보조 본)이 프리뷰에 포함됨
- Cat의 `Foot_Fpole_L/R`, `Foot_Bpole_L/R`, `DU_*` 본이 대표적 사례

### 구현

1. **메시 vertex group 스캔**: 각 vertex group의 최대 웨이트 계산
2. **필터링**: 최대 웨이트 < 임계값(0.001)인 본은 deform 본에서 제외
3. **적용 위치**: `skeleton_analyzer.py`의 `extract_bone_data()` 또는 호출부

```python
# 의사 코드
def get_weighted_bones(mesh_obj):
    """메시에서 실제 웨이트가 있는 vertex group 이름 집합 반환."""
    weighted = set()
    for v in mesh_obj.data.vertices:
        for g in v.groups:
            if g.weight > 0.001:
                vg = mesh_obj.vertex_groups[g.group]
                weighted.add(vg.name)
    return weighted
```

### 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/skeleton_analyzer.py` | `extract_bone_data()`에 mesh_obj 파라미터 추가, 웨이트 필터링 |
| `scripts/arp_convert_addon.py` | 호출부에서 mesh_obj 전달 |
| `scripts/extract_test_fixture.py` | fixture에 `has_weight` 정보 추가 |
| `tests/test_skeleton_analyzer.py` | 웨이트 0 본 제외 테스트 추가 |

### 완료 조건

- [x] 웨이트 0인 deform 본이 프리뷰에 포함되지 않음
- [x] 웨이트가 있는 deform 본은 정상적으로 포함됨
- [x] 기존 deer/cat fixture 테스트 통과
- [x] pytest 전체 통과

---

## F2. IK Pole Vector 위치 매칭

### 문제

- ARP 리그 빌드 시 pole target 본이 기본 위치에 생성됨
- 소스 리그의 폴 벡터 본 위치와 불일치 → IK 방향이 달라짐

### 구현

1. **소스 pole 본 탐색**: non-deform 본 포함 전체 본에서 pole/knee/elbow 패턴 탐색
   - 이름 패턴: `*pole*`, `*knee*`, `*elbow*`
   - 위치 기반: 다리 체인 평면에서 수직 방향으로 떨어진 본
2. **ARP pole target 이동**: 빌드 후 `c_pole_ik.*` 본 위치를 소스 값으로 설정

### 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/skeleton_analyzer.py` | non-deform 본에서 pole 본 탐색 함수 추가 |
| `scripts/arp_convert_addon.py` | BuildRig 후 pole target 위치 반영 |

### 완료 조건

- [x] 소스 리그에 pole 본이 있으면 ARP pole target이 같은 위치로 이동
- [x] pole 본이 없는 리그에서는 ARP 기본 위치 유지
- [x] Fox/Cat 모두 정상 동작 (Blender 테스트 완료)

---

## F3. Shape Key 드라이버 보존

### 문제

- 소스 메시에 shape key가 있고, 드라이버로 본에 연결된 경우
- ARP 변환 시 원본 본이 사라져 드라이버가 깨짐

### 지원 드라이버 타입

1. **Transform 기반**: 본의 위치/회전/스케일 → shape key value
2. **커스텀 프로퍼티 기반**: 본의 custom property → shape key value

### 구현

1. **드라이버 스캔**: `mesh.data.shape_keys.animation_data.drivers` 파싱
2. **컨트롤러 본 식별**: driver variable의 target bone 추출
3. **cc_ 커스텀 본 등록**: 컨트롤러 본을 cc_ 본으로 생성 (위치/형태 유지)
4. **드라이버 리맵**: data_path를 새 cc_ 본으로 변경

```python
# 의사 코드
def scan_shape_key_drivers(mesh_obj):
    """shape key 드라이버에서 컨트롤러 본 정보 추출."""
    drivers_info = []
    for driver in mesh_obj.data.shape_keys.animation_data.drivers:
        for var in driver.driver.variables:
            if var.type == 'TRANSFORMS':
                bone_name = var.targets[0].bone_target
                transform_type = var.targets[0].transform_type
            elif var.type == 'SINGLE_PROP':
                # custom property path 파싱
                ...
            drivers_info.append({...})
    return drivers_info
```

### 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/skeleton_analyzer.py` | shape key 드라이버 스캔 함수 추가 |
| `scripts/arp_convert_addon.py` | cc_ 본 등록 + 드라이버 리맵 로직 |

### 완료 조건

- [x] transform 기반 드라이버 보존
- [x] 커스텀 프로퍼티 기반 드라이버 보존
- [x] shape key가 없는 메시에서 에러 없음
- [ ] Cat에서 실제 shape key 동작 확인 (Blender 테스트 필요)

---

## F4. 리타게팅 IK 모드

### 문제

- 현재 리타게팅은 FK(본 회전) 기반 → 발 슬라이딩, 바닥 접지 불안정
- 사족 동물은 IK 기반이 더 자연스러운 결과

### 구현

1. **소스 발/손 위치 추출**: 매 프레임 world space 위치 베이크
2. **IK 컨트롤러에 키프레임**: `c_foot_ik.*`, `c_hand_ik.*` 등 ARP IK 본에 loc 키프레임
3. **폴 벡터 위치 계산**: 무릎/팔꿈치 위치에서 폴 벡터 방향 계산, 프레임별 적용
4. **FK/IK 전환**: ARP의 `ik_fk_switch` 프로퍼티를 IK 모드로 설정

### 변경 파일

| 파일 | 변경 |
|------|------|
| `scripts/arp_convert_addon.py` | 리타게팅 오퍼레이터에 IK 모드 옵션 추가 |
| `scripts/arp_utils.py` | FK→IK 변환 유틸 함수 |

### 완료 조건

- [ ] IK 모드로 리타게팅 시 발 슬라이딩 감소 (Blender 테스트 필요)
- [x] FK 모드도 기존대로 동작 (후방 호환 — 기본값 off)
- [ ] 걷기/달리기 애니메이션에서 정상 동작 확인 (Blender 테스트 필요)

---

## 구현 순서

```
F1 (웨이트 필터링) → F2 (pole vector) → F3 (shape key) → F4 (IK 리타게팅)
```

F1은 분석 정확도에 영향을 주므로 가장 먼저 구현.
F2는 리그 빌드 단계에서 독립적으로 적용 가능.
F3, F4는 범위가 크므로 별도 브랜치에서 작업 권장.

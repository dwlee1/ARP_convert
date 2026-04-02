# 리타게팅 코드 전면 삭제 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Rig (Step 3) 이후의 모든 리타게팅 코드를 삭제하여 깨끗한 상태를 만든다.

**Architecture:** 4개 파일(arp_convert_addon.py, arp_utils.py, skeleton_analyzer.py, pipeline_runner.py)에서 리타게팅 관련 코드를 제거. Build Rig까지의 기능은 그대로 유지. 테스트 중 bmap 관련 테스트도 삭제.

**Tech Stack:** Python, Blender API (bpy)

---

## 파일 구조 변경 요약

| 파일 | 변경 | 설명 |
|------|------|------|
| `scripts/arp_convert_addon.py` | 수정 | Step 3.5/4 오퍼레이터, UIList, UI, Props, 등록 제거 |
| `scripts/arp_utils.py` | 수정 | retarget/clean source/bmap 관련 함수 전체 제거 |
| `scripts/skeleton_analyzer.py` | 수정 | `generate_bmap_content`, `populate_bone_map` 제거 |
| `scripts/pipeline_runner.py` | 수정 | Step 2/3 (retarget) 전체 제거, Build Rig까지만 유지 |
| `tests/test_custom_bone_hierarchy.py` | 수정 | `test_generate_bmap_content_*` 테스트 제거 |

---

### Task 1: arp_utils.py — 리타게팅 관련 함수 전체 삭제

**Files:**
- Modify: `scripts/arp_utils.py`

이 파일에서 제거할 대상:

**상수/클래스 (파일 상단):**
- `CLEAN_SOURCE_ACTION_NAMES_PROP` (line 16)
- `CLEAN_SOURCE_MODE_PROP` (line 17)
- `CLEAN_SOURCE_ACTION_PROP` (line 18)
- `_OBJECT_TRANSFORM_PATHS` (lines 19-25)
- `_POSE_TRANSFORM_PATH_RE` (lines 26-28)
- `_POSE_CUSTOM_PROP_PATH_RE` (lines 29-31)
- `_POSE_CONSTRAINT_INFLUENCE_PATH_RE` (lines 32-34)
- `_MISSING` (line 35)
- `class CleanSourceCloneError` (lines 43-49)

**함수:**
- `ensure_retarget_context()` (lines 126-136)
- `install_bmap_preset()` (lines 139-199)
- `export_clean_fbx()` (lines 252-287)
- `import_clean_fbx()` (lines 290-317)
- `_ensure_action_slot()` (lines 320-341)
- `_eval_fcurve()` (lines 344-349)
- `_read_pose_basis()` (lines 352-391)
- `_compute_world_matrices_from_fcurves()` (lines 394-469)
- `normalize_clean_hierarchy()` (lines 472-640)
- `_classify_fcurve_data_path()` (lines 643-676)
- `_sanitize_clone_hierarchy()` (lines 679-746)
- `_extract_clone_bone_settings()` (lines 749-761)
- `_apply_clone_bone_settings()` (lines 764-777)
- `_collect_actions()` (lines 780-796)
- `get_clean_source_actions()` (lines 799-821)
- `_norm_fc_insert()` (lines 824-830)
- `_capture_animation_state()` (lines 833-874)
- `_restore_animation_state()` (lines 877-913)
- `_build_action_bindings()` (lines 916-966)
- `_apply_action_bindings()` (lines 969-993)
- `_store_clean_source_metadata()` (lines 996-1003)
- `_matrix_max_delta()` (lines 1006-1008)
- `_collect_sample_frames()` (lines 1011-1014)
- `_key_clean_object_transforms()` (lines 1017-1032)
- `_key_clean_pose_bone()` (lines 1035-1048)
- `_pose_basis_from_target_matrix()` (lines 1051-1057)
- `_key_clean_pose_basis()` (lines 1060-1075)
- `_validate_clone_action()` (lines 1077-1121)
- `bake_source_to_clean_clone()` (lines 1124-1268)
- `create_clean_source_clone()` (lines 1271-1343)
- `_create_clean_source_fbx_fallback()` (lines 1346-1371)
- `create_clean_source()` (lines 1374-1398)
- `cleanup_clean_source()` (lines 1401-1420)

**유지 대상:**
- `log()`, `ensure_object_mode()`, `select_only()`, `get_3d_viewport_context()`, `run_arp_operator()`
- `find_arp_armature()`, `find_source_armature()`, `find_mesh_objects()`
- `load_mapping_profile()`, `resolve_project_root()`
- `_PROJECT_RESOURCE_DIRS`

- [ ] **Step 1: 상수/클래스 삭제** — lines 16-35의 상수, line 43-49의 CleanSourceCloneError 삭제
- [ ] **Step 2: ensure_retarget_context ~ import_clean_fbx 삭제** — lines 126-317
- [ ] **Step 3: _ensure_action_slot ~ cleanup_clean_source 삭제** — lines 320-1420 (export_clean_fbx 이후 ~ load_mapping_profile 이전 전체)
- [ ] **Step 4: 사용하지 않는 import 정리** — `re`, `shutil`, `json` 등 삭제 함수에서만 쓰던 임포트 제거 (json은 load_mapping_profile에서 사용하므로 유지)
- [ ] **Step 5: docstring 업데이트** — 파일 상단 docstring에서 `02_retarget_animation.py` 참조 제거

---

### Task 2: arp_convert_addon.py — Step 3.5/4 오퍼레이터, UIList, UI, Props 삭제

**Files:**
- Modify: `scripts/arp_convert_addon.py`

제거 대상:

**Props (ARPCONV_Props 내):**
- `clean_source_armature` (line 967)
- `clean_source_mode` (line 968)
- `clean_fbx_path` (line 969)
- `regression_run_retarget` (lines 982-985)
- `retarget_ik_mode` (lines 993-997)

**오퍼레이터/UIList:**
- `ARPCONV_OT_RemapSetup` 클래스 전체 (lines 2792-2953)
- `_find_arp_armature_cached()` 함수 (lines 2961-2969)
- `ARPCONV_UL_BoneMap` 클래스 전체 (lines 2972-3001)
- `ARPCONV_OT_Retarget` 클래스 전체 (lines 3003-3109)

**UI 패널 (ARPCONV_PT_MainPanel.draw):**
- Step 3.5 박스 전체 (lines 3424-3502)
- Step 4 박스 전체 (lines 3504-3510)
- Regression 박스에서 `regression_run_retarget` prop 줄 삭제 (line 3517)

**회귀 테스트 오퍼레이터 (ARPCONV_OT_RunRegression):**
- `retarget` 관련 report 필드 (line 3149)
- Remap/Retarget 호출 블록 (lines 3194-3203) 삭제
- report["retarget"] 참조 정리

**등록 (classes 리스트):**
- `ARPCONV_OT_RemapSetup` 제거 (line 3535)
- `ARPCONV_UL_BoneMap` 제거 (line 3536)
- `ARPCONV_OT_Retarget` 제거 (line 3537)

- [ ] **Step 1: Props 삭제** — ARPCONV_Props에서 clean_source_armature, clean_source_mode, clean_fbx_path, regression_run_retarget, retarget_ik_mode 제거
- [ ] **Step 2: Step 3.5/4 오퍼레이터 삭제** — RemapSetup, _find_arp_armature_cached, ARPCONV_UL_BoneMap, Retarget 클래스 전체 + 관련 섹션 주석 제거
- [ ] **Step 3: UI 패널 삭제** — Step 3.5 박스, Step 4 박스, regression_run_retarget prop 줄 삭제
- [ ] **Step 4: 회귀 오퍼레이터 정리** — retarget 관련 report 필드, Remap/Retarget 호출 블록, should_run_retarget 로직 제거
- [ ] **Step 5: 등록 리스트 정리** — classes[]에서 3개 클래스 제거
- [ ] **Step 6: 사용하지 않는 import 정리** — UIList import 등

---

### Task 3: skeleton_analyzer.py — bmap 생성 함수 삭제

**Files:**
- Modify: `scripts/skeleton_analyzer.py`

제거 대상:
- `generate_bmap_content()` (lines 1759-1837)
- `populate_bone_map()` (lines 1840-1928)

유지 대상 (Build Rig에서 사용):
- `map_role_chain()`, `discover_arp_ctrl_map()`, `_dynamic_ctrl_names()`, `ARP_CTRL_MAP`, `_apply_ik_to_foot_ctrl()` — 이 함수들은 bmap 뿐만 아니라 generate_arp_mapping에서도 사용

- [ ] **Step 1: generate_bmap_content 삭제** — lines 1759-1837
- [ ] **Step 2: populate_bone_map 삭제** — lines 1840-1928

---

### Task 4: pipeline_runner.py — retarget 단계 제거

**Files:**
- Modify: `scripts/pipeline_runner.py`

Build Rig (Step 1: match_to_rig까지)는 유지. Step 2 (retarget 설정), Step 3 (액션별 retarget) 전체 삭제.

- [ ] **Step 1: ConversionResult에서 retarget_stats 제거** — line 109, save()의 해당 필드
- [ ] **Step 2: Step 2 + Step 3 전체 삭제** — lines 347-505 (retarget 설정 + 실행 + clean source 정리)
- [ ] **Step 3: main() 하단 정리** — retarget 결과 출력 줄 제거, success 판정 기준 단순화
- [ ] **Step 4: 사용하지 않는 import 정리**

---

### Task 5: 테스트 정리

**Files:**
- Modify: `tests/test_custom_bone_hierarchy.py`

- [ ] **Step 1: test_generate_bmap_content_orders_unmapped_by_hierarchy 삭제** — lines 16-39

---

### Task 6: 검증 + 커밋

- [ ] **Step 1: pytest 실행**

```bash
pytest tests/ -v
```

Expected: 기존 테스트 중 retarget 관련 삭제 후 나머지 모두 PASS

- [ ] **Step 2: Python syntax 검증**

```bash
python -c "import ast; ast.parse(open('scripts/arp_convert_addon.py').read()); print('addon OK')"
python -c "import ast; ast.parse(open('scripts/arp_utils.py').read()); print('utils OK')"
python -c "import ast; ast.parse(open('scripts/skeleton_analyzer.py').read()); print('analyzer OK')"
python -c "import ast; ast.parse(open('scripts/pipeline_runner.py').read()); print('runner OK')"
```

- [ ] **Step 3: 커밋**

```bash
git add scripts/arp_convert_addon.py scripts/arp_utils.py scripts/skeleton_analyzer.py scripts/pipeline_runner.py tests/test_custom_bone_hierarchy.py
git commit -m "refactor: 리타게팅 코드 전면 삭제 — Build Rig까지만 유지, 리타게팅 재설계 준비"
```

---

## 삭제 후 남는 구조

```text
Addon 경로 (삭제 후)
1. 소스 deform 본 분석 (웨이트 0 본 필터링 + 제외 본 부모 관계 포함)
2. Preview Armature 생성 + Source Hierarchy 트리
3. 역할 수정 (Source Hierarchy 트리에서 본 클릭 → 선택 → 역할 변경)
4. ARP 리그 생성 (append_arp → set_spine/neck/tail/ears → ref 정렬 → match_to_rig)
5. 앞다리 3 Bones IK 값 설정 + IK pole vector 위치 매칭
6. cc_ 커스텀 본 추가 (shape key 드라이버 컨트롤러 포함)
7. 전체 웨이트 전송 (deform + cc_ → ARP)
8. Shape key 드라이버 리맵
(여기까지 — 리타게팅은 추후 새로 설계)
```

```text
비대화형 경로 (삭제 후)
pipeline_runner.py: 소스 분석 → ARP 리그 생성 → ref 정렬 → match_to_rig (리타게팅 없음)
```

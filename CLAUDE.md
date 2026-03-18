# BlenderRigConvert

## 프로젝트 목표
게임/애니메이션용 동물 캐릭터의 리깅 방식을 **AutoRig Pro(ARP)**로 통일하는 프로젝트.
- 파일마다 다른 리깅 방식 → ARP 하나로 표준화
- 익스포트 방식도 통일하여 작업 효율 향상
- 현재 절반 이상 ARP 적용 완료, 나머지 변환 진행 중

## 환경
- **Blender 4.5 LTS**
- **AutoRig Pro** 애드온

## 디렉토리 구조
```
BlenderRigConvert/
├── Asset/                    # 작업 에셋 (블렌더 + 유니티)
│   ├── BlenderFile/          # Blender 프로젝트 파일 (.blend)
│   │   ├── 2024/             # 2024 이벤트별 (Cherry Blossom, Summer, Christmas 등)
│   │   ├── 2025/             # 2025 이벤트별 (Valentine, Easter, Summer 등)
│   │   ├── 2026/             # 2026 이벤트별 (Australia, Cat Challenge 등)
│   │   ├── Sup_01/           # 보충 1 (Crane, Monkey, Boar, Panda, Tiger, Frog 등)
│   │   ├── Sup_02/           # 보충 2 (Husky, Lynx, Moose, Penguin, Snow Leopard 등)
│   │   ├── bird/             # 조류 (Albatross, Eagle, Pelican 등)
│   │   ├── normal/           # 육상 동물 (Cat, Fox, Bear, Wolf 등)
│   │   ├── sea/              # 해양 동물 (Dolphin, Orca, Seal 등)
│   │   ├── Effect/           # 이펙트
│   │   └── etc/              # 기타
│   └── UnityFBX/             # Unity용 FBX 익스포트 파일
│       └── 02. Animals/      # 동물 FBX 에셋
├── docs/                     # 프로젝트 문서
├── blend_files_report.csv    # .blend 파일 현황 리포트
├── scan_blend_files.py       # 스캔 유틸리티
└── cleanup_blend1.py         # 백업 파일 정리 유틸리티
```

## 파일 형식
- `.blend` — Blender 프로젝트 (1,065개)
- `.fbx` — 게임 엔진 익스포트 (555개)
- `.png/.jpg` — 텍스처
- `.psd` — 컨셉아트
- `.spp` — Substance Painter

## 파일 명명 규칙
- 숫자 접두사: `3082_duck`, `3089_guineapig`
- 날짜 접미사 (YYMMDD): `_240311`, `_250115`
- 리그 파일: `_rig`, `_rig2`
- 애니메이션: `_AllAni`, `_animation`, `_Ani_`
- 모델링: `_Modeling`
- 버전: `_ex`, `_01`, `_02`

## 유틸리티 스크립트

### scan_blend_files.py
전체 .blend 파일 현황을 CSV로 생성.
```bash
python scan_blend_files.py
```
→ `blend_files_report.csv` 출력 (동물명, 경로, 날짜, 크기, 중복 상태)

### cleanup_blend1.py
Blender 자동 백업(.blend1) 파일 삭제.
```bash
python cleanup_blend1.py        # 확인 후 삭제
python cleanup_blend1.py --yes  # 바로 삭제
```

## 코드 컨벤션
- Python: snake_case 함수명, UPPERCASE 상수
- 주석/문서: 한국어
- 외부 의존성 없이 Python 표준 라이브러리만 사용

## 자동 변환 스크립트 현황

### 파이프라인 (`scripts/rigify_to_arp.py`)
커스텀 리그 → ARP(AutoRig Pro) 자동 변환 스크립트. Blender Scripting 탭에서 실행.

```
Step 1: 소스 아마추어 식별 (커스텀 본 이름 매핑)
Step 2: 변환 전 상태 기록
Step 3: ARP 리그 추가 (dog 프리셋)
Step 4: ARP 리그 생성 (match_to_rig)
Step 4.5: IK→FK 전환 시도
Step 5: Remap 애니메이션 리타게팅 (액션별 개별 처리)
Step 6: FBX 익스포트 (비활성화, ARP GUI에서 수동)
```

### 테스트 결과 (Fox - fox_AllAni_240311.blend)
- ✅ ARP dog 프리셋 리그 생성 성공
- ✅ 17/17 액션 리타게팅 성공 (custom_quadruped.bmap 사용)
- ✅ .bmap 본 매핑 로드 성공
- ✅ FBX 익스포트 성공 (Blender 기본 익스포터)
- ⚠️ 뒷다리(FK) 애니메이션 동작 확인, 앞다리 IK→FK 전환 미해결
- ❌ 본 위치가 메시와 안 맞음 (레퍼런스 본 위치 조정 미구현)

### 미해결 이슈 (다음 세션)
1. **ARP IK/FK 스위치**: 커스텀 프로퍼티 이름을 정확히 파악 필요. Blender에서 ARP 리그의 hand/foot 관련 pose bone의 커스텀 프로퍼티를 확인해야 함
2. **레퍼런스 본 위치 조정**: `import_rig_data` 또는 직접 edit_bones 이동으로 ARP 레퍼런스 본을 소스 메시에 맞게 배치해야 함. Step 3 후 Step 4 전에 수행
3. **메시 바인딩 품질**: 본 위치 수정 후 `bind_to_rig` 재테스트 필요

### 주요 스크립트
| 파일 | 용도 |
|------|------|
| `scripts/rigify_to_arp.py` | 메인 변환 스크립트 (PoC) |
| `scripts/diagnose_arp_operators.py` | ARP 오퍼레이터 파라미터 조사 |
| `scripts/inspect_rig.py` | 리그 구조 조사 유틸리티 |
| `scripts/bone_mapping.py` | Rigify↔ARP 본 매핑 테이블 |
| `scripts/arp_retarget_reference.py` | ARP 리타게팅 워크플로우 레퍼런스 |
| `remap_presets/custom_quadruped.bmap` | Fox 커스텀 리그용 본 매핑 프리셋 |

### 기존 리그 특징 (fox 기준)
- **순수 Rigify 아님** — 완전 커스텀 리그 (DEF- 접두사 없음)
- 본 이름: `thigh_L`, `leg_L`, `shoulder_L`, `upperarm_L` 등
- IK 컨트롤러: `L_foot_IK`, `Lhand_IK` 등 (별도 본)
- 특수 본: `ear01_L/R`, `eye_L/R`, `tail_01~04`, `jaw`
- 액션: 17개 (walk, run, idle, jump 등)
- 메시: 11개 (Fox 컬러 바리에이션)

### ARP 프리셋 경로
- 아마추어: `C:\Users\manag\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\user_default\auto_rig_pro\armature_presets\`
- Remap: `C:\Users\manag\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\user_default\auto_rig_pro\remap_presets\`

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

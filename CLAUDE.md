# BlenderRigConvert

## 프로젝트 목표
동물 캐릭터 리깅을 **AutoRig Pro(ARP)**로 통일. 현재 절반 ARP 적용 완료, 나머지 변환 진행 중.

## 환경
- **Blender 4.5 LTS** + **AutoRig Pro** 애드온

## 디렉토리 구조
```
BlenderRigConvert/
├── Asset/BlenderFile/    # .blend 파일 (normal/, bird/, sea/, Sup_01~02/, 이벤트별)
├── Asset/UnityFBX/       # FBX 익스포트
├── scripts/              # 변환 스크립트
├── mapping_profiles/     # 본 매핑 JSON 프로필
├── remap_presets/        # ARP .bmap 프리셋
└── docs/                 # 프로젝트 문서
```

## 코드 컨벤션
- Python: snake_case 함수명, UPPERCASE 상수
- 주석/문서: 한국어
- 외부 의존성 없이 Python 표준 라이브러리만 사용

## 변환 파이프라인
```
1. 01_create_arp_rig.py   — ARP 리그 생성 (JSON 프로필 기반 본 매핑)
2. 02_retarget_animation.py — 애니메이션 리타게팅 (ARP Remap)
```

- 공유 유틸리티: `scripts/arp_utils.py`
- 매핑 프로필: `mapping_profiles/custom_quadruped.json` (Fox, Cat, Wolf 등)
- 상세 계획: `docs/ConversionPlan.md`

## 주요 규칙
- ARP dog 프리셋 앞다리는 `_dupli_001` 접미사 사용
- face rig 불필요 — ear/eye/jaw만 커스텀 본으로 처리
- JSON 프로필에 L사이드만 정의 → R사이드 자동 미러링

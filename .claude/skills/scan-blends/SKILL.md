---
name: scan-blends
description: blend 파일 현황 스캔 및 결과 요약
---

프로젝트의 모든 .blend 파일을 스캔하고 현황을 요약합니다.

1. `scan_blend_files.py` 스크립트를 실행하여 `blend_files_report.csv`를 생성합니다.
2. 생성된 CSV를 읽고 다음을 요약합니다:
   - 총 .blend 파일 수
   - 폴더별 파일 수 (2024, 2025, 2026, Sup_01, Sup_02, bird, normal, sea 등)
   - 동물별 파일 수 (중복 포함)
   - 가장 최근 수정된 파일 top 10
   - 총 용량
3. 결과를 간결한 표 형태로 사용자에게 보여줍니다.

실행 명령:
```bash
cd $PROJECT_DIR && python scan_blend_files.py
```

CSV 경로: `blend_files_report.csv`

# Blend Identity Tools

이 폴더는 기존 ARP 변환/리타게팅 개발과 분리된 보조 분석 도구입니다.

포함 파일:

- `extract_blend_identity.py`: Blender 내부에서 현재 `.blend`의 리그/액션/메시 메타데이터 추출
- `scan_blend_identity.py`: 여러 `.blend`를 순회하며 추출기를 실행하고 CSV/JSON 리포트 생성

기본 실행:

```bash
python3 tools/blend_identity/scan_blend_identity.py
```

Windows exe 빌드:

```bat
tools\blend_identity\build_exe.bat
```

또는:

```bat
py -3 tools\blend_identity\build_exe.py
```

생성 파일:

```text
tools\blend_identity\dist\blend_identity_scan.exe
```

exe 실행 시 기본 출력 위치:

- exe 옆의 `output\blend_identity_report.csv`
- exe 옆의 `output\blend_identity_report.json`

예시:

```bash
python3 tools/blend_identity/scan_blend_identity.py --filter "2024/2024_Cherry Blossom/Axolotl" --limit 2
```

스크립트 직접 실행 시 기본 출력:

- `tools/blend_identity/output/blend_identity_report.csv`
- `tools/blend_identity/output/blend_identity_report.json`

이 도구는 기존 `scripts/arp_convert_addon.py`, `scripts/pipeline_runner.py`, `scripts/03_batch_convert.py`와 직접 연결되지 않습니다.

# lab_dashboard 저장소 구조·운영

## 핵심 요약
lab_dashboard_ver0.1 (서버17 `/root/02_SGS/`, 곧 `01_MachineLearning`으로 개명 예정) 프로젝트의 폴더 구조·git 버전관리·정리 규칙. 연구 내용은 [[앙상블 Bias-Variance·튜닝]]·[[노이즈 정의·정제 파이프라인]]·[[PRISM(LAB) 데이터·진단]] 등 별도.

## 기록

### 저장소 대청소 + 01_~07_ 재편  <!-- (2026-08-13) -->
- 루트 40폴더 → 8: `01_code 02_dataset 03_json 04_logs 05_docs 06_data 07_app 99_trash_20260813`.
- 데이터(seq789·canonical) → `06_data/`, 대시보드 런타임(models/static/tools) → `07_app/`.
- `01_code` 121 → 17개 (연구핵심 4 + 러너 10 + 대시보드 3). 미사용 코드·데이터는 `99_trash_20260813/`로 이동(되돌리기 가능, 하드삭제 보류). STTabNet 폐기 산출물도 여기로.
- 유지 코드 경로 참조 일괄 갱신: 러너 `$BASE/06_data/...`, app 3파일 `BASE_DIR/07_app/...`.
- 유지 코드는 전부 상대경로(`BASE=$(pwd)`, `BASE_DIR=Path(__file__).parent.parent`). 절대경로 박은 스크립트는 전부 미사용이라 아카이브됨.
- 상세 = 프로젝트 `STRUCTURE.md`.

### git 버전관리 시작  <!-- (2026-08-13) -->
- repo: `github.com/cole0213/LightGBM_Traffic_Classification` (origin/master, push 완료).
- `.gitignore`: `06_data/ 07_app/ 04_logs/ 99_trash*/ *.db *.out *.pkl *.csv *basenames*.txt` 등 대용량·런타임 제외 → 코드·문서·결과 json만.
- `.gitattributes`: `* text=auto eol=lf` — 서버(Linux) .sh CRLF 오염 방지.
- 커밋·push는 글로벌 `/commit` 커맨드(수동 트리거). 글로벌 `~/.claude/CLAUDE.md`·`AGENTS.md`에 코드 주석 규칙 + git 규칙 상주(모든 프로젝트 공통).

### 폴더 개명 예정  <!-- (2026-08-13) -->
- `lab_dashboard_ver0.1` → `01_MachineLearning`.
- 코드가 상대경로라 **개명 시 코드 수정 0**. 이름 박힌 곳은 문서·주석뿐.
- 실행 중 LAB 튜닝 job의 작업 디렉터리라 **job 완주 후** 진행(optuna sqlite 경로·SMB open-file 충돌 회피). optuna resume 가능이라 최악도 재실행 복구.

## 다음 할 일
- [ ] LAB LightGBM 클린 튜닝 완주 후 폴더 개명 + 문서·주석 이름 일괄 갱신
- [ ] `99_trash_20260813` 무문제 확인 후 하드삭제

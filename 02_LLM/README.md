# 02_LLM — 생성형 AI 트래픽 식별 프로젝트

01_MachineLearning(트래픽 분류 본체)과 나란히 두는 **LLM 트래픽 연구** 홈.
대주제=네트워크 트래픽 분류, 소주제=생성형 AI. **핵심 주제 = L4 작업 단계 추론**
(단순질문 vs 긴 추론 vs 도구사용)을 SNI-free·per-flow로 트래픽만 보고 식별.

## 폴더 구조
```
02_LLM/
├─ 01_code/
│  └─ L4_reasoning_probe/     ← 초미니 검증 실험(추론 ON/OFF 타이밍)
│     ├─ mini_probe.py         # 같은 질문 × 추론 ON/OFF, 타이밍 측정
│     ├─ plot_probe.py         # 결과 그림(핵심=산점도)
│     ├─ setup_server.sh       # 서버 패키지 설치 + 연결 확인
│     ├─ README.md             # 실행법
│     └─ out/                  # 결과 CSV·그림
├─ 02_literature/             ← 논문 자동수집 파이프라인(구 lit/) + 코퍼스
│  ├─ tools/literature_collection/pipeline_v3.py   # 마스터 프롬프트 구현
│  ├─ config/collection.yaml   # root=/root/02_SGS/02_LLM/02_literature
│  └─ papers/                  # literature.db(498편), pdfs(다운로드), reports
├─ 05_docs/
│  └─ genai_traffic_topics.pptx  # 선배 발표용 주제후보 12장
├─ 06_data/                   ← (향후) pcap·피처 데이터
└─ 08_obsidian/               ← 지식노트는 ../_notes(볼트)에 있음, 아래 링크
```

## 지식 노트 (옵시디언 볼트 = ../_notes)
- `_notes/생성형AI 트래픽 식별.md` — 허브(주제·config·기록)
- `_notes/생성형AI 트래픽 식별 — 주제 추천·의사결정.md` — L4 추천 근거
- `_notes/생성형AI 트래픽 식별 — L4 연구 로드맵.md` — 시작 로드맵(v2, 자기비판 반영)
- `_notes/생성형AI 트래픽 식별 — baseline 문헌분석.md` — 16편 정독 분석

## 지금 단계
1. [진행] L4 초미니 검증 — 추론 ON/OFF가 출력 길이와 무관하게 타이밍에 갈리나?
   - 서버: `cd 01_code/L4_reasoning_probe && bash setup_server.sh` → 키 설정 → `python3 mini_probe.py --limit 2 --repeats 1`
2. [대기] 갈리면 → Phase 1: tcpdump 패킷 캡처 얹어 진짜 네트워크 side-channel 실험.

## 서버 실행 메모 (17서버 = 163.152.223.17, Linux)
- 경로: `/root/02_SGS/02_LLM/...` (Windows에선 `U:\root\02_SGS\02_LLM\...`).
- 패키지는 서버에서 `setup_server.sh`로 설치(내가 깐 건 Windows python쪽이라 서버엔 따로 필요).
- API 키는 `export ANTHROPIC_API_KEY=...` (자격증명, 본인이 관리).

작성일: 2026-09-01

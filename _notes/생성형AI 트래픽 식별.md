# 생성형AI 트래픽 식별

## 핵심 요약
**대주제 = 네트워크 트래픽 분류, 소주제 = 생성형 AI.** 암호화 상태에서 트래픽만으로 GenAI 상호작용을 **계층적 fine-grained 핑거프린팅**하는 연구. 상위 뿌리: [[02_SGS]]. 세미나·심층분석: [[생성형AI 트래픽 식별 — baseline 문헌분석]]. 주제 추천: [[생성형AI 트래픽 식별 — 주제 추천·의사결정]]. 실험개념: [[생성형AI 트래픽 식별 — 실험 설계·평가 개념]]. 방법론(시퀀스 표현학습·보편성 검증)은 [[STTabNet·VPN·Tor 보편분류]]·[[노이즈 정의·정제 파이프라인]]과 공유.

**★ 연구 목적 (2026-09-05 확정, 3층 구조) — 교수님 "목적 미흡" 피드백 반영.**
진단: 지금까지 **신호를 먼저 찾고 목적을 나중에 붙인** 순서(method-first)라 목적이 허했음. 그리고 "짧추/긴추 분류"는 **방법·결과지 목적이 아님**(목적은 그 위 "그걸로 뭘 아나"). 셋(프라이버시·네트워크관리·비용)을 평면 나열하면 흩어져 보임 → **하나를 척추로, 나머지는 동기·응용으로 계층화.**
한 문장: *"암호화된 LLM 트래픽에서 내용 없이도 '추론 깊이(계산 성격)'가 누출됨을 규명하고(핵심 기여), 이를 워크로드 가시성·비용 추정·에이전트 남용 탐지의 토대로 삼는다."*
- **① 동기(왜 중요):** 암호화 LLM 트래픽 급증 → 복호화 없이는 워크로드·비용·프라이버시가 안 보임. "트래픽만으로 요청의 성격을 알 수 있나?"
- **② 척추(기여=실제 목적):** 기존 side-channel(내용·길이)의 **상류인 '추론 깊이(계산 성격)'라는 새 누출 축을 발견·정량화 + 경계(인프라 조건) 규명.** 짧추/긴추 분류 = 이 누출을 증명하는 **도구**. ← side-channel 논문은 "응용이 대박"이어야 통과 아님, 새 누출 규명 자체가 기여 = 우리 증거(Gemini 96%+경계)와 정확히 일치, 과장 없음.
- **③ 응용/향후:** 네트워크 워크로드 가시성·QoS·이상탐지 / 비용·부하 추정 / 자율 에이전트 남용 탐지 / 프라이버시 경고·방어 설계.
- <!-- [DEPRECATED] 2026-09-05: 2026-09-02의 "주 목표=자율 에이전트 이상탐지" 프레이밍은 3층 중 **응용층(③)으로 강등**. 이유: 아직 미검증(타이밍 사용자편차·데이터 없음)이라 주축 못 됨. 척추는 '증명된 규명(②)'으로 고정. -->
- **다음 실험(목적 A 강화 순):** ①E2 반복확대(공짜)—지터·SNR 실측으로 "언제 새나" 수치화 → ②**인프라 격리**(핵심)—같은 gpt-oss를 느린 클라우드GPU vs Groq LPU로 confound 제거, 경계 인과 규명. 이후 E4 연속·E5 분리·실서비스 일반화. 관련: [[생성형AI 트래픽 식별 — L4 연구 로드맵]].

**핵심 프레이밍 전환 (2026-09-01 확정): 서비스명 → 작업단계·에이전트 행동 추론.**
"ChatGPT냐 아니냐" 서비스명 분류는 기존 앱분류와 겹쳐 신규성 약함. **트래픽만으로 "무슨 행동/작업을 하는지"를 추론**하는 게 진짜 기여. 행동 축(계층 라벨):
- L1 GenAI 트래픽 여부 (vs 일반 웹/스트리밍)
- L2 **에이전트 유형** — 대화형 vs 코딩 에이전트 vs 리서치 에이전트 (행동으로, 서비스명 아님)
- L3 **출력 모달리티** — 텍스트 vs 이미지 vs 음성 생성
- L4 **작업 단계/복잡도** — 단순 질문 vs 긴 추론(extended thinking) vs 도구 사용 ← 최신규
- L5 **배포·자율성** — 로컬 모델 vs 클라우드 API / interactive user vs autonomous agent
- L6 보편성·드리프트 + **왜 행동 라벨이 서비스명보다 교차서비스 일반화가 잘 되나**

**실현가능성(문헌 근거):** L3 음성=전송계층부터 다름(가장 쉬움, "Fingerprinting Encrypted Voice Traffic on Smart Speakers" 등). L4 작업단계=Time Will Tell(번역 vs 분류 태스크 추론)·Remote Timing(의료 vs 코딩 주제)·InputSnatch(timing으로 입력 추론)가 간접근거 — 이미 "태스크 유형이 트래픽에 샌다" 증명됨. **L2 에이전트유형·L5 자율성 = 코퍼스에 거의 0편 = 최대 화이트스페이스.** **핵심 신규성=선행연구는 "알려진 서비스의 내용/주제"를 캠, 우리는 "행동·작업단계·에이전트성 자체"를 라벨공간으로.** 서비스명 무관하게 일반화 → 나중에 이상탐지(비정상 에이전트 행동)로 연결 가능.

**시그니처 가설:** 토큰 스트리밍(SSE)의 IAT·패킷크기 시퀀스 + 음성은 WebRTC 오디오 cadence + 깊은추론은 응답 전 긴 침묵/reasoning 스트림. **함정:** SNI/IP/포트로 새면 반칙 → per-flow split·SNI제거로 행동기반 증명 필수(Sweet Danger 교훈).

## 0. PROJECT CONFIG
> 아래 값을 먼저 읽고, 비어 있는 값은 안전한 기본값으로 처리하라.
> API 키나 기관 권한이 없더라도 OA 수집은 계속하고, 사용할 수 없는 경로만 명확히 보고하라.

```yaml
project:
  project_id: "genai-traffic-identification"
  root: "/workspace"
  topic: "암호화 트래픽에서 생성형 AI 서비스(LLM 챗봇/코파일럿 등) 트래픽 자체를 식별 — 존재 탐지(있다/없다) → 서비스 단위 구분 → 상호작용 유형 추론까지 계층적으로 접근"

  research_questions:
    - "RQ1. 암호화된 상태에서 생성형 AI 트래픽을 일반 웹/스트리밍/API 트래픽과 구분 가능한가? 결정적 피처는 무엇인가(토큰 스트리밍의 IAT 시계열 vs 패킷크기 분포 vs 상·하향 비대칭)?"
    - "RQ2. GenAI 트래픽 식별용 데이터셋을 어떻게 확보·구축하는가? 공개 데이터셋이 존재하는가, 없다면 자체 캡처(웹UI/앱/API·서비스별·상호작용 유형별) 프로토콜과 라벨링·시간동기 방식은? 서비스 UI 변경에 따른 데이터 신선도·재수집 주기는?"
    - "RQ3. 서비스 단위 세분(ChatGPT vs Claude vs Gemini vs Copilot vs Perplexity 등) 어디까지 가능한가? 프론트가 같은 CDN/클라우드 뒤에 있을 때(SNI 없이)도 되는가?"
    - "RQ4. 접근 채널별 트래픽 차이 — 웹 UI vs 공식 앱 vs API 직접호출 — 로 채널을 구분/역추론할 수 있는가?"
    - "RQ5. 상호작용 유형(짧은 QA vs 긴 생성, 코드생성 vs 자연어, 멀티턴 vs 단발, 이미지·음성 멀티모달)이 트래픽 형태에서 추론 가능한가?"
    - "RQ6. 보편성 — 네트워크 환경(가정/모바일/VPN·프록시 경유)·시점을 넘어 식별기가 일반화되는가? 서비스 UI/프로토콜 변경에 얼마나 견디는가(드리프트)?"

  include_scope:
    - "암호화 트래픽 분류·표현학습 (transformer/byte 기반: ET-BERT, YaTC, THA, TFE-GNN 등) — 방법론 공유"
    - "웹사이트/서비스 핑거프린팅 (website fingerprinting, service identification) — 특히 SNI·IP 없는 행동 기반"
    - "스트리밍 미디어 vs 대화형 스트리밍 구분 (SSE·chunked transfer·QUIC 스트림 타이밍 분석)"
    - "LLM 서비스 트래픽 특성 연구 (토큰 스트리밍 부채널, 응답 길이·타이핑 속도 누출, 프롬프트 길이 추론)"
    - "부채널/프라이버시 누출 (키스트로크·가변길이 압축·타이밍 기반 정보 추론)"
    - "보편성/교차 데이터셋 일반화·컨셉 드리프트 대응"

  exclude_scope:
    - "평문 페이로드/DPI 시그니처 기반 식별 (암호화 대상이 아님)"
    - "LLM 응답 내용 자체의 복원·해독 (본 단계 범위 밖 — 존재/유형 식별에 한정)"
    - "생성형 AI '모델' 성능·품질 벤치마크 (트래픽 무관)"
    - "악성 LLM 사용 탐지 등 앱/서비스 식별과 무관한 보안 태스크 (식별 성공 후 응용으로만 언급)"
    - "트래픽과 무관한 순수 NLP/생성 방법론"
    - "자체 데이터 수집 불가한 폐쇄 사설 서비스 (공개·자체수집 가능 서비스만 다룸)"
```

## 기록
### v3 파이프라인 재건·acquire 버그수정 (L1~L5 확정판)  <!-- (2026-09-01) -->
- 08-31 다른 세션이 **`pipeline_v3.py`**(마스터 프롬프트 완전구현: preflight→discover→resolve→canary→acquire→report) + L1~L5 맞춤 쿼리14+seed4 + 개선 gate(intrusion/malware/anomaly 제외) 작성. config도 영문 L1~L5 주제로 갱신. 활성 DB만 유실 상태였음(legacy에 아카이브 3개: 원본3342, gate_fix 332×2).
- 이 세션서 v3로 깨끗이 재건: **332편**(core 8·method 69·background 36·noise 219). RQ커버 L2=30·L6=31·L1=21·L3/4/5 각 8~9.
- **acquire 버그 잡음**: line 244 UPDATE에 `reason_code='downloaded_%s'%loc['source']`가 SQL 문자열 안에 박혀 OperationalError → 좋은 arXiv PDF가 failed 오기록. `reason_code=?` 파라미터로 수정 → **OA 26편 다운로드**(직전 0).
- failed 44 = http_403 봇차단 27 + HAL repo 오응답 15 + 기타 2 (전부 정당, 수동몫). no_oa 7, background 36(메타만).
- 새 온타깃: **Fingerprinting Encrypted Voice Traffic on Smart Speakers**(RQ3 음성), InputSnatch(timing), QUIC WFP defenses, Evaluation of local LLMs for network traffic packet analysis(2026).
- 관련 파일: `02_LLM/02_literature/tools/literature_collection/pipeline_v3.py`, `02_LLM/02_literature/config/collection.yaml`, `02_LLM/02_literature/papers/state/literature.db`. 재실행: `python pipeline_v3.py run --config config/collection.yaml`.

### P1 선행연구 정독 → 차별점·위협모델 확정  <!-- (2026-08-22) -->
정독 3편(다운로드분): Whisper Leak, Time Will Tell, Remote Timing. 관련 파일: `02_LLM/02_literature/papers/pdfs/`.

**선행연구 공통 구도 (네트워크 LLM 부채널):**
- 관측지점 동일 = **passive 네트워크 도청, TLS 그대로, 스트리밍 토큰의 패킷크기+도착간격(IAT)**.
- 목표 = 전부 **내용(content) 추론**. Whisper Leak=민감 주제 이진탐지(타깃토픽당 분류기, 28 LLM, >98% AUPRC), Time Will Tell=출력 토큰수로 번역언어/분류클래스 복원, Remote Timing=speculative decoding 타이밍으로 주제(의료 vs 코딩)·언어·PII 복원(ChatGPT·Claude).
- 전부 **"이미 특정 LLM 서비스 트래픽인 걸 전제"** 하고 그 안을 캠.

**아무도 안 한 것 (= 우리 갭):**
1. **탐지**: 이 암호화 flow가 GenAI 서비스 트래픽이냐 vs 일반 웹/스트리밍/API? (프레이밍 자체가 없음)
2. **서비스 구분**: 어느 제공자냐(ChatGPT/Claude/Gemini/Copilot/Perplexity), SNI 없이. (Remote Timing은 ChatGPT·Claude를 각각 알려진 타깃으로 쓸 뿐, 어느 서비스인지 분류 안 함)
3. **채널**: 웹UI vs 앱 vs API 직접호출.
4. **상호작용 유형**: 짧은QA/긴생성/코드/멀티턴/멀티모달 (트래픽 형태로).
5. **open-world**: 미지·신규 서비스를 OOD로, 억지로 known 클래스에 안 넣음.
6. **보편성**: 네트워크 환경(VPN/모바일)·시점(UI/프로토콜 드리프트) 넘어 견딤.

**차별점 1문장:** *선행연구는 "알려진 LLM 트래픽 속 내용 누출"을 함 — 우리는 그 상류에서 **GenAI 서비스/채널/상호작용 유형 자체를 open-world·보편적으로 식별**한다.*

**위협모델:** 관측지점은 선행연구와 동일(passive, TLS, 패킷크기+IAT+방향/볼륨). 단 **태스크가 내용복원이 아니라 식별**. → 내용이 새면 식별은 당연히 가능(선행연구가 우리 실현가능성 근거), 피처도 겹침(스트리밍 IAT/크기). 신규성은 **라벨공간·open-world·보편성** = [[02_SGS]] 기존 강점(OOD·교차데이터 일반화·행동 시퀀스)과 정렬.

### core 201편 정제 → 정타깃 23편 + 신규성 판단  <!-- (2026-08-22) -->
- core 201편은 LLM 일반논문(교육/의료 챗봇·번역·서베이) 대량 오탑재. 사람(Claude) 판정으로 **23편 선별**, DB에 `on_target_tier` 컬럼 태깅. 리포트 `02_LLM/02_literature/papers/reports/curated_core.md`.
- **TIER1 정타깃 5편** (GenAI 트래픽 네트워크 식별): Whisper Leak, Time Will Tell, Remote Timing Attacks, Hello GenAI?, LLM-WFIN.
- TIER2 부채널 7 (캐시·GPU·물리·음향, RQ5 선행) / TIER3 암호트래픽 방법론 6 / TIER4 LLM=도구 5.
- **신규성 판단 (중요)**:
  - **Whisper Leak(2025)이 사실상 정면 선행연구** — 암호화 LLM 트래픽 패킷크기·타이밍으로 프롬프트 주제 추론(28 LLM). "GenAI 트래픽에서 내용 누출"은 이미 됨.
  - 즉 순진한 버전("LLM 트래픽 식별 가능?")은 남이 함. **차별점 필요.**
  - 상대적 빈 땅: **서비스 단위 구분(ChatGPT vs Claude vs Gemini, RQ3)·접근채널(웹/앱/API, RQ4)·open-world 미지 서비스·드리프트 견딤(RQ6)** — 부채널 논문들은 내용 누출에 집중, 식별/핑거프린팅 자체는 얕음.
  - 이건 [[02_SGS]]의 기존 강점(open-world·보편성·행동 시퀀스)과 정렬됨 → 각 나옴.
- 관련: [[STTabNet·VPN·Tor 보편분류]](WFP·표현학습 방법), TIER3 "Sweet Danger of Sugar"=암호트래픽 표현학습 데이터누수 경고 필독.

### TIER1+2 PDF 다운로드 (scope B, 일부)  <!-- (2026-08-22) -->
- TIER1+2 = 12편 중 **9편 자동 다운로드·검증 완료** → `02_LLM/02_literature/papers/pdfs/`. 다운로더 모듈 추가(`acquire/{resolve,download}.py`, `validate/pdf.py`, cli `download` 서브커맨드).
- 나머지 3편 = OA 확정이나 **출판사 봇차단(403)**: LLM-WFIN(MDPI)·Hello GenAI(ACM gold)·Keystrokes(IEEE Access). UA위장 금지 → 수동. 링크는 `02_LLM/02_literature/papers/reports/manual_queue_targets.md`.
- 삽질: arXiv id가 `arxiv.2410.17175`로 접두 오염 저장돼 URL 404 → resolve에서 `arxiv.`/`arxiv:` 접두 정리로 수정. (arXiv 첫 히트 throttle인 줄 오판했다가 실제는 id 버그였음.)

### 논문 자동수집 툴 구축·1차 발견 (scope A)  <!-- (2026-08-22) -->
- 마스터 프롬프트(`generalized_automated_paper_collection_master_prompt.md`) 기반 문헌수집 파이프라인 구현. **scope A = 메타데이터 발견만, PDF 다운로드 없음.**
- 관련 파일: `02_LLM/02_literature/tools/literature_collection/` (cli·db·normalize·relevance·queries·discovery/{openalex,arxiv,crossref}·report), 설정 `02_LLM/02_literature/config/collection.yaml`.
- 소스 = OpenAlex+arXiv+Crossref (무키, polite mailto=cole0213). 28개 topic 쿼리 자동생성(RQ1~6 태그).
- 결과: **고유 3340편**, OA표시 2042. 관련성 core 201 / method 1394 / background 559 / noise 846 / unclear 340. → `02_LLM/02_literature/papers/state/literature.db`, `manifest.csv`, `reports/`.
- **삽질/주의**:
  - cap이 중복 재조회까지 세서 12/28 쿼리에서 조기중단 → unique 기준으로 수정, max 4000.
  - 관련성 게이트가 순수 키워드라 **"LLM=식별대상"(우리 타깃) vs "LLM=도구"(IDS·합성·증강) 구분 못함** → TARGET_SIGNAL(fingerprint·chatbot traffic 등) 있으면 core, TOOL_USE(IDS·GAN·malicious 등)면 method로 강등. 정밀도 개선했으나 여전히 6G survey 등 일부 오탑재. **다음 단계서 사람/LLM 판정으로 정제 필요.**
  - arXiv `all:` 검색은 노이즈 큼(연도필터 없어 옛 논문 섞임). OpenAlex가 최고품질.
  - 교차버전 중복(같은 제목 저널DOI+프리프린트) 미병합 — paper_key가 DOI/arXiv라 별건 취급.

### 노트 신설 — config 초안  <!-- (2026-08-21) -->
- [[02_SGS]] 보편 분류기 연구의 방법론(정체성 피처 없는 행동 시퀀스 분류·보편성 실증)을 **생성형 AI 트래픽**이라는 새 대주제에 이식.
- 이미지의 `open-world-encrypted-traffic-discovery` config 양식을 그대로 따라 RQ/scope 구성. 아직 실험 전, 가설 단계.
- 핵심 가설: 토큰 스트리밍의 시계열 지문이 식별 신호. 검증 필요.

## 다음 할 일 (연구 로드맵 P1~P5)
- [x] 문헌 자동수집 툴 구축 + 1차 발견(scope A) — 고유 3340편
- [x] core 201편 정제 → 정타깃 23편(`on_target_tier` 태깅)
- [x] TIER1+2 PDF 다운로드 9/12 (봇차단 3편 수동)
- [x] **P1 선행연구 정독 → 차별점·위협모델 확정** (위 기록)
- [ ] **P2 자체 데이터 캡처 [핵심·최대난관]** — 서비스 3~5 × 채널(웹/앱/API) × 상호작용유형(짧은QA/긴생성/코드/멀티턴/멀티모달). TLS 그대로, 능동생성 라벨, 세션-패킷 시간동기. [[PRISM(LAB) 데이터·진단]] 방식 재활용
  - [ ] 캡처 프로토콜·도구(tcpdump/pyshark)·라벨 스키마 설계
  - [ ] 파일럿 캡처(서비스 2개×채널 웹/앱) → 파이프라인 검증
- [ ] **P3 예비분석** — 스트리밍 IAT·패킷크기 분포로 (a)GenAI vs 일반web (b)서비스간 갈리나 값싸게 확인. 안 갈리면 방향 재검토
- [ ] **P4 모델** — [[02_SGS]] 파이프라인 이식(행동 시퀀스·open-world/OOD·트리+딥). RQ1/3/4/5 실험
- [ ] **P5 보편성 증명(=차별점)** — 교차환경(VPN/모바일)·드리프트(시점/UI) 평가. [[STTabNet·VPN·Tor 보편분류]] 일반화 프레임 재사용
- [ ] (보조) 봇차단 3편 수동 다운로드 / TIER3 방법론 6편 정독(특히 Sweet Danger of Sugar)

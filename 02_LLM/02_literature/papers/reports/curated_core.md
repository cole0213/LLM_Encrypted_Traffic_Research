# Curated Core — genai-traffic-identification

core 201편을 사람(Claude) 판정으로 정제. 나머지 ~177편은 LLM 일반논문(교육/의료 챗봇·번역·서베이 등) 오탑재 → 제외.

선별 **23편** (TIER1 정타깃 5 / TIER2 부채널 7 / TIER3 방법론 6 / TIER4 도구 5).


## TIER 1 — GenAI/LLM 트래픽 네트워크 식별 (정타깃)

- **Whisper Leak: a side-channel attack on Large Language Models** (2025) `2511.03675v1`
  - Whisper Leak: 암호화 LLM 트래픽의 패킷크기·타이밍으로 프롬프트 주제 추론, 28개 LLM. ★가장 근접 선행연구
- **Time Will Tell: Timing Side Channels via Output Token Count in Large Language Models** (2024) `2412.15431v1`
  - Time Will Tell: 출력 토큰 수 타이밍 부채널, 네트워크 너머 폐쇄형 LLM 대상
- **Remote Timing Attacks on Efficient Language Model Inference** (2024) `10.48550/arxiv.2410.17175`
  - Remote Timing Attacks: 사용자↔원격 LLM 암호화 트래픽 관찰로 메시지 내용 추론
- **Hello, GenAI? Dissecting Human to Generative AI Calling** (2025) `10.1145/3730567.3764441`
  - Hello, GenAI?: 실시간 음성 GenAI 통화앱의 네트워크 운영특성 측정/해부
- **LLM-WFIN: A Fine-Grained Large Language Model (LLM)-Oriented Website Fingerprinting Attack via Fusing Interrupt Trace and Network Traffic** (2025) `10.3390/electronics14071263`
  - LLM-WFIN: LLM 웹접속의 website fingerprinting(트래픽+interrupt trace 융합)

## TIER 2 — LLM 토큰/상호작용 부채널 (비네트워크, RQ5 선행)

- **The Early Bird Catches the Leak: Unveiling Timing Side Channels in LLM Serving Systems** (2024) `2409.20002v5`
  - Early Bird: LLM 서빙 시스템 공유캐시·GPU 타이밍 부채널로 시스템프롬프트 추론
- **Spill The Beans: Exploiting CPU Cache Side-Channels to Leak Tokens from Large Language Models** (2025) `2505.00817v1`
  - Spill The Beans: CPU 캐시 부채널로 LLM 생성 토큰 유출
- **SparSEEty: Extracting Tokens from Sparsity-Exploiting LLM Serving Systems via Deterministic Side Channels** (2026) `2608.02995v1`
  - SparSEEty: sparsity-exploiting LLM 서빙의 결정적 부채널로 토큰 추출
- **PrefixWall: Mitigating Prefix Caching Side Channels in Shared LLM Systems** (2026) `2603.10726v2`
  - PrefixWall: prefix caching 타이밍 부채널(타 사용자 요청 재구성) + 완화
- **The Vision Encoder as a Privacy Boundary: Visual-Token Side Channels in Encoder-Free Vision-Language Models** (2026) `2606.14783v1`
  - Vision Encoder as Privacy Boundary: encoder-free VLM의 visual-token 부채널
- **Real-world Edge Neural Network Implementations Leak Private Interactions Through Physical Side Channel** (2025) `2501.14512v1`
  - Edge NN Physical Side Channel: 하드웨어 가속기에서 사용자 상호작용 누출
- **From Keystrokes to Semantics: Acoustic Side-Channel Attacks on Typed Text Using Deep Neural Networks and Large Language Models** (2026) `10.1109/access.2026.3697132`
  - Keystrokes to Semantics: 타이핑 음향 부채널 + LLM으로 텍스트 복원

## TIER 3 — 암호화 트래픽 분류·WFP 방법론 토대

- **The Sweet Danger of Sugar: Debunking Representation Learning for Encrypted Traffic Classification** (2025) `10.1145/3718958.3750498`
  - Sweet Danger of Sugar: 암호트래픽 표현학습의 데이터누수·shortcut 폭로. ★방법론 경고 필독
- **Bottom Aggregating, Top Separating: An Aggregator and Separator Network for Encrypted Traffic Understanding** (2025) `10.1109/tifs.2025.3529316`
  - Bottom Aggregating Top Separating: 바이트 의미 왜곡 없는 암호트래픽 이해 모델
- **TAO-Net: Two-stage Adaptive OOD Classification Network for Fine-grained Encrypted Traffic Classification** (2025) `2512.15753v1`
  - TAO-Net: 미지 앱 OOD 세분 분류(신규 카테고리 대응)
- **Respond to Change With Constancy: Instruction-Tuning With LLM for Non-I.I.D. Network Traffic Classification** (2025) `10.1109/tifs.2025.3574971`
  - Respond to Change With Constancy: non-IID 트래픽 분류, 분포드리프트·라벨부족 대응
- **Redefining Website Fingerprinting Attacks With Multiagent LLMs** (2025) `2509.12462v1`
  - Redefining WFP with Multiagent LLMs: SPA·사용자행동 다양성 하에 WFP 재정의
- **Multimodal Reasoning with LLM for Encrypted Traffic Interpretation: A Benchmark** (2026) `2604.08140v1`
  - Multimodal Reasoning LLM for Encrypted Traffic Interpretation: 해석가능 벤치마크

## TIER 4 — LLM을 트래픽분석 도구로 사용 (인접 참고, 식별대상 아님)

- **NetGPT: Generative Pretrained Transformer for Network Traffic** (2023) `10.48550/arxiv.2304.09513`
  - NetGPT: 네트워크 트래픽용 생성 사전학습 모델
- **TrafficLLM: LLMs for improved open-set encrypted traffic analysis** (2026) `10.1016/j.comnet.2025.111847`
  - TrafficLLM: open-set 암호트래픽 분석용 LLM
- **Language of Network: A Generative Pre-trained Model for Encrypted Traffic Comprehension** (2025) `2505.19482v1`
  - Language of Network: 암호트래픽 이해용 생성 사전학습 모델
- **NetKD: Towards Resource-Efficient Encrypted Traffic Classification Using Knowledge Distillation for Language Models** (2024) `10.1109/cscwd61410.2024.10580837`
  - NetKD: 언어모델 지식증류 경량 암호트래픽 분류
- **Encrypted Traffic Detection in Resource Constrained IoT Networks: A Diffusion Model and LLM Integrated Framework** (2025) `2512.21144v1`
  - DMLITE: diffusion+LLM IoT 암호트래픽 탐지 프레임워크

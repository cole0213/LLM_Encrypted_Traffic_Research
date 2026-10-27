# 생성형AI 트래픽 식별 — baseline 문헌분석

상위: [[생성형AI 트래픽 식별]] · [[02_SGS]]

## 핵심 요약
세미나·심층연구용 **baseline 13편 전문 정독** 분석(2026-08-22). 세 갈래 = ①LLM 네트워크 부채널 3(우리 주제 정면 선행) ②암호트래픽 표현학습 3(ET-BERT/TFE-GNN/YaTC) ③WFP/open-world/논쟁 7. **최대 수확 = [[#논쟁]]의 "Sweet Danger of Sugar"가 ET-BERT·YaTC를 데이터누수 shortcut으로 정면 반박** — 비판대상과 비판논문을 둘 다 확보. PDF: `02_LLM/02_literature/papers/pdfs/`, 태깅: DB `baseline` 컬럼.

---
## 1. 논문별 요약 (배경/방법/발견/한계)

### 그룹 A — LLM 네트워크 부채널 (우리 주제 정면)
**Whisper Leak (2025, Microsoft, arXiv 2511.03675)**
- 배경: TLS는 내용 암호화하나 패킷 크기·타이밍 메타데이터 노출. 기존 부채널은 응답재구성/특정 최적화에 집중 → "프롬프트 상위 주제 분류" 공백.
- 방법: 수동 네트워크 관찰자. 표적주제(돈세탁) 100변형 + Quora 배경 11,716질문, 모델당 최대 21,716쿼리 tcpdump 캡처 → 크기/타이밍 시퀀스로 LightGBM·Bi-LSTM·DistilBERT 이진분류.
- 발견: 28개 상용 LLM 중 17개 AUPRC>98%. 10,000:1 불균형서 recall 5-20%에 정밀도 100%. 완화 3종(패딩·배칭·주입) AUPRC 3.5-4.8pp만 하락.
- 한계: 극단불균형 정밀도는 외삽 추정. 단일 표적·영어·단일턴 PoC. 통제 클라우드 결과(하한 규정).

**Time Will Tell (2024, Toronto, arXiv 2412.15431)**
- 배경: "출력 토큰 수" 사이드채널 최초 제안. 번역 대상언어·분류 출력클래스가 토큰수를 체계적으로 바꿈.
- 방법: 스트리밍 불필요. 입출력 길이+응답시간 관찰. 자기회귀 T∝n으로 타이밍→토큰수. 번역=2D 프로파일 GMM+Bhattacharyya, 분류=설명길이 임계값(few-shot 편향 증폭).
- 발견: 번역 12+언어 77-82% 정밀도(중/러/한 ~100%). 분류 GPT-4o 86.9%. 원격(AWS) GPT-4o 74.7%.
- 한계: GPT-4o 토큰수-시간 상관 0.370(투기적 디코딩 추정). batch=1·저부하 가정. 분류는 이진·태스크 인지 가정.

**Remote Timing Attacks (2024, Google DeepMind, arXiv 2410.17175)**
- 배경: 효율추론(투기적 디코딩 등)이 데이터의존 타이밍 편차 유발. LLM은 토큰당 수백ms라 원격 타이밍 실용적. 효율추론 첫 타이밍공격.
- 방법: 수동+능동 위협모델. A/B 테스트(pA/pB 100회)로 토큰간 지연 서명 GMM/CNN 학습. 주제(의료 vs 코딩) 분류, 프로덕션 ChatGPT/Claude는 IPD+패킷크기 CNN.
- 발견: 5개 효율추론 다 취약(A/B 근100%). 오픈소스 주제 89.5-99.8%. 능동공격 PII 첫자리 97.2%. **더 크고 최적화된 모델일수록 더 취약.**
- 한계: 서명 시변(GPT-3.5 한달 뒤 붕괴). 웹UI GMM<30%. constant-rate 방어로 완전차단 가능(대역폭 50-300%↑).

### 그룹 B — 암호트래픽 표현학습
**ET-BERT (2022, WWW)**
- 배경: 기존 DL은 라벨 분포 과의존·일반화 약함. 평문지문(FlowPrint)·통계특징은 TLS 1.3 부적응. 대규모 비라벨로 일반화 표현 학습.
- 방법: 원시 데이터그램 BURST 분할 → bi-gram/BPE 토큰화 → 12층 Transformer. 자기지도 Masked BURST + Same-origin BURST 사전학습 후 fine-tuning.
- 발견: 6개 공개셋+CSTNET-TLS1.3 SOTA. ISCX-VPN F1 98.9%, TLS1.3 97.4%(+10). few-shot 10%도 91.55%.
- 한계: 시변 콘텐츠·TLS1.3 ECH로 SNI 라벨링 불가. 사전학습 30GB 고비용. **미관측 클래스 예측은 future work.**

**TFE-GNN (2023, WWW)**
- 배경: flow 통계특징은 짧은flow서 불안정, 헤더/페이로드 동일취급 문제. 세밀 in-app 행동 분류 목표.
- 방법: PMI로 바이트 그래프 구성 → dual embedding(헤더/페이로드) → GraphSAGE 4층 → cross-gated fusion → Bi-LSTM. **사전학습 없음.**
- 발견: ISCX-Tor F1 0.9855, Telegram 0.9649. ET-BERT 대비 FLOPs 1/5·파라미터 절반(효율 우위 주장).
- 한계: 학습전 고정 그래프 비최적. 바이트 시간정보 미반영. 하이퍼파라미터 민감.

**YaTC (2023, AAAI)**
- 배경: 원시바이트 단순표현 정보누락, 긴 패킷 바이트가 압도. BERT식 NLP 사전학습은 트래픽에 부적절 주장.
- 방법: MFR 행렬(byte/packet/flow 계층) → packet-level + flow-level attention(파라미터 공유) → **MAE 사전학습(90% 마스킹 재구성)** → fine-tuning.
- 발견: ISCXVPN F1 98.04%, USTC-TFC 97.86%. Cross-Platform 전이 +12.42%p. 90% 마스킹 최적 → **"트래픽은 텍스트보다 이미지"** 주장.
- 한계: 사전학습 데이터구성 좌우. 90% 마스킹 데이터셋별 재조정. 별도 한계절 없음.

### 그룹 C — WFP (website fingerprinting)
**Deep Fingerprinting (2018, CCS)**
- 배경: Tor WFP. 기존 공격(k-NN/CUMUL/k-FP) 수작업 피처, 저비용 방어(WTF-PAD/Walkie-Talkie)에 30%<로 붕괴.
- 방법: 로컬 수동공격자. **방향값 시퀀스(-1/+1, 5000)만**, 수작업 無. 깊은 CNN(VGG/ResNet식).
- 발견: 비방어 closed 98.3%. WTF-PAD 90.7%(유일 유효). Walkie-Talkie 49.7%(방어됨). open precision 0.99/recall 0.94.
- 한계: Walkie-Talkie 무력. 10-14일 staleness. 홈페이지만·방향만(타이밍 미활용).

**Var-CNN (2019, PoPETs)**
- 배경: DL WFP는 대량데이터서만 우수, 소량서 수작업피처 대비 미미. 웹 자주변해 갱신부담.
- 방법: ResNet-18+dilated causal conv, 방향+타이밍 2모델 앙상블, 수작업 통계 7개 in-training 결합. 소량데이터 강조.
- 발견: 소량(100×100) 97.8%(DF 93.6%, DF는 5배 데이터 필요). open서 FPR 4배 감소.
- 한계: DF보다 훈련 6배 느림. Tamaraw 무력. Rimmer 데이터 재사용(자체수집 아님).

**Redefining WFP with Multi-Agent LLMs (2025, arXiv 2509.12462)**
- 배경: 기존 WFP는 정적·페이지단위 가정, SPA/스트리밍서 붕괴. 스크립트봇은 실사용자 행동다양성 없음.
- 방법: 사이트(도메인) 단위 라벨, 5000패킷 연속블록. **LLM 멀티에이전트(Claude 3.7 + Computer Use)로 인간형 트래픽 생성**, persona+밴딧 프롬프트 최적화.
- 발견: **scripted→human 교차서 F1 ~0 (10%<)**. human→human 75-80%. Human+Claude 훈련 시 cross-user +25-35%p. ClaudeOnly가 ScriptedOnly 종종 3배.
- 한계: LLM 생성 고비용. API rate limit로 10사이트 규모제한. open-world 수천사이트 곤란. targeted fingerprinting 윤리.

### 그룹 D — open-world / 해석
**DecETT (2025, WWW)**
- 배경: 암호터널(VPN/프록시) 하 앱핑거프린팅. 기존은 재캡슐화·서버정보 은폐 무시.
- 방법: TLS를 "의미앵커"로 터널플로우와 병렬쌍 상관. Siamese Bi-GRU + GRL 5손실로 앱-무관 터널특징 디커플. 추론시 터널플로우만.
- 발견: ShadowsocksR 94.2%. FlowPrint 붕괴(F1 1.4%), ET-BERT 저조(25.6%). 강난독 V2Ray서 2위 대비 +20%.
- 한계: TLS-터널 병렬쌍 직접수집(자원부담). 단일앱 가정. 긴 시퀀스 저하. **54앱 통제환경, 미지앱 미대응.**

**TAO-Net (2025, arXiv 2512.15753)**
- 배경: OOD 트래픽 취약, 기존은 미지를 단일 "Other"로 뭉뚱. ID/OOD 둘 다 + OOD도 세분류 목표.
- 방법: 2단계. ①하이브리드 OOD탐지(LSTM+PCA잔차+층간평활도). ②ID=Transformer, **OOD=GPT-4o 생성+Semantic-Priority Prompt**.
- 발견: macro-F1 96.8-97.7%. PacRep 대비 +38-41pp, GPT-4o 단독 대비 +10-15pp.
- 한계: OOD세분류 GPT-4o 제로샷 의존(프롬프트 라벨목록 좌우). ID/OOD 수동분할. 임계값 고정. LLM 비용·지연 미분석.

**Multimodal Reasoning for Encrypted Traffic (2026, arXiv 2604.08140)**
- 배경: 기존은 단일모달·블랙박스(라벨만). 감사가능 추론과정·의미주석 데이터 부재.
- 방법: BGTD 벤치(Claude Opus로 주석 자동생성). mmTraffic 3모듈(NetMamba 지각 → MLP정렬+보조분류 → Qwen3+LoRA 인지). 의미우선 생성손실로 환각억제.
- 발견: ISCXVPN JClsAcc 0.9902, BERTScore 6개 다 >0.90. Zero-shot LLM 분류 붕괴. **오분류도 리포트에 투명("실패의 투명성").**
- 한계: 인지품질이 지각(인코더) 신뢰도 종속. TLS1.3/Tor 바이트 구별불가쌍 오분류 전파. 정답이 Claude Opus 생성물(개방세계 확장 제한).

---
## 2. 방법론 비교 (설계·자료·도구)

| 논문 | 설계구조 | 피처/입력 | 자료수집(공개?) | 분석도구 | 코드공개 |
|---|---|---|---|---|---|
| Whisper Leak | 캡처→시퀀스→이진분류 | 패킷크기·IAT | Quora+자체표적(미공개) | LightGBM/LSTM/BERT | ✗ |
| Time Will Tell | 오프profiling→매칭 | 출력토큰수·응답시간 | Flores·NatInst(공개) | GMM·Bhattacharyya | ✗ |
| Remote Timing | 서명학습→적합판정 | 토큰간 IPD·크기 | 자체생성+ChatGPT/Claude | GMM·CNN·GCG | ✗ |
| ET-BERT | BURST→Transformer 사전학습 | 원시바이트(hex) | ISCX·USTC+CSTNET(공개) | BERT/PyTorch/UER | ✓✓ |
| TFE-GNN | 바이트그래프→GNN→LSTM | PMI 바이트그래프 | ISCX+WWT(자체) | GraphSAGE/PyTorch | ✗(불명) |
| YaTC | MFR→MAE 사전학습 | MFR 행렬(이미지형) | ISCX·USTC·CICIoT(공개) | ViT/MAE/PyTorch | ✓✓ |
| Deep Fingerprint | 방향시퀀스→CNN | 방향(-1/+1) | Sirinam DF(공개) | CNN/Keras | ✓✓ |
| Var-CNN | 방향+타이밍 앙상블 | 방향·타이밍+통계 | Rimmer(공개) | ResNet-18/Keras | ✓ |
| Redefining WFP | LLM에이전트 생성→WFP분류 | 크기·시간 5000블록 | 3자체(gdrive공개) | 9개WFP/Claude API | ~(데이터만) |
| DecETT | 병렬쌍 상관→Siamese디커플 | TLS-터널 병렬 | 5터널 자체 | Bi-GRU/GRL | ✓ |
| TAO-Net | OOD탐지→적응(LLM)분류 | LSTM특징+PCA | CHNAPP·ISCX(공개) | LSTM/GPT-4o | ✗(불명) |
| Multimodal Reason | 지각→정렬→인지(LLM) | 원시바이트+주석 | BGTD 6종통합 | NetMamba/Qwen3 | ~ |

**패턴:** 트래픽분류 정전(ET-BERT/YaTC/DF/Var-CNN)은 코드·데이터 공개율 높음. 부채널 3편은 코드 미공개(방법은 상술). 최신 LLM활용(TAO-Net/TFE-GNN) 코드링크 확인 안 됨.

---
## 3. 타당성·재현성·해석 비판 (트래픽분류 관점)

- **재현성 최상:** Deep Fingerprinting·YaTC·ET-BERT·Sweet Danger(코드+벤치+데이터). **최하:** 부채널 3편(코드링크 없음)·TAO-Net·TFE-GNN(링크 미확인).
- **내부타당성 역설:** **가장 높은 정확도(ET-BERT/YaTC 98%)가 가장 의심스러움** — Sweet Danger가 per-packet split 데이터누수(암시적 flow ID: SeqNo/AckNo/timestamp)로 부풀려졌음을 실증. per-flow split시 ~40%, frozen시 <30%, **ET-BERT는 랜덤초기화도 동성능(97.1 vs 97.4)** → 사전학습 무의미.
- **상대적으로 견고:** DF/Var-CNN(WFP)은 **방향값만** 써서 flow-ID 누수 여지 작음 → 타당성 높으나 Tor 특정·좁음. 부채널 3편은 인과기전 명확(토큰→패킷)이라 **해석가능성 최상**, 단 시변(drift)에 약함.
- **해석가능성:** 대부분 블랙박스. Multimodal Reasoning만 명시적 증거리포트. Sweet Danger는 feature-importance·5-NN purity로 "왜 되는지"(=shortcut) 해부 = 방법론적 모범.
- **우리 프로젝트 시사:** 정확도 숫자 신뢰 말고 **분할·frozen·shallow 베이스라인**을 Sweet Danger 권고대로 처음부터 통제. 백본은 ET-BERT/YaTC 무비판 이식 금물.

---
## 4. 공통 한계·구조적 병목·논쟁

### 공통 향후과제/한계 (Q1)
- **시간 드리프트(보편):** ET-BERT(콘텐츠 시변)·DF(10-14일 staleness)·Var-CNN(웹 수시간변)·Whisper Leak(분포시프트)·Remote Timing(서명 한달 붕괴). **아무도 안 풂.**
- **open-world/미지클래스:** ET-BERT가 future work로 명시, TAO-Net·DecETT·Redefining WFP 다 씨름하나 미완.
- **데이터/컴퓨트 비용:** 사전학습(ET-BERT 30GB, YaTC 4×3090), LLM생성(Redefining WFP, TAO-Net).
- **통제환경↔실환경 간극:** Whisper Leak·Remote Timing "하한" 규정, DF 파싱 가정.

### 구조적 결함·계산 병목 (Q2)
- **[최대] per-packet split 데이터누수** — Sweet Danger: 암시적/명시적 flow ID를 shortcut으로 악용 → 표현학습 서브분야 전체 98% 주장이 인위적. per-flow시 최대 80% 하락.
- **사전학습 무용 가능성:** ET-BERT 랜덤초기화 동성능.
- **자기회귀=부채널 근원:** 스트리밍 토큰생성이 크기/타이밍 누출(Time Will Tell·Remote Timing). 모든 Transformer 내재라 완화 근본적으로 어려움. **효율추론(투기적 디코딩)이 누출 증가.**
- **표현학습 비효율:** Sweet Danger — shallow ML(LightGBM 등)이 동등/우수한데 표현학습은 최대 2048배 느림.

### 미해결 논쟁 (Q3)
1. **딥/표현학습이 암호트래픽에 값어치 있나?** Sweet Danger=NO(shallow가 이김, shortcut 인플레) vs ET-BERT/YaTC/TFE-GNN 라인=YES. **둘 다 코퍼스에 있음.**
2. **트래픽=NLP냐 CV냐?** ET-BERT(BERT/MLM/언어) vs YaTC(MAE/90%마스킹/"이미지에 가깝다"). 명시적 대립.
3. **메타데이터 누출 방어 가능한가?** Whisper Leak(완전차단 불가, 고양이-쥐) vs Remote Timing(constant-rate 완전차단, 단 대역폭 대가).
4. **합성 vs 실측 데이터:** Redefining WFP — 스크립트봇 훈련은 인간서 붕괴(행동엔트로피) → DF/Var-CNN식 crawl-and-train 방법론 자체 도전.
5. **평가지표 무결성:** micro-F1 오용(YaTC/NetMamba 지적), 참조기반 지표 둔감(Multimodal Reasoning).

---
## 5. 세미나 심화질문 3

1. **[이론충돌·DL 값어치]** per-flow split이 ET-BERT·YaTC를 ~40%로 무너뜨리고 랜덤초기화가 사전학습과 동성능이라면, 암호트래픽 표현학습은 진짜 진보인가 벤치마킹 아티팩트인가? 그렇다면 우리 GenAI-트래픽 분류기는 이 백본들을 이식할까, shallow ML로 갈까?
2. **[귀납편향 해석]** 트래픽을 언어(ET-BERT)·이미지(YaTC)·그래프(TFE-GNN)로 보는 상충된 가정이 전부 겹치는 ISCX서 SOTA를 주장한다. 이들은 모델링 능력을 재는가 데이터셋 shortcut을 재는가? 무슨 실험이 이를 판별하는가?
3. **[드리프트·방어충돌, 우리 주제 직결]** 부채널 논문들은 패킷크기·타이밍으로 내용이 근100% 샌다고 증명하나 방어는 대역폭/지연을 대가로 한다. GenAI-트래픽 **식별**(우리 태스크)에서 스트리밍-토큰 시그니처는 안정적 지문인가, 아니면 벤더 완화(패딩/배칭)가 지워버릴 이동표적인가 — 우리 명제는 이 논문들이 촉발한 방어에 견디는가?

---
## 다음 할 일
- [ ] (선택) 봇차단 3편(LLM-WFIN·Hello GenAI·Keystrokes) 수동 확보해 부채널 커버리지 완성
- [ ] P2 데이터 캡처 설계 시 **Sweet Danger 권고 반영**: per-flow split·frozen 테스트·shallow 베이스라인 처음부터
- [ ] 세미나 후 확정된 차별점을 [[생성형AI 트래픽 식별]]에 반영

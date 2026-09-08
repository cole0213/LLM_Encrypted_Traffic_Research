# 암호화 트래픽 Reasoning Effort 탐지 — 연구설계

상위: [[02_SGS]] · 선행 파일럿 라인: [[생성형AI 트래픽 식별]] · [[생성형AI 트래픽 식별 — L4 연구 로드맵]]
원본 설계 프롬프트: `C:\Users\GyuSang\Downloads\LLM 암호화 트래픽 기반 Reasoning Effort 탐지 연구 설계 프롬프트.md`

## 핵심 요약
암호화(TLS) 상태의 **멀티프로바이더·멀티모델 LLM API 트래픽**에서 reasoning effort(low/high)를
탐지하는 연구의 정식 설계본. 선행 L4 파일럿(단일모델·Gemini/Groq에서 추론깊이 누출 실증, E1 96%)을
**여러 provider·model로 확장**하고, configured effort와 realized reasoning token을 분리한 이중
ground truth·model identification 분리·cross-model 일반화·early detection까지 포함한다.
핵심 방어축은 "이게 그냥 duration/TTFA 재포장 아니냐"와 "reasoning 아니라 provider fingerprint
아니냐"를 정면으로 막는 것.

## 선행 라인과의 관계 (왜 새 노트인가)
- 선행 [[생성형AI 트래픽 식별 — L4 연구 로드맵]]: 단일 모델에서 "추론 ON/OFF가 길이 통제 후에도
  트래픽에 새는가"를 실증(E1 96%, E3 성립조건 = 추론시간 > 지터). 파일럿·측정 중심.
- 본 설계: 그 실증 위에 **멀티프로바이더·멀티모델 정식 데이터셋 + Task A/B/C 분리 + cross-model +
  early detection**을 얹은 논문화 설계. 선행 결과가 근거·baseline으로 들어간다.
- 선행 노트는 폐기하지 않음. 파일럿 산출물(pcap·분류결과)은 본 설계의 존재증명 근거로 재사용.

## 연구 질문 (RQ)
- RQ1: 동일 모델·동일 프롬프트에서 low/high effort가 구별되는 네트워크 패턴을 만드는가?
- RQ2: 어떤 신호가 effort를 가장 잘 나타내나? (단, 스트리밍 가시성 그룹별로 답이 갈림 — 아래)
- RQ3: 새 prompt/날짜/네트워크에 일반화되나?
- RQ4: provider·model 간 탐지 성능 차이는?
- RQ5: 한 모델서 학습한 탐지기가 미학습 모델서도 되나? (cross-model)
- RQ6: 응답 완료 전에 얼마나 일찍 판단 가능한가? (early detection)

## 세 가지 Task (반드시 분리)
- Task A: configured effort 탐지 f(X) → {Low, High}. label = API effort 설정값.
- Task B: realized reasoning 추정 g(X) → reasoning token 수. label = API usage의 실제 thinking token.
- Task C: model identification h(X) → model. 목적 = 모델 자체 fingerprint 세기 측정.
- A와 C를 분리해, effort 탐지기가 단순 모델 fingerprint를 쓰는 게 아닌지 검증.

## 기록

### 급소 6개 검토·반영 <!-- (2026-09-08) -->
설계 프롬프트를 심사자 관점에서 검토, 치명 급소 6개 도출·문서 반영(옛 내용은 `<!-- DEPRECATED -->` 보존).

1. **스트리밍 가시성 축 (제일 위험).** reasoning token이 클라이언트로 스트리밍되는지가 신호 구조
   전체를 결정. Hidden(A)=생각 중 침묵→신호가 TTFA로 수렴, packet sequence 무의미. Streamed(B)=생각
   중 패킷 흐름→sequence가 TTFA 넘는 정보 가짐. 또한 출력을 단답으로 통제할수록 답변 패킷이 사라져
   신호가 TTFA로 수렴하는 **통제-신호 역설**. → provider를 A/B/C로 먼저 분류하고 모든 핵심 분석을
   그룹별로. "packet sequence > TTFA"는 B/C에서만 성립 목표, A에선 "TTFA가 상한"이 결과.
2. **모델명 정정.** 아래 provider별 검증표. 정확한 model ID/snapshot은 실제 API 응답서 저장.
3. **configured effort label 오염.** Claude 5·Gemini는 adaptive → "low/high 설정"이 실제 동작과
   불일치 가능. adaptive-only는 Task A서 빼거나 별도 표기, realized token을 1차 target으로.
4. **유효 표본 수.** group split(prompt_id)이라 독립 단위 = 프롬프트 수(500)지 세션 2만 아님.
   "2만 세션" 부풀리기 금지. cross-model은 leave-one-model-out 시 사실상 N=모델수 → power 약함.
   → **여력 되는 만큼 모델 개수 늘려** cross-model 근거 강화(1차 방향). 부족하면 탐색적으로 표기.
5. **provider fingerprint 누수.** SNI/IP 빼도 packet size 분포·TLS record 크기·chunk 단위가 인프라
   지문 → sequence에 녹아듦. → **within-provider/within-model 평가**를 주 증거로(같은 모델 안에서
   effort 갈리면 진짜 reasoning 신호). adversarial training은 보조.
6. **세션 segmentation.** HTTP/2·QUIC multiplexing·connection reuse로 요청 경계 긋기 어려움.
   → 주 실험 = 요청당 새 연결 강제, 별도 현실성 실험 = 재사용 + idle-gap heuristic + 오분할률 보고.

관통 주제: **깨끗한 통제 = 비현실 / 현실 = confound.** 급소1·5·6 모두 이 축. 논문은
"통제 실험으로 존재 증명 → 현실 실험으로 한계 측정" 2단으로 정면돌파.

### provider별 reasoning 설정·노출 검증 <!-- (2026-09-08, 공식문서 기준, 실측 재검증 필요) -->
| provider | 대표 모델 | effort 설정 | reasoning 노출 | 잠정 그룹 |
|---|---|---|---|---|
| OpenAI | GPT-5.6 Sol / Terra / Luna | reasoning.effort none/low/medium/high/xhigh/max (기본 medium) | raw 은닉(요약만), 생성 중 침묵 | A (Hidden) |
| Claude | Opus 4.7 / 4.8 · Sonnet 5 · Fable 5 · Haiku 5 | effort low/medium/high/xhigh (Claude 5 = adaptive-only) | thinking_delta SSE 스트리밍(요약·풀 과금) | B (Streamed) |
| Gemini | Pro · Flash | thinkingLevel / thinkingBudget + includeThoughts | includeThoughts on=요약 스트리밍(B), off=침묵(A) | A/B 가변 |
| Grok (xAI) | grok-4.6 | reasoning_effort low/medium/high/(xhigh 4.6+) | reasoning summary delta 스트리밍 | B (Streamed) |

- Sol/Terra/Luna = OpenAI GPT-5.6 계열(flagship/balanced/cost). 실재 확인.
- Claude 5(Opus 4.7·4.8·Sonnet 5·Fable 5)는 adaptive thinking이 유일한 thinking on 경로, budget_tokens deprecated.
- 함의: 선행 E3의 "Claude 스트리밍 vs OpenAI 침묵" 관찰과 정합. 성립조건 = 추론시간 > 지터.
- 캡처 설정(Gemini includeThoughts, Claude 요약 노출)이 관측 트래픽을 바꿈 → 수집 프로토콜에 고정.

## 다음 할 일
- [ ] provider별 정확한 model ID/snapshot·effort parameter를 실제 API 호출로 캡처·저장 (문서값 아닌 응답값)
- [ ] A/B/C 스트리밍 그룹 분류를 **실측**으로 확정(패킷캡처로 생각 구간 downlink 유무 직접 확인)
- [ ] Task A 대상에서 adaptive-only(Claude 5·Gemini auto) 처리 방침 확정
- [ ] within-provider 평가 프로토콜 설계(급소5 방어 핵심)
- [ ] 요청당 연결 1:1 강제 캡처 셋업 + 현실성용 재사용 segmentation 방법 확정(급소6)
- [ ] cross-model 모델 개수 확장 계획(급소4) — 여력·비용 산정
- [ ] 선행 파일럿 pcap을 본 설계의 존재증명 baseline으로 재편입
- 관련: [[생성형AI 트래픽 식별 — 실험 설계·평가 개념]] · [[생성형AI 트래픽 식별 — baseline 문헌분석]]

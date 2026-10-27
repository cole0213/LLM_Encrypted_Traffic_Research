# 암호화 트래픽 Reasoning Effort 탐지 — 연구설계

상위: [[02_SGS]] · 선행 파일럿 라인: [[생성형AI 트래픽 식별]] · [[생성형AI 트래픽 식별 — L4 연구 로드맵]]
원본 설계 프롬프트: `C:\Users\GyuSang\Downloads\LLM 암호화 트래픽 기반 Reasoning Effort 탐지 연구 설계 프롬프트.md`

> **실험 진행 상황·수치는 `U:\root\02_SGS\HANDOFF.md` 가 정본.** 이 노트는 설계와 판단 근거를 담는다.
> 3차(30문항, 2026-10-06)까지 완료. 보고 정본 지표는 **timing-only**(크기 피처 제외)로 바뀌었다.

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
   전체를 결정. ~~Hidden(A)=생각 중 침묵→신호가 TTFA로 수렴, packet sequence 무의미.~~
   <!-- [DEPRECATED] 2026-10-06: 실측 반증. Groq(hidden, reasoning_format="hidden")에서 TTFA 단일
        정확도가 0.492(=무정보)인데 패킷 간 간격은 0.944다. 침묵으로 수렴하지 않고 **간격으로 이동**한다.
        대체 서술은 아래 "가시성 축 실측" 기록 참조. -->
   Streamed(B)=생각 중 패킷 흐름→sequence가 TTFA 넘는 정보 가짐. 또한 출력을 단답으로 통제할수록
   답변 패킷이 사라져 신호가 TTFA로 수렴하는 **통제-신호 역설**. → provider를 A/B/C로 먼저 분류하고
   모든 핵심 분석을 그룹별로.
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

### 가시성 축 실측 — 침묵 수렴이 아니라 '채널 이동' <!-- (2026-10-06) -->
설계 당시 급소1의 "Hidden이면 신호가 TTFA로 수렴"은 **틀렸다.** 3차(30문항·270콜×3데이터셋) 실측:

| | 첫 침묵(TTFA) 단일 | 패킷 간 간격 포함(timing-only) |
|---|---|---|
| Gemini (thinking on, 침묵형) | 0.883 | 0.933 |
| Groq 20b (`reasoning_format="hidden"`) | **0.492 = 무정보** | **0.944** |
| Groq 120b | **0.494** | **0.967** |

- Gemini는 생각이 끝날 때까지 안 보내서 **추론 시간이 통째로 첫 침묵에 쌓인다**
- ~~Groq은 첫 패킷 뒤 패킷들이 생각하는 동안 벌어진다 → 추론 시간이 패킷 사이에 흩어진다~~
  <!-- [DEPRECATED] 2026-10-27: 반증됨. '평균 간격이 크다'를 '흩어졌다'로 읽었으나 실제로는
       간격 하나가 거대해서 평균이 끌려올라간 것이었다. 대체 서술은 아래 "추론 멈춤의 위치" 기록. -->
- Groq도 침묵은 **한 군데**다. 다만 첫 응답 패킷 **이후**에 있다(아래 "추론 멈춤의 위치")
- 간격의 **방향도 정반대**(Gemini 27→19 감소 / Groq 16→84 증가) → within-provider 평가 필수의 직접 근거
- 즉 hidden은 "신호 소멸"도 "TTFA 수렴"도 아닌 **채널 이동**이다. 관련: [[생성형AI 트래픽 식별 — L4 연구 로드맵]]

### 바이트 피처는 신호로 쓰면 안 된다 <!-- (2026-10-06) -->
답을 A/B/C/D 한 글자로 고정했는데도 `down_bytes`에 신호가 남아 정체를 갈라냈다. **provider마다 다르다.**

- **Groq = usage 숫자 자릿수 아티팩트.** 추론 텍스트는 안 온다(`had_reasoning: false`).
  SSE 끝 `usage` 객체의 토큰 수 자릿수(`33`→`227`→`1204`)가 평문 길이를 늘린 것.
  자릿수를 고정하면 추론량 하위25% vs 상위25%의 바이트가 **완전히 같다**(2,144 vs 2,144).
  추론 흔적이 아니라 **라벨의 그림자**다. 숫자 패딩 1바이트면 막힌다.
- **Gemini = 진짜 데이터가 더 온다.** 자릿수 고정해도 추론토큰당 약 3.9바이트로 선형(3자리 구간 AUC 1.000).
  텍스트 1토큰 평균 바이트와 비슷해 **thought summary가 실제 전송된다고 의심**된다 — **미확인**.
- **대응: 보고 정본을 `timing-only`(간격 2피처)로 옮겼다.** 7개 비교 중 4개에서 타이밍 2피처가
  하향 6피처를 **이긴다**. 크기를 버려도 잃는 게 없으니 두 의혹을 통째로 우회한다.

### 설정(configured)은 깊이를 거의 못 나타낸다 <!-- (2026-10-06) -->
급소3(configured label 오염)이 **실측으로 확정**됐다. Gemini `think_low` 콜의 **83%(75/90)가
추론 토큰 0**이다. 추론이 실제로 일어난 콜끼리만 비교하면 `low vs high` 균형정확도가 **0.667**로
떨어진다(전체 기준 0.911). 즉 Task A 성능의 대부분은 "**생각을 했나 안 했나**"이지 "얼마나 깊이"가 아니다.
→ 설계의 "realized token을 1차 target으로" 방침이 옳았다. **Task B 착수가 다음 순서.**

### ⭐ 추론 멈춤의 위치 — 둘 다 '단일 침묵'이고 위치만 다르다 <!-- (2026-10-27) -->
Groq 120콜 쓸기에서 **최대 패킷 간격 = 첫 간격**인 콜이 110/120(92%)이었다. 짧은 설명 조건은 24/24(100%).
즉 추론 멈춤은 응답 전체에 흩어지지 않고 **첫 응답 패킷 직후 한 군데에 통째로** 있다.

| | 침묵 위치 | 포착 피처 | 3차 단일 AUC |
|---|---|---|---|
| Gemini | 첫 패킷 **이전** | `pkt_gap_ms`(요청→첫응답) | 0.890 |
| Groq | 첫 패킷 **이후** | `down_iat_first_ms`(첫 간격) | — (신규) |

- `pkt_gap_ms`가 Groq에서 무용지물(0.49)이던 이유가 이걸로 설명된다 — 첫 패킷이 추론과 무관하게 ~300ms 고정
- "채널이 이동한다"보다 단순하고 강한 설명. **양쪽 다 추론량에 비례하는 단일 침묵**이고 기준점만 다르다
- 관련: [[생성형AI 트래픽 식별 — L4 연구 로드맵]]의 "응답 전 침묵 구간" 피처 설계가 Groq에선 기준점을
  첫 패킷으로 옮겨야 한다는 뜻

### 평균 간격은 긴 응답에서 신호를 지운다 <!-- (2026-10-27) -->
추론 멈춤은 응답당 사실상 한 번인데, 답이 길면 간격이 수백 개가 되어 평균에 묻힌다.
`think_high` 기준 실측(Groq 120b):

| 응답 길이 | 추론 토큰 | 첫 간격 | 평균 간격 |
|---|---|---|---|
| 1글자 | 210 | 548ms | 183.7ms |
| 짧은 설명(142자) | 286 | 1,912ms | 32.9ms |
| 긴 설명(868자) | 571 | **4,017ms** | **16.5ms** |

**평균은 떨어지고 첫 간격은 오른다 — 방향이 반대다.** 평균만 쓰면 "긴 응답에선 신호가 죽는다"는
틀린 결론에 도달한다. → `parse_pcap.py`에 `down_iat_max_ms`·`down_iat_p90/p99_ms`·
`stall_total_ms`·`stall_count`·`down_iat_first_ms` 6개를 추가했다.

⚠️ 단 **정량 관계는 미확정**. 조건 안에서 추론 토큰과의 순위상관이 0.11~0.50으로 약하다.
조건당 8콜 + 아래 오염 때문이며, 깨끗한 캡처로 다시 재야 한다.

### E4(응답 길이) 파일럿 — 설계 결함 3건 <!-- (2026-10-27) -->
"답이 길어져도 추론이 탐지되나"를 재려고 응답 길이를 쓸었다. 본실험 전에 돌린 게 정답이었다.

1. **고정 문자열 arm 폐기.** 길이를 통제하려고 `ABCDEFGHIJ`를 N번 반복시켰는데,
   모델이 횟수를 못 센다(1,601자 지시 → 10,825자 출력, 준수율 **0/24**). 게다가 세느라
   **추론 토큰을 5배**(131→691) 쓴다. 측정 대상을 실험 조작이 오염시키는 꼴이라 폐기.
2. **arm 혼합 캡처 금지.** 5개 arm을 한 캡처에 섞어 무작위로 돌렸더니, 거대 응답 바로 뒤에 온
   짧은 콜의 간격이 1,000~2,100ms로 튀었다(정상은 30ms대). 앞 콜 꼬리·연결 재설정이
   다음 콜 측정창에 섞인 것. 이 때문에 1글자 조건이 3차(AUC 0.997)를 재현 못 했다(0.625).
   → **본실험은 arm 별로 분리 캡처.**
3. **자유 응답이면 길이 통제가 저절로 된다.** `free_brief`에서 답변 토큰이
   low 97.5 / med 111.5 / high 98 로 **추론 수준과 무관**했다. "추론 많이 하면 답도 길어진다"는
   우려가 짧은 응답에선 성립하지 않는다. 억지 고정 장치가 불필요하다는 뜻.
   (긴 응답 `free_full`은 573/492/687로 비단조 — n=8이라 **판정 보류**.)

→ 본실험 조건은 **1글자 / 짧은 설명 / 긴 설명** 3개, 전부 자연 응답, arm별 분리 캡처.

### 쿼터가 실험 규모를 제약한다 <!-- (2026-10-27) -->
- **Groq 무료 티어 일일 토큰 한도 200,000(조직 단위, 키 단위 아님).** 이날 소진돼 본실험이 65/180에서 중단.
  쓸기 실험의 폐기 대상 arm 2개(`400`·`1600`)가 **113,673토큰, 전체의 71%**를 먹은 게 원인.
- 실측 콜당 토큰(입력 300 포함): 1글자 450 / 짧은 설명 606 / **긴 설명 1,294**.
  원안(30문항×3조건×2반복×3arm=540콜)은 **423,000토큰 = 한도의 2.1배**.
- **날짜를 쪼개 돌리면 안 된다** — arm과 날짜가 교락되어 arm 간 비교가 불가능해진다. 3조건은 같은 날 연속으로.
- 유료 전환 시 비용: `gpt-oss-120b` 입력 $0.15 / 출력 $0.60 per 1M → 원안 전체 **약 $0.18**.
  (단가는 `console.groq.com/docs/models`에서 확인. `groq.com/pricing`엔 단가가 없어 교차검증 불가.
   Dev tier의 TPD는 문서 간 수치가 충돌해 **확인 못 함** — 계정 `/settings/limits`에서 봐야 한다.)

## 다음 할 일
- [ ] **Gemini E4** — Groq 쿼터와 무관하므로 먼저 가능. `arm 0`이 3차와 같은 프로토콜이라
      `thought_chars`(바이트 정체)도 같이 확정된다. Gemini 무료 한도는 미확인이라 arm 하나씩 확인하며 진행
- [ ] **Groq E4 재시도** — 쿼터 리셋 후. 유료 전환하면 원안대로, 아니면 20문항으로 축소(141K)
- [ ] ~~Gemini 90콜 재캡처~~ → 위 Gemini E4에 흡수됨
- [ ] **Task B(realized 토큰 회귀) 착수** — Task A 천장이 라벨에서 막힌 것이 3차에서 재확인됨
- [ ] Groq `include_usage=false` 캡처로 자릿수 가설 확정
- [x] ~~A/B/C 스트리밍 그룹 분류를 실측으로 확정~~ → 위 "가시성 축 실측"(2026-10-06). 단 OpenAI·Claude는 미실시
- [ ] provider별 정확한 model ID/snapshot·effort parameter를 실제 API 호출로 캡처·저장 (문서값 아닌 응답값)
- [ ] Task A 대상에서 adaptive-only(Claude 5·Gemini auto) 처리 방침 확정
- [ ] within-provider 평가 프로토콜 설계(급소5 방어 핵심)
- [ ] 요청당 연결 1:1 강제 캡처 셋업 + 현실성용 재사용 segmentation 방법 확정(급소6)
- [ ] cross-model 모델 개수 확장 계획(급소4) — 여력·비용 산정
- [ ] 선행 파일럿 pcap을 본 설계의 존재증명 baseline으로 재편입
- 관련: [[생성형AI 트래픽 식별 — 실험 설계·평가 개념]] · [[생성형AI 트래픽 식별 — baseline 문헌분석]]

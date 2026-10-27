# open-set 판별

## 핵심 요약
학습 안 본 클래스(unknown)를 억지 분류 말고 **거부**하는 능력 측정. 교수님 피드백(2026-09): 실배포는 정제 안 된 raw 트래픽 + 처음 보는 앱 천지 → **raw로 open-set 판별부터**. 논문 관례(80% known/20% unknown, known 8:1:1, unknown 전량 test, AUROC 주지표) 따름. 5방법(MSP·Margin·Entropy·Energy·Distance) 중 **Energy가 best(AUROC 86.5)**, 근데 실전 operating point(FPR@95 51%·OpenF1 52)는 약함 = raw·세밀 프로세스라 원래 어려움. CIL의 전제(새 클래스 탐지→편입). 관련: [[live-traffic-classifier-plan(memory)]], [[PRISM(LAB) 데이터·진단]], [[주차 교차전이 week2-week3]]

## 기록

### 설계 (논문 근거)  <!-- (2026-09-05) -->
- 코드 `01_code/openset_detect.py`. raw PRISM(노이즈필터 X), seq-core 299, LightGBM(core 튜닝).
- 논문 관례(WebSearch 확인): 클래스 80% known/20% unknown, known train:val:test=8:1:1, unknown 전량 test, **AUROC 주지표**, openness 변주, baseline MSP/OpenMax/energy. 트리앙상블 선례=Darknet open-world(RF·XGBoost uncertainty).
- **≥15 필터는 raw 아님(전처리)** 지적 반영 → **희소 클래스 버리지 말고 unknown 풀에**(RARE_AS_UNKNOWN). 학습가능(≥MIN_FLOW=50)만 known 후보, 나머지·희소는 unknown.
- 5방법(전부 클수록 unknown): MSP(1−maxproba)·Margin(−(top1−top2))·Entropy·Energy(−logsumexp raw_score)·Distance(표준화 X centroid 최소거리).
- 2모드: **random**(week2 내 무작위 80/20) · **temporal**(week2 학습→week3 신규프로세스=unknown, 배포현실·CIL직결).

### random 결과 (week2 raw, 5회)  <!-- (2026-09-06) -->
- 학습가능 65클래스(≥50 flow) + 희소 19 → known 52 / unknown 32(held-out 13 + 희소 19). `03_json/openset_random_w2.json`.

| 방법 | AUROC | OpenF1 | ClosedAcc | FPR@95 |
|---|---|---|---|---|
| **Energy** | **86.48±2.29** | 52.63 | 89.27 | 52.36 |
| Entropy | 82.41 | 54.01 | 90.63 | 50.96 |
| MSP | 78.88 | 51.94 | 90.86 | 51.19 |
| Margin | 76.65 | 49.85 | 90.68 | 51.53 |
| Distance | 53.25 | 46.10 | 88.43 | 88.38 |

- **Energy best**(문헌대로). Entropy·MSP 쓸만. **Distance(centroid) 실패**(53≈랜덤) — 299차원 raw서 유클리드 centroid는 novelty 못 잡음(고차원 저주). Mahalanobis/leaf로 개선하거나 폐기.
- **실전 약함**: FPR@95 ~51%(unknown 95% 잡으려 known 절반 오거부), OpenF1 ~52. AUROC 86은 좋아 보여도 분포 겹침 큼 → raw·세밀 프로세스라 원래 어려운 문제(문헌 baseline F1<45%와 정합).

### temporal(week2→week3) 결과 — 드리프트로 거의 실패  <!-- (2026-09-07) -->
- week2 학습(known 65) → week3 test, 신규 61 프로세스 = unknown. Mahalanobis로 Distance 개선 반영. `03_json/openset_temporal_w2w3.json`.

| 방법 | AUROC | OpenF1 | ClosedAcc | FPR@95 |
|---|---|---|---|---|
| Entropy | 59.69 | 42.27 | 68.27 | 88.18 |
| MSP | 58.04 | 42.72 | 66.32 | 88.62 |
| Distance | 56.53 | 34.36 | 65.72 | 88.63 |
| Margin | 56.25 | 43.59 | 63.94 | 90.11 |
| Energy | 53.92 | 41.61 | 73.26 | 91.75 |

- **random(Energy 86.5) → temporal(~55, 거의 랜덤).** 신규탐지가 무작위 hold-out보다 훨씬 어려움.
- **Energy 역전**(random best → temporal worst): raw logit 기반이라 드리프트로 known logit도 낮아지면 신규랑 구분 불가. Entropy/MSP는 softmax 정규화라 덜 취약(그래도 약함).
- **원인 = 시점 드리프트가 novelty 오염**: week3 known도 드리프트(ClosedAcc 66~73, w2→w3 −32 정합)로 헷갈림 → "드리프트된 known"과 "진짜 신규"의 unknown 점수 겹침.
- **스토리(중요)**: static open-set(random)은 되나 **현실 temporal open-set은 드리프트로 실패** → **CIL(모델 갱신)이 필요**하다는 동기. 실패가 곧 해법의 근거.
- Mahalanobis Distance는 temporal서 56(random 유클리드 53보다 약간↑)이나 여전히 약함. 개선 미미.

### temporal-adapt(CIL 단순형) — 드리프트 적응이 open-set 회복시킴  <!-- (2026-09-08) -->
- week2 학습 → week3-known 일부 흡수 재학습(적응비율 0/0.5/1.0) → 신규 프로세스 open-set 재측정. week3-known test 고정 30%(공정), 신규는 계속 unknown. OOM 캡(known3 50만·new3 9.7만). `03_json/openset_temporal_adapt.json`.

| adapt | Energy | Entropy | MSP | Distance | ClosedAcc |
|---|---|---|---|---|---|
| 0.0 | 53.95 | 59.73 | 58.09 | 56.52 | 68.5 |
| 0.5 | 70.47 | 69.96 | 66.19 | 58.19 | 80.7 |
| 1.0 | **72.37** | 72.05 | 67.94 | 58.81 | 81.5 |

- **핵심: 적응하니 AUROC Energy 54→72(+18)·Entropy 60→72, ClosedAcc 68→81(+13).** 드리프트 잡으니 **open-set 탐지 회복 + Energy 다시 best 복귀**(random 때처럼).
- **완성된 루프**: static open-set 됨(random 86.5) → 시점 드리프트로 실패(temporal 55) → **지속학습(CIL)이 회복(72)**. 논문 핵심 서사.
- Distance(Mahalanobis)는 적응해도 58로 여전히 약함 — 거리기반은 이 문제에 부적합. Energy/Entropy가 주력.
- 한계: 아직 신규클래스 "편입"은 안 함(신규는 계속 거부만). = 드리프트 적응(known 갱신)까지. 진짜 CIL(신규 클래스 학습편입)은 다음.

### CIL 문헌 지형 — 암호화 트래픽 CIL은 이미 붐빈다, 빈칸은 GBDT와 '발견'  <!-- (2026-09-14) -->
- WebSearch로 확인. **암호화 트래픽 CIL 선행연구 다수**: MEMENTO(Computer Networks 2024, Cerasuolo·Aceto·Pescapè·Rossi; MIRAGE19·CESNET-TLS22, fine-tuning+메모리+distillation+rectification, 최대 10배 속도), ILETC(Computer Networks 2023, WGAN-GP 생성리플레이+exemplar), HCA-Net(Computers & Security 2024, contrastive), MISS(C&S 2023), Explainable FCIL(CN 2025). **전부 신경망** — distillation·생성리플레이는 부스팅 트리에 못 옮긴다.
- **GBDT 증분학습은 "새 데이터/드리프트"만 다룬다**: iGBDT(Neural Processing Letters 2019), GBDT-IL(Sensors 2024), Elastic/Online GBDT. **클래스 추가는 안 다룸.** → 우리 `temporal-adapt`는 CIL이 아니라 **이 범주(드리프트 적응)**다. HANDOFF의 "CIL 단순형" 표기는 과장 — 논문에 그렇게 쓰면 지적당한다.
- 표형 CIL 인접: TRIL3(arXiv 2407.09039) — ILVQ+Deep Neural Decision Forest, 순수 GBDT 아님(미분가능 NN 하이브리드).
- **LightGBM num_class 고정 확인**(GitHub #1306·#3747): `num_class × num_boost_round` 트리를 만들고 num_class는 학습 시 고정. `init_model` 이어학습은 되나 클래스 수는 못 바꿈.
- **정정**: "OvR 이진기 점수 비교 문제는 선행연구 적다"는 틀림. **base rate가 달라 스케일이 어긋나는 건 표준 문제**고 해법(Platt scaling·isotonic regression on held-out)도 확립돼 있다. sklearn `CalibratedClassifierCV`로 바로 됨 — 새로 만들지 말 것.
- **우리 자리 2개**: (가) 모델 축 — 부스팅 트리로 트래픽 CIL(NN 무기가 안 넘어옴). (나) 문제 축 — **NN CIL 논문들은 "새 클래스 데이터+라벨이 주어진다"를 전제**하는데 우리는 그게 없다(게이트→클러스터→라벨→편입). **(나)가 더 강한 카드** — (가)는 "왜 NN 안 쓰냐"에 계속 시달린다.

### S0 클러스터 가능성 검증 — 자동 발견 실패  <!-- (2026-09-14) -->
- 배경: 게이트가 unknown을 걸러도 "새 클래스 N개"로 쪼개려면 클러스터링이 필요. CIL 본체 전에 이 가정부터 싸게 검증. 코드 `01_code/cluster_probe.py`(재학습 없음, 로딩이 비용 전부). 출력 `03_json/cluster_probe_w3.json`.
- 대상: week3 신규 34클래스 96,410 flow. 표준화→PCA 30차원(설명분산 70.2%)→MiniBatchKMeans k변주 + HDBSCAN. 라벨은 채점에만 사용.
- **결과: ARI 2.4~5.1 = 무작위와 동급.** 클러스터 분할이 실제 앱 분할과 사실상 무관.
- **내가 박아둔 판정기준이 결함이었다**: `purity ≥ 70 → PASS`로 찍혔는데 그건 **k=68(실제 34의 2배)로 쪼개서 얻은 값**. purity는 k를 늘리면 자동으로 오른다. 게다가 **fc_online 혼자 51%**라 무지성 baseline이 이미 purity 51. → 기준을 **ARI(우연일치 보정)** 기반으로 교체하고 `BALANCE=1`(클래스 균등화)·baseline 출력·purity_lift를 추가.
- **두 방향 동시 파손**: 과분할(fc_online이 7조각, 으뜸 클러스터 점유 9.5%) + 저분할(`c7 = orca 37.5% + cursor 27.4% + chatgpt_classic 22.1%` — 전부 Electron/CEF). ③행동중첩이 비지도에서 그대로 재현.
- **대조군(week3 known 60클래스)도 ARI 7.1로 비슷** → 처음엔 "피처공간 자체 문제"로 해석했으나 **철회**: 대조군에 svchost(42만)·system(25만)·servicemapcollector(10만)가 들어 있었다. 이들은 여러 앱 트래픽을 대신 나르는 프록시라 **원리적으로 클러스터가 안 생긴다.** 실앱 필터를 안 건 설계 누락.
- **살아남은 경로**: HDBSCAN(mcs=50) — 36.4% 버리고 127조각, **clustered purity 91.8 / homogeneity 87.2 / completeness 32.1**. "새 앱 34개 자동 발견"은 실패지만 **"사람이 볼 양을 flow 96,410개 → 클러스터 127개로 줄인다"(760배)**는 성립 가능. 단 fc_online 51% 지배 상태의 수치라 균등 조건 재확인 필요.
- **왜 지도학습은 되고 비지도는 안 되나**: 지도학습은 정답을 보며 "앱 구분에 중요한 축"을 고른다. 클러스터링은 299축을 동등하게 놓고 거리를 재서 정체성과 무관한 축(총 전송량·세션 길이)이 거리를 지배한다. 인물사진을 배경색으로 묶는 격.
- **미해결 설계 결함 5개**(결론 유보 사유): ① 피처공간 미검증 — **base 모델의 raw margin 공간에서 클러스터링해야** 맞다(NN novel class discovery의 표준). ② PCA 30 근거 없음(30% 버림). ③ 대조군 클래스 수 불일치(34 vs 60). ④ 평가기준 과도 — fc_online 7조각이 실제로 7가지 행동이면 라벨이 거친 것. ⑤ HDBSCAN 파라미터 미탐색.
- **결론**: 지금 숫자로 "클러스터링 경로가 죽었다"고 말할 수 없다. **"표준화 원피처+PCA30 공간에서는 안 된다"까지만** 참.

## 다음 할 일
- [ ] **S0c: base 모델 raw margin 공간에서 클러스터링** — 결함 ①. 여기서도 ARI 낮으면 그때 경로 폐기 판정
- [ ] S0b: 실앱 필터 + 균등화 + PCA 변주(30/100/없음) + 대조군 클래스 수 맞춤
- [ ] 게이트 그룹집계 재설계 — **basename이 곧 5-tuple이라 "같은 pcap 묶기"는 그룹 크기 1**. 프로세스명은 정답이라 반칙. 쓸 수 있는 키는 (목적지 호스트+시간창) 또는 (client_ip+시간창)뿐
- [ ] 신규클래스 편입 CIL — 탐지된 unknown을 실제 클래스로 학습(One-vs-rest/부분재학습), 망각 측정. **week3 UNIFIED 통일본이 전제** ([[UNIFIED 정제 기준 통일]])
- [ ] openness 곡선(known 90/80/70%), OpenMax·contrastive.
- [ ] 적응비율 더 촘촘히(0.1/0.25) — 소량 적응만으로 회복되나(실배포 효율).

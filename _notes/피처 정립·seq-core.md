# 피처 정립·seq-core

## 핵심 요약
seq789(앞100패킷·789 행동피처)를 **정본 seq-core 299**(앞30패킷·6그룹)로 압축하고, 다시 **compact core N100/N60**로 경량화. 근거 기반 압축(진단→truncation→ablation→expand→select)이라 성능 손실 없음. 최종 full BV(LightGBM·B=15)에서 **299→100→60으로 5배 줄여도 3데이터셋 전부 ±0.4 이내 동률**, CSTNET·LAB은 오히려 소폭 상승 → 압축 정당성 입증. 입력은 행동피처(seq)뿐, 정체성(SNI·IP·포트)은 라벨링/노이즈필터에만. 관련: [[앙상블 Bias-Variance·튜닝]], [[노이즈 정의·정제 파이프라인]], [[PRISM(LAB) 데이터·진단]]

## 기록

### 피처 정립 5단계 (789 → 299 → N100/N60)  <!-- (2026-08-20) -->
전량 클린·단일 split·가벼운 자(uniform LightGBM) 스크리닝, macro-F1 기준.

| 단계 | 결정 | 근거 |
|---|---|---|
| 진단 importance | — | burst≈0(거의 죽음), chan+cum 지배, 상위피처 앞20패킷 집중(중앙값 3번째) |
| truncation | 앞 30패킷(K30, 789→299) | 무릎점. 손실 0, CSTNET/LAB은 상승(뒤 70패킷=노이즈). K15부터 붕괴 |
| ablation | 6그룹 전부 유지(burst 포함) | burst 빼면 2/3 데이터셋 나빠짐(Cipher −0.03·CSTNET −0.21·LAB +0.05), 10피처뿐 → 유지 |
| expand | 새 후보 6그룹(34피처) 미채택 | 전부 개선 0 이하 → chan/cum이 raw 담아 중복 = core 충족성 증거 |
| select | compact = N100(희소보존) + N60(경량) | N40도 full과 거의 동일. LAB 희소클래스는 피처 많을수록 유리 → N100 최고 |

- **seq-core 299 구성**: flow(29 통계요약) + chan(150=앞30패킷×5채널) + cum(60) + hist(40) + quant(10) + burst(10).
- **compact 선택**: 299 importance 3데이터셋 평균 통합랭킹 상위 N. 리스트 = `02_dataset/core100_features.txt`·`core60_features.txt`·`core_ranking.txt`.
- 상세 문서 = `05_docs/FEATURE_PLAN.md`.

### 인프라 모듈화 + 라벨 오염 정제  <!-- (2026-08-20) -->
- 피처조립 `features.py`, 로드/라벨 `seqdata.py`, 측정 harness `feat_harness.py`로 분리. bias_variance·tune도 이 모듈 쓰게 리팩터(회귀테스트 bit-exact).
- 라벨 오염 제거: Cipher `chacha20`(1000행) 제외 → 도메인 42→**41**. LAB `unknown`(라벨 없음 7989행) 제외.
  - **[정정 2026-08-26]** chacha20은 암호명 오염이 아니라 **`none_aes256gcm_getpocket.com`이 오라벨된 것**(SNI가 assets.getpocket.com로 확증, aes128 getpocket과 동일 분포). source(X:)는 clean 41도메인, 내 추출 seq에서만 폴더명이 chacha20으로 깨져 있었음(추출코드 버그 아님, 상류 폴더명 glitch, 1/123개만). **수정**: seq csv 라벨 chacha20→getpocket.com 재라벨 완료 → getpocket 2000→**3000**(3암호), **41도메인·123,000 flow 전량 valid**(122,000 아님). DOMAIN_EXCLUDE=chacha20은 이제 no-op(재실행 시 자동 반영). 기존 재튜닝·full BV 표는 122,000/getpocket2000 기준(영향 ~0.8%, 헤드라인 불변).
  - **Cipher 재라벨 BV 재실행(2026-08-26)**: 수정 데이터(123,000)로 LightGBM BV 재계산 → 299 F1/Acc **99.34/99.34**, N100 **99.36/99.36**, N60 **99.30/99.30**. 기존(122k)과 ±0.02 → 예상대로 변화 미미. `bias_variance_core_*.json`의 CipherSpectrum 갱신됨(CSTNET·PRISM은 merge 보존).

### 정본 299 재튜닝 (Optuna)  <!-- (2026-08-20) -->
- 8/13 튜닝은 789 기준이라, 피처 바뀐 정본 299 위에서 재튜닝. 도구 동일, 대상 피처만 변경. `03_json/boosting_best_params_core.json`.
- val macro-F1: Cipher LGB **99.47**/XGB 99.34, CSTNET 90.62/89.53, LAB 72.09/73.02. 789 대비 Cipher +0.98·LAB +0.77(CSTNET −0.59) → 압축이 성능 손해 없음.

### 최종 full BV — 정본 299/N100/N60 실측  <!-- (2026-08-23) -->
3설정 × 3데이터셋 × LightGBM · B=15, core 튜닝값. 3설정 동일 데이터(클래스≥15·split·부트스트랩) → 피처만 다른 통제비교.

**LightGBM macro-F1 / Accuracy:**

| 피처설정 | Cipher(41) | CSTNET(120) | LAB 전량(76) |
|---|---|---|---|
| seq-core 299 | 99.34 / 99.34 | 90.78 / 92.77 | 70.15 / 88.90 |
| N100 | 99.34 / 99.34 | **91.17** / 92.93 | 70.11 / 88.78 |
| N60 | 99.31 / 99.31 | 91.15 / 92.91 | **70.54** / 88.42 |

- **결론**: 299→60으로 피처 5배 줄여도 ±0.4 이내. CSTNET·LAB은 N100/N60이 299보다 소폭 높음 → compact core 정당성 확정.
- LAB는 **전량 603,502행·76클래스**(≥15 필터). macro-F1 70%/Acc 89% — 불균형·행동중첩 탓, 실앱은 잘 맞힘. → [[PRISM(LAB) 데이터·진단]] 희소클래스 진단으로 연결.
- **GPU 삽질**: LightGBM GPU(OpenCL)로 Cipher/CSTNET은 완료됐으나, LAB 전량 603k·다중클래스에서 `best_split_info.left_count > 0` 체크 크래시(3설정 전부). CPU면 안 나는 GPU 버그 → **LAB만 CPU로 재실행**(설정당 4~20시간). 큰 다중클래스 전량은 GPU LightGBM 불가.
- 출력 = `03_json/bias_variance_core_{299,N100,N60}.json`.

### 타 접근(부록B: 집계피처+XGBoost+SHAP)과 방법론 대조  <!-- (2026-08-28) -->
- 랩 내 다른 산출 프로토콜(슬라이드)과 비교. 저쪽 = **XGBoost(depth 12·n_est 450·lr 0.065·조기종료 val50) + CICFlowMeter류 집계피처(Fl_rate·BCU/BF/BB 히스토그램·d_i) + SHAP+gain consensus 선택 + 5-tuple 그룹split**, 타깃 도메인. 성능 숫자는 슬라이드에 없어 프로토콜만 비교.
- **내가 배울 점**: ① **SHAP+gain consensus** 선택(gain은 고빈도분할 피처 과대평가, SHAP이 편향 적음) → 내 compact core를 gain 단일 대신 SHAP 얹으면 견고. ② 5-tuple 그룹split 명시(내 seq는 flow당 1행이라 원래 누수 없음).
- **내 차별/우위**: 시퀀스 피처(chan/cum, 패킷 순서 담음) vs 저쪽 집계(순서 없음) — truncation으로 순서 지문 입증. depth 6 근거(probe로 깊이 무제한=depth6 Acc동일, 추론만 느림) vs 저쪽 depth 12 근거 불명(과적합·추론느림 위험). 3데이터셋 평균 선택·압축스토리(789→299→N60).
- **하이퍼파라미터 Acc 영향**: depth 12 vs 6, n_est/lr 차이는 Acc **≤1~2%p, 깊은쪽 우위 보장 없음**(내 튜닝 이득도 +0.5~1.4뿐). Acc 진짜 변수 = **피처·데이터·누수**지 이 노브 아님. 저쪽은 과거 "test를 조기종료 eval에 넣던 누수" 있었고 고침 → **누수 수정이 하이퍼파라미터보다 Acc에 큼**.
- **후속 아이디어(강력)**: 같은 데이터셋에 **집계피처 vs 시퀀스피처(seq-core) 정면 비교** — 순서정보의 가치를 정량화. 논문 한 방. 관련: [[앙상블 Bias-Variance·튜닝]](depth probe).

## 다음 할 일
- [ ] (후속) 집계피처 vs seq-core 정면비교 실험 (같은 데이터·같은 모델, 순서정보 가치 정량화)
- [ ] (검토) compact core 선택에 SHAP 지표 추가 (gain 단일 → SHAP+gain consensus)
- [ ] PPT S8~10·S19를 299 실측표로 갱신 + N100/N60 압축표 추가. 구글시트 행도. per-class F1 확보.
- [ ] compact core 전이강건성 검증(현재 스크리닝 성능만, 전이는 미검증) — VPN/Tor·교차전이에서 299 vs N60 비교.
- [ ] LAB 희소클래스 진단(보류 해제) — confusion matrix로 데이터부족/불균형/행동중첩 구분.

# 앙상블 Bias-Variance·튜닝

## 핵심 요약
seq789(패킷 행동 수치피처)로 6개 트리모델의 0-1 loss bias/variance를 부트스트랩(B=15) 실측 분해. 단일→Bagging에서 variance 급감, Boosting(LightGBM·XGBoost)이 bias·variance 최저. CatBoost는 통일 params에선 열세지만 튜닝하면 회복 → "열세는 모델이 아니라 params 탓". LightGBM은 추론 느림(leaf-wise 깊이 + predict 구현). 이건 "왜 부스팅인가" 근거보강(IME654 곁가지)이지 논지 자체는 아님. 관련: [[STTabNet·VPN·Tor 보편분류]], [[노이즈 정의·정제 파이프라인]]
- **현재 상태(2026-08-23)**: 피처 정본이 seq789 → **seq-core 299**(앞30패킷)로 바뀜. 정본 299/N100/N60 최종 full BV 완주 → 성능표·상세는 [[피처 정립·seq-core]]로 이관. 이 노트의 789 기준 수치는 정립 이전 근거(부스팅 우위·bias/var 분해 방법론)로 유지.

## 기록

### Bias-Variance 6모델 × 3데이터셋 (통일 params)  <!-- (2026-08-05) -->
- 방법: 부트스트랩 B=15 반복학습 → main=최빈값, bias=mean(main≠정답), var=mean(P≠main), err≈bias+var (Kohavi-Wolpert 0-1 loss). AC·macro-F1·추론시간(IT_s)·mem 측정.
- 피처=seq789(전 수치, 범주형 인코딩 이슈 없음). 통일 params(공정비교): lr .05·트리300·reg_lambda 10·colsample .8, LightGBM/XGBoost max_depth=6.
- 결과(macro-F1): **LightGBM 최고** — CipherSpectrum 98.0 / CSTNET 88.9 / LAB 65.4.
- 세 데이터셋 다 **단일→RandomForest에서 var 급감**(Cipher 3.63→1.07, LAB 12.95→5.65, CSTNET 17.86→6.69), Boosting이 bias·var 최저.
- 관련 파일: `01_code/bias_variance.py` + `run_bias_variance.sh`, `03_json/bias_variance_results.json`

### CatBoost 추가 — 통일 params 열세  <!-- (2026-08-06) -->
- CatBoost macro-F1: Cipher 93.5 / LAB 45.0 / CSTNET 78.0 = 전부 최하위. bias 높음(언더피팅 경향), var는 낮음.
- 원인: CatBoost는 대칭트리+ordered boosting이라 자기 튜닝값에 민감 → LightGBM/XGBoost용 통일값이 불리.

### Optuna 튜닝 — CatBoost 회복  <!-- (2026-08-09) -->
- 부스팅 3종만 튜닝(트리계는 통일값 유지). train 내부 홀드아웃 macro-F1 최적화(BV test 누수 방지), 60 trials.
- **CatBoost Cipher 93.5 → 97.4로 회복** → "열세=params 탓" 검증. LightGBM/XGBoost는 튜닝 이득 미미(이미 통일값 적절).
- CPU(LGB+XGB) ∥ GPU(CatBoost) 동시 실행으로 단축. **단 CatBoost GPU는 8GB VRAM(RTX3060)에서 다중클래스 OOM** — Cipher(42클래스)만 성공, CSTNET(120)·LAB OOM → CatBoost 튜닝은 Cipher만. XGBoost는 GPU(device=cuda) 가능.
- 관련 파일: `01_code/tune_boosting.py`, `run_tune_boosting.sh`/`run_tune_xgbgpu.sh`, `03_json/boosting_best_params.json`

### 추론속도(IT_s) probe — LightGBM은 왜 느린가  <!-- (2026-08-09) -->
- 같은 데이터/params, max_depth만 바꿔 predict 시간 격리(Cipher).
- LightGBM 무제한(leaf-wise, 실측깊이 max38) predict 42.1s → depth6 27.0s (−36%). depth6도 XGBoost depth6(2.65s)의 **10배**.
- 결론: max_depth는 36%만 설명, 나머지는 **LightGBM 다중클래스 predict 구현 오버헤드**. depth6가 정확도 손해 없이(98.49) 추론 1.5배↑ + 학습도 빠름.
- 배포 관점: 정확도 LightGBM > 추론속도 XGBoost (트레이드오프).
- 관련 파일: `01_code/probe_lgbm_it.py`

### 추론 느림 원인 = 캐시 miss 확정 (cachegrind)  <!-- (2026-08-25) -->
- 앞 probe의 "구현 오버헤드"를 cachegrind로 규명. 동일조건(Cipher seq-core 299, depth6, 300×41트리, 단일스레드) predict만 격리. 코드 `01_code/probe_cache.py` + `run_probe_cache.sh`.
- **속도**: LightGBM predict 2111.7µs/샘플 vs XGBoost 167.8µs = **12.6배 느림**. (반대로 학습은 LightGBM 440s < XGBoost 1590s = 3.6배 빠름 → "LightGBM=학습 최적화 / XGBoost=추론 최적화" 트레이드오프가 한 실험서 양방향 확인.)
- **캐시(cachegrind)**: 명령어 수는 거의 같음(16.6B vs 17.6B, LightGBM이 오히려 적음) → 계산량 문제 아님. 근데:
  - D1 miss rate 24.1% vs 4.3% (5.6배), **LLd miss rate 20.2% vs 0.4% (50배)**, 실제 RAM 왕복(LL misses) 1.19B vs 28.8M (**41배**).
  - → LightGBM predict는 트리 노드를 메모리 비지역적으로 긁어와 캐시 miss 폭증 = memory-bound. XGBoost는 캐시 친화 배치로 거의 hit.
- **결론**: 추론 느림의 주범은 트리 깊이·계산량이 아니라 **메모리 접근 패턴(캐시 지역성)**. 가설→데이터로 확정. perf 미설치라 valgrind cachegrind로 측정(가상 캐시모델이나 41~50배 차이라 결정적).
- 관련 파일: `01_code/probe_cache.py`, `04_logs/probe_cache_wd/cg_*.out`

### 클린 bias-variance + 클린 튜닝 (08.13 연구계획 PPT)  <!-- (2026-08-13) -->
- `심규상_260813_연구계획.pptx`로 정리 — STTabNet 제거, **클린 데이터셋만**, BV 표에 F1/Acc/bias/var/err/학습s/추론s/mem 전체 지표.
- **클린 BV macro-F1 (LightGBM 최고 재확인)**: Cipher 98.03 / CSTNET 88.89 / LAB week2(클린·65클래스) 68.09 / LAB week3(클린·79클래스) 67.33.
  - LAB는 노이즈(DNS/CDN 30%) 제거로 통일-params 대비 5모델 전부 F1 +2.7~4.3, bias −3~5 동반 하락.
  - 공통 패턴 유지: 단일→Bagging에서 var 급감, Boosting이 bias·var 최저.
- **주차 재현성 (week2 vs week3, 클린-클린)**: LightGBM 주차차 −0.76로 가장 안정(부스팅이 주 변화에 강건). 절대값 하락은 대부분 클래스 수(65→79) 아티팩트 → 공통클래스 통제비교로 순수 측정 예정.
- **클린 부스팅 튜닝 (Optuna val macro-F1, 60 trials)**: Cipher LGB **98.49**/XGB 98.14/Cat 97.41; CSTNET LGB **91.21**/XGB 90.22(CatBoost GPU OOM 제외); LAB week2 클린 XGB 71.71, LGB **71.32**(완주). 세 데이터셋 모두 val 기준 LightGBM 최고.
- 관련 파일: `03_json/boosting_best_params.json`·`bias_variance_lab_pipeclean.json`·`bias_variance_week3_pipeclean.json`. 데이터는 이제 `06_data/`(재편). 관련: [[노이즈 정의·정제 파이프라인]], [[PRISM(LAB) 데이터·진단]]

### 튜닝반영 BV 완주 (통일 vs 튜닝) + 동일조건(CPU) 원칙  <!-- (2026-08-18) -->
- `TUNED_PARAMS=boosting_best_params.json`로 BV 재실행 → `03_json/bias_variance_tuned_results.json`. 트리계(DT/RF/ET)는 통일값, 부스팅만 튜닝값. **CatBoost 전면 제외**(다중클래스 GPU OOM + 최하위), 5모델.
- **동일조건 수집 원칙(선배 지적)**: 보고 표(F1/Acc/bias/var/err/학습s/추론s/mem)는 전 모델 **CPU 단일 디바이스**로 통일. GPU는 튜닝 *탐색* 때만 썼고 하이퍼값은 디바이스 무관 → CPU BV에 넣어도 공정. 8GB VRAM에선 CatBoost 다중클래스 GPU OOM이라 공통 디바이스=CPU뿐. XGBoost 튜닝값에 device/tree_method 없음 확인(누수 X). `bias_variance.py`는 XGB_GPU 미설정시 CPU가 기본이라 원본 통일표도 이미 전부 CPU였음.
- **튜닝 효과 (동일조건인 Cipher·CSTNET만 정확)**: Cipher LGB 98.03→**98.59**(+0.56)·XGB +0.22; CSTNET LGB 88.89→**90.32**(+1.43)·XGB +0.87. 트리계는 튜닝 안 해 불변 → 파이프라인 정합 확인.
- **최고 모델**: Cipher·CSTNET = LightGBM. **LAB만 macro-F1 최고가 XGBoost(70.04 > LGB 69.08)** — 단 bias·var·err는 LAB에서도 LightGBM이 낮음 → "부스팅 2강, 지표별 우위 상이"로 서술. 추론속도는 XGBoost가 LightGBM의 3~9배(Cipher 50 vs 334µs) → 배포=XGBoost/정확도=LightGBM 트레이드오프 재확인.
- **노이즈 파일 차이로 LAB 65→64클래스**: 옛 통일표는 `lab_pipeline_noise_basenames.txt`(prism04 조인, 489k, 65클래스), 이번 튜닝은 `lab_seqmeta_noise_basenames.txt`(seqmeta 규칙, 479k, 64클래스). 튜닝도 seqmeta라 튜닝값↔튜닝BV는 정합. → **노이즈 정본은 seqmeta로 통일 권장**, 옛 65클래스 통일표는 폐기 대상. (그래서 LAB의 튜닝 Δ와 트리 델타는 기준선 불일치로 부정확 — Cipher/CSTNET Δ만 신뢰.)
- **클린 vs 더티 (튜닝반영, LAB)**: 더티=노이즈 제거 안 함(`LAB_NOISE_FILE` 빼고 재실행) → `03_json/bias_variance_tuned_dirty.json`(Cipher/CSTNET는 노이즈≈0이라 클린값 복사). LAB 클린이 더티보다 **5모델 전부 F1 +2.6~3.4, err 대폭↓**(LGB err 15.35→11.67). 튜닝값 넣어도 노이즈 정제 가치 유지. (클린 64 vs 더티 62클래스라 완벽 통제는 아니나 방향 일관.) 관련: [[노이즈 정의·정제 파이프라인]]
- **삽질**: `run_bv_tuned.sh` 버그 3개 수정 — ① LAB에 `LAB_NOISE_FILE` 누락(더티로 돌 뻔), ② `LAB_LABEL_MAP` default가 폴더 재편(`06_data/`) 후 `06_data/02_dataset/...` 잘못 참조 → FileNotFoundError(실제는 루트 `02_dataset/`), ③ GPU 플래그 차단·CatBoost 데이터셋별 정합. 인라인 실행 시 `BASE=$(pwd) python $BASE/...`는 셸 전개 타이밍상 `$BASE`가 빈 값 → 상대경로로 우회.
- 서브샘플: LAB은 61만행이라 `BV_SUB=200000`으로 잘라 씀(전량 아님, 옛 통일과 동일). 5모델 동일 서브샘플·부트스트랩셋이라 비교는 공정.
- 관련 파일: `03_json/bias_variance_tuned_results.json`·`bias_variance_tuned_dirty.json`, `01_code/run_bv_tuned.sh`

### raw(정제 안 함) BV — 정본 299·전량 (노이즈 제거 가치 재확인)  <!-- (2026-09-03) -->
- PRISM week2 raw(노이즈필터 없음, background 포함) 전량 869,700행·**79클래스**, 5모델, seq-core 299, B=15. `03_json/bias_variance_raw_w2_299.json`.
- 결과 F1: DT 63.82 · RF 62.80 · ET 63.37 · **LightGBM 64.85** · **XGBoost 65.92**.
- vs clean(76클래스): LightGBM ~70-73 → **raw가 ~5-8점 낮음** = 노이즈 제거 가치 정본 299·5모델·전량서 재확인(옛 789 더티 65.83과 정합).
- week3 raw는 **OOM으로 중단**(2.27M·113클래스, RF 44GB→ET에서 62GB 초과 kill). DT/RF만 저장. 부스팅만 재실행 가능하나 **결론 안 바뀌어 보류**(사용자 결정 2026-09-03).
- 삽질: 전량 raw는 2.8일(week2만) + RF/ET가 대용량서 메모리 폭식(ET 28GB, RF 44GB). raw BV는 CIL 아니라 baseline/완결성 결과. 관련: [[live-traffic-classifier-plan(memory)]], [[노이즈 정의·정제 파이프라인]]

### UNIFIED 기준 재튜닝 — depth 4→12, bias 35% 감소  <!-- (2026-09-28) -->
- 정제 기준이 [[UNIFIED 정제 기준 통일]]로 바뀌면서 **하이퍼파라미터가 낡았다**: `boosting_best_params_core.json`은 옛 76클래스·603k 기준(val 72.089)인데 새 데이터는 44클래스·186k에 svchost·system도 빠져 훨씬 쉬운 문제.
- 근거는 **bias 지배**였다. 옛 params로 UNIFIED BV: bias 4.91 / variance 1.54 — variance가 이미 낮으니 데이터·앙상블로는 못 줄이고, **모델 용량 부족(max_depth=4)이 bias로 남는다**는 가설.
- 재튜닝(Optuna 40 trials, 6.5시간, `TUNE_TAG=_unified`, 출력 `03_json/boosting_best_params_unified.json`):

| | 옛 `_core` | 새 `_unified` |
|---|---|---|
| max_depth | **4** | **12** |
| num_leaves | **23** | **244** |
| n_estimators | 1200 | 1100 |
| learning_rate | 0.0104 | 0.1009 |
| reg_lambda | 0.175 | 3.18 |
| val_macro_f1 | 72.089 (옛 데이터) | 91.183 (새 데이터) |

- **동일 조건 BV 비교(둘 다 UNIFIED 44클래스·B=15)**: F1 91.51→**92.47**(+0.96), Acc 95.09→**96.80**(+1.71), **bias 4.91→3.20(−35%)**, variance 1.54→1.79(+0.25), err 5.21→4.02.
- **가설 검증됨** — 얕은 트리가 bias의 주원인. variance가 조금 올랐지만 bias 감소분이 훨씬 커서 순이득.
- **대가는 추론 1.87배**(668→1,249 µs). 리프 23→244라 트리 순회가 길어짐. 학습도 1.61배(887→1,432s). 실시간 배포 관점에선 정확도↔속도 트레이드오프.
- **교훈**: 데이터셋 정의가 바뀌면 하이퍼파라미터도 같이 늙는다. 옛 튜닝값을 그대로 들고 가면 bias를 공짜로 떠안는다.
- 주의: 옛 val 72.089와 새 val 91.183은 **다른 데이터에서 잰 값이라 직접 비교 불가**. 튜닝 홀드아웃(train 내부 80/20 단일)과 BV(부트스트랩 15회)도 프로토콜이 달라 섞어 읽으면 안 된다.

## 다음 할 일
- [ ] XGBoost UNIFIED 튜닝 + BV — 옛 raw에서 XGBoost가 LightGBM보다 앞섰던 게(65.92 vs 64.85) 새 기준에서도 성립하나
- [x] 클린 데이터 튜닝 재실행 (Cipher·CSTNET·LAB 전부 완주)
- [x] 튜닝반영 BV — `TUNED_PARAMS`로 클린 BV 재실행 (3데이터셋 완주)
- [x] 튜닝반영 더티 BV (노이즈 정제 전) — 클린 vs 더티 대비 완료
- [x] 노이즈 정본 seqmeta로 통일 확정(LAB=64클래스), 옛 65클래스 통일표 [DEPRECATED] 마킹 (실제 정리는 /정리 시)
- [ ] PPT slide 8~11 튜닝버전 표(통일 vs 튜닝, 학습s는 B=15 합계라 /15 단위통일)
- [ ] 주차간 공통클래스 통제비교 (week2·week3 공통 앱만 같은 클래스셋)
- [ ] 교차 데이터셋 일반화 (학습 A→테스트 B) — 보편성 핵심 증거
- [ ] 5-fold 평균±표준편차로 엄밀화

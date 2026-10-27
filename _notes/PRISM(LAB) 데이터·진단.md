# PRISM(LAB) 데이터·진단

## 핵심 요약
LAB = 실환경 자체수집 트래픽(서버28 PRISM_week), 경로 `날짜/IP/App/process.exe/pcap`로 프로세스 라벨(task3). week2(2026.07.10~12)는 canonical 878,890 basename 확정. week3(07.20~24)는 신규 추출 2.43M flow→dedup 2.27M·123클래스. 시스템 프로세스(svchost 등)가 지배적이고 불균형 심함. 관련: [[노이즈 정의·정제 파이프라인]], [[앙상블 Bias-Variance·튜닝]]

## 기록

### canonical LAB 재현 (week2)  <!-- (2026-08-05) -->
- "고유 실세션 904,807" 정의: DoH 제외(session_stat L7=DoH) → endpoints+ts_first 중복제거 → 906,666. 라벨=session_stat task3(소켓-프로세스 실측).
- 우리 seq(146만)에 filename 조인 + basename 중복제거 + 클래스≥10 → **878,023행·85클래스**(904,807의 97%; 차이는 파일당 다중flow 단위차, 누락 아님).
- 키맵: `02_dataset/lab_canon_label.csv`(filename→task3, 878,890행).
- 시스템 프로세스 지배: svchost 32%·system 12% = 44%(이질적, 앱과 겹쳐 천장 낮음). 상위5=69% 불균형 → Acc 83이나 macro-F1 60대.

### 노이즈 2축 (LAB)  <!-- (2026-08-11) -->
- 프로세스라벨 노이즈: svchost·system·측정인프라(servicemapcollector·autolabellauncher) 제거 → 실앱 46클래스, 트리 macro-F1 64.7→75(+11).
- 파이프라인 노이즈: DNS/CDN/배경(seqmeta 규칙) 30% 제거 → +4. 두 축은 직교(라벨 정제 vs 세션타입 정제). 상세 [[노이즈 정의·정제 파이프라인]]

### week3 추출 (2026.07.20~24)  <!-- (2026-08-10) -->
- 서버28 `Week3` (5일치, ~2.43M pcap) 마운트 스트리밍 추출, `--label-depth 2`(App명, .exe 제거). errors 1.
- 2,431,364 flow → basename dedup 2,271,708 · 123클래스. week2와 성격 동일(system 지배). 라벨맵 `02_dataset/week3_label.csv`.
- **Stage3(dedup+class≥10)는 bias_variance --lab 내장**(라벨맵 join→drop_duplicates('bn')→vc≥10). week2와 유일 차이 = DoH 제외 위치(week2 canonical / week3 노이즈규칙), 결과는 둘 다 DoH-free.
- 관련 파일: `01_code/extract_pcap_seq_sni_v2.py`, `run_week3_bv.sh`

### 희소클래스 진단 도구 준비 (5-fold)  <!-- (2026-08-26) -->
- 배경: 최종 full BV에서 PRISM 전량 **76클래스**(≥15) macro-F1 70.2 / Acc 88.9 — Acc 높고 macro-F1 낮은 불균형 패턴 지속. [[주차 교차전이 week2-week3]]가 "희소 프로세스가 시점 드리프트 주범"으로 가리킴 → 진단 착수.
- 도구: `01_code/lab_rare_diag.py` — LAB week2 전량·seq-core 299, **stratified 5-fold out-of-fold** 예측 → per-class P/R/F1/support + 각 클래스 최다 오분류 대상 + F1↔log(표본수) 상관. 출력 `03_json/lab_rare_diag_299.json`.
- **왜 5-fold(≠B=15)**: B=15 부트스트랩은 예측만 안정화, 희소클래스 test 표본(고정 홀드아웃 ~5개)은 그대로. 5-fold는 모든 샘플이 test 1번 → 희소 coverage 3배 + 비용 절반(5 fit vs 15). 진단 목적엔 coverage가 병목이라 5-fold가 맞음.
- 판정법: F1↔표본수 상관 높으면 ①데이터부족/②불균형, 낮으면 ③행동중첩. 오분류가 특정 클래스 집중=③, 흩어짐=①, 큰 클래스 쏠림=②.
- memory: `lab-rare-class-diagnosis`(보류 해제됨).

### 희소클래스 진단 결과 — 주범 = ③행동중첩 (데이터부족 아님)  <!-- (2026-08-26) -->
- `lab_rare_diag.py` 5-fold OOF 완주: macro-F1 **73.01** / Acc **89.03** (76클래스). `03_json/lab_rare_diag_299.json`.
- **F1↔log(학습표본수) 상관 = 0.418**(중간-낮음) → 데이터 양이 성능 지배 안 함(①아님).
- **데이터 많은데 F1 처참** = ①부정 결정적 증거: socketlogger(train 2007, F1 4.3), autolabellauncher(3045, F1 11), visual_studio_code(1443, F1 38).
- **오분류가 의미적 "쌍둥이"에 집중**(③ 전형):
  - 측정인프라: socketlogger·autolabellauncher·flexnet → servicemapcollector(63~75%). = **PRISM 수집장치 자신**, 실앱 아님 → 제거 대상.
  - 시스템서비스: taskhostw·mousocoreworker·vgc·omadmclient → system(63~81%).
  - 앱패밀리: vscode↔visual_studio(62%), acrocef→chrome, acrobat→acrotray. 같은 엔진=행동 동일.
- **판정**: macro-F1 70대 = 모델 약점 아니라 **라벨공간에 행동쌍둥이 혼입**. 데이터 추가 무의미(①아님), 불균형②은 부차. **대응 = 측정인프라 제거 + 실앱 전용 서브셋**(과거 64.7→75 상승과 정합, [[노이즈 정의·정제 파이프라인]]). 정직 프레이밍: "실앱 고성능 / 시스템·측정인프라·엔진공유앱은 행동중첩 원리적 한계".

### 실앱 전용 서브셋 결과 — macro-F1 +10.5 (진단 입증)  <!-- (2026-08-28) -->
- `LAB_EXCLUDE_FILE=lab_noise_labels.txt`(75라벨: 측정인프라+시스템백그라운드) 제거 → 실앱만. week2, seq-core 299, 5-fold. `03_json/lab_rare_diag_realapp_299.json`.
- **실앱 44클래스: macro-F1 83.51 / Acc 94.44** (274,697행). vs 전체 76클래스 73.01/89.03 → **macro-F1 +10.5, Acc +5.4.** (과거 64.7→75 전례와 정합.)
- → 76클래스 70대 낮음의 주범 = **시스템·측정인프라 행동중첩** 확정(실앱 실력 아님). 제거 시 급등.
- **실앱 내 남은 저F1도 여전히 ③쌍둥이**(상관 0.526): nvidia app(39)→chrome, visual_studio_code(1443,F1 42)→visual_studio(IDE쌍둥이), python(17)→xshell, acrobat/acrocef→chrome(Chromium임베드), ms_365_copilot(1258)→onedrive(MS제품군), **riot_client↔riotclient(같은앱 라벨변종)**. 대부분 실앱은 F1 80~99.
- 정직 프레이밍 완성: **"실앱 고성능(83.5), 낮은 건 원리적 행동중첩(시스템서비스·엔진공유앱·앱변종)"** — 데이터 탓 아님.
- 부수: chatgpt↔codex, spotify↔notion 소량 혼동(둘 다 실앱, F1 80+).

### week3 진단 — 주차 재현성 (패턴 성립, 강도 다름)  <!-- (2026-08-29) -->
- week3 전량 5-fold(전체 + 실앱). `03_json/lab_rare_diag_week3_{299,realapp_299}.json`.

| | 클래스 | macro-F1 | Acc | 상관 |
|---|---|---|---|---|
| week2 전체 | 76 | 73.01 | 89.03 | 0.42 |
| week2 실앱 | 44 | 83.51 | 94.44 | 0.53 |
| week3 전체 | 109 | 65.21 | 84.57 | 0.56 |
| week3 실앱 | 74 | 68.89 | 90.61 | 0.66 |

- **방향 재현**: 두 주차 다 실앱만 하면 macro-F1↑·Acc 큰폭↑(week3 84→90). 시스템/측정인프라가 macro-F1 깎는 것 week3도 동일.
- **강도 차이**: week3 상승폭 +3.7(week2 +10.5), 실앱 절대값 68.89(week2 83.51). 원인 = week3 실앱 **74클래스**(week2 44) 세밀·신규앱多 → 희소·쌍둥이 증가. week3 상관 0.66(week2 0.53) → ①데이터부족·②불균형 영향이 week3서 더 큼.
- **결론**: 시점 넘으면 ③행동중첩뿐 아니라 **①신규 희소앱**도 커짐 → [[주차 교차전이 week2-week3]] 드리프트(−32)의 원인("희소·신규 클래스")과 정합. 재현성은 방향은 있으나 클래스 수 아티팩트로 절대비교는 주의.

### 라벨 오염 3종 — "신규 클래스" 목록이 지저분하다  <!-- (2026-09-14) -->
- week3 "신규 32클래스"(week2에 없고 flow≥50)를 뜯어보니 진짜 신규는 **15개 안팎**이었다.
- **(a) 라벨 표기 변형 = 가짜 신규**: `chrome`(w3 197)인데 week2에 `google_chrome` 124,181 존재. `riot client`(81) vs week2 `riotclient` 30,950/`riot_client` 255. `nexon_game_manager`·`nexon_game_security` vs `nexonplug` 23,685. `cefproczf`·`acrocef`(둘 다 CEF 헬퍼).
- **(b) MIN_FLOW 임계 부작용**: week2에 있었지만 50 미만이라 "신규" 판정 — zoom(w2 3→w3 10,559), python(30→310), smartscreen(31→300), winword(2→74) 등 10개. **처음 등장이 아니라 사용량 급증**이다.
- **(c) 시스템·인프라 5개**: smartscreen·sihclient·lockapp·startmenuexperiencehost·ahnlab_safe_transaction. 실앱도 아닌데 신규 클래스로 세고 있었다.
- **★ fc_online 의혹**: week2 `fclauncher` 8,304→w3 19로 급감, `fczf` 469→0 소멸, 대신 `fc_online` 0→**49,225** 급증. **라벨 이름이 바뀐 것으로 강하게 의심**(zf = 넥슨 FC 내부 태그로 보임). 그런데 fc_online이 S0 클러스터링 데이터의 **51%**라 가짜 신규면 그 실험 전체가 무의미해진다. 사용자 확인 필요.
- **정체 불명**: `nai8w8~v`(w3 5,659) — DOS 8.3 축약명이라 원본 불명인데 신규 실험의 6%.
- **CIL 직결**: `chrome`을 신규 클래스로 편입하면 모델이 이미 아는 `google_chrome`과 거의 같은 트래픽을 두 클래스로 배운다 → 옛 클래스 성능 하락 → **그걸 "망각"으로 오측정**한다. 신규 목록 정리는 CIL의 선결 조건.
- **해소**: [[UNIFIED 정제 기준 통일]]의 `product/` 매핑이 이 병합표를 이미 갖고 있다(프로세스 44 → 제품 25). 새로 만들 필요 없음.

### UNIFIED 44클래스 진단 — 남은 오차의 27%가 "같은 제품군"  <!-- (2026-09-23) -->
- `lab_rare_diag.py` 5-fold OOF, UNIFIED 프로세스 44클래스 185,971세션. `03_json/lab_diag_unified_w2.json`.
- **macro-F1 92.78 / Acc 95.44** (BV 단일split 91.51/95.09와 정합, OOF가 약간 높은 건 정상).
- **F1↔log(학습표본수) 상관 0.395** — 데이터양이 절반도 설명 못 함. ③행동중첩 지속.
- **같은 제품군 내부 혼동 = 총 오분류의 27.4%**(2,333/8,504). **각 클래스의 최다 오분류 대상 1개만 센 하한**이라 실제로는 더 크다.

| 혼동쌍 | 건수 | 정체 |
|---|---|---|
| codex ↔ chatgpt | 480+434=914 | 둘 다 OpenAI 데스크톱, 같은 엔드포인트 |
| leagueclient ↔ riotclientservices | 621+282=903 | 같은 게임 클라이언트 두 프로세스 |
| msedge → msedgewebview2 | 190 | 같은 Chromium 엔진 |
| onedrive.sync.service → onedrive | 96 | OneDrive 형제 |
| league of legends → leagueclient | 88 | Riot 형제 |
| remoting_host → chrome | 27 | Chrome 원격 데스크톱 호스트 |

- 최저 F1: remoting_host 71.4 / nvidia overlay 72.2(n=23) / **chatgpt 79.1** / updater 81.5(n=16) / msedge 85.6. 표본 부족은 3개(updater 16·nvidia overlay 23·onedrivesetup 28)뿐이고 **나머지는 데이터가 충분한데도 틀린다**.
- **제품 25 병합으로 Riot(~1,036)·Edge(190)·OneDrive(108)·Office(38)는 사라지지만 최대쌍 codex↔chatgpt(914)는 제품 관점에서도 별개 클래스로 남는다** — 제품 병합 이득이 F1 +1.34에 그친 이유.
- **판정**: 튜닝으로 뚫리는 부분(bias)과 원리적 천장(같은 라이브러리·같은 엔드포인트)이 공존. 후자는 모델 문제가 아니라 **라벨 정의 문제**.

## 다음 할 일
- [x] 앱패밀리 병합 → [[UNIFIED 정제 기준 통일]]의 제품 25클래스로 해소
- [ ] `fclauncher/fczf`(w2) = `fc_online`(w3) 동일 게임인지 확인 — 신규클래스 실험의 51%가 걸림
- [ ] `nai8w8~v` 정체 확인(8.3 축약명 원본)
- [ ] week2·week3 공통클래스로 통제 진단 (클래스 수 아티팩트 제거한 순수 주차 비교)

# STTabNet·VPN·Tor 보편분류

## 핵심 요약
STTabNet = 시퀀스 stream(Conv1d 패치→Transformer, mask-aware) + 표형 stream(비선형 tabular 인코더) → gate 융합. 정체성 피처(SNI·IP·5-tuple) 없이 패킷 행동만으로 분류. CipherSpectrum 도메인 42분류 macro-F1 91.9. ISCX-VPN/Tor로 외부 확장 → **이진(은닉여부)은 잘 되나 다중분류(app/service)는 붕괴**(pcap 수 부족+극단 불균형). 관련: [[앙상블 Bias-Variance·튜닝]], [[노이즈 정의·정제 파이프라인]]

## 기록

### 모델 구조·버전 (CipherSpectrum)  <!-- (2026-08-11 정리) -->
- seq stream: Conv1d 패치임베딩 → 위치임베딩 → Transformer(pre-LN, nhead4) → mask 평균/attention pooling. tab stream: Linear(x)+Linear(sin x)→SiLU. gate: features*(1+gate) residual.
- v1 83.3 → v2(mask·residual gate·채널5·정석 train/val/test) 91.6 → v3(채널6·stride1·3layer·attention pool) 91.9.
- 관련 파일: `01_code/sttabnet.py`, `train_cipherspectrum_sttabnet_v2.py`

### ISCX-VPN/Tor 추출  <!-- (2026-08-10) -->
- 원본 pcap = 서버99 `X:\data-8t\21_ISCX-VPN-2016`·`22_ISCX-TOR-2016`. 읽기전용 마운트 스트리밍 추출.
- 추출코드 견고화: `--timeout`(대용량 P2P), `--cap-packets`(초대용량 -c), truncated pcap도 파싱분 유지, errors.log. → VPN 30.7만 flow·Tor 4.4만, **에러 0**.
- STTabNet `--label-mode {application|encapsulation|service}` 추가(폴더명 `{encap}_{service}_{app}` 파싱).

### VPN/Tor 결과 — 다중분류 붕괴  <!-- (2026-08-10) -->
- 이진 encapsulation(은닉 여부): VPN 65.4 / Tor 94.0 macro-F1 — 잘 됨.
- 다중분류: VPN application 11.6 / service 21.7, Tor application 14.6 / service 18.9 = **랜덤 수준 붕괴**.
- 원인: ISCX-VPN 총 139 pcap/40폴더 = 클래스당 1~4개뿐 → pcap 그룹분할이 클래스 굶김 + 극단 불균형(Tor nonTor Browsing 75%).

### 관련연구 조사 — 신규성 위치  <!-- (2026-08-11) -->
- ET-BERT(WWW2022, TLS1.3·SNI없이), FS-Net, Path Signature+LSTM 등 **행동시퀀스 분류는 이미 확립된 분야**. 핵심 아이디어는 신규 아님.
- 차별점 후보: **보편성/교차 데이터셋 일반화**(분야 약점), **실측 라벨 LAB 데이터셋**, **엄밀 ablation**, seq+tabular 융합 이득. → "새 딥모델"보다 "보편성 실증"으로 포지셔닝.
- 트리 vs 딥: tabular(엔지니어링 피처)에선 GBDT가 딥을 자주 이김(Grinsztajn 2022). seq789 LightGBM 98 > STTabNet 92 → 딥의 존재이유 = "요약 못 담는 순서/타이밍 잔여신호"를 잡는 것(같은 분할 공정비교 필요).

## 다음 할 일
- [ ] [최우선] 다중분류 붕괴 진단 (불균형 vs 그룹분할 격리, 클래스별 pcap 분포)
- [ ] 5-fold 평균±std
- [ ] 교차 데이터셋 일반화 (공통 태스크 service category로 VPN↔Tor)
- [ ] 정체성(SNI) vs 행동(seq789) ablation

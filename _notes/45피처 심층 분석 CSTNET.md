# 45피처 심층 분석 CSTNET

## 핵심 요약
CSTNet은 120개 클래스를 46,382개 flow로 분류하며, 기본 45피처만으로는 flow 통계 중심의 식별 한계가 있다. `ws_col_info`에서 TCP 세그먼트·윈도우 정보를 파생해 붙인 결과, 동일 랜덤 분할에서 Macro-F1이 65.76%에서 최대 73.08%까지 올랐다.

## 기록
### CSTNet 45피처·WS 파생피처 비교  <!-- (2026-07-27) -->
- 기준 45피처: Accuracy 69.43%, Macro-F1 65.76%, ECE 4.26.
- `ws_col_info`의 길이·방향·TCP window·재전송 정보를 파생해 **추가**한 실험이다. 기존 45개 정의를 교체하거나 수정한 것이 아니다.
  - 통계형 추가(총 63개): Accuracy 73.64%, Macro-F1 69.75%, ECE 6.03.
  - 순서형 세그먼트 길이까지 포함(총 77개): Accuracy 76.11%, Macro-F1 72.27%, ECE 5.11.
  - 순서형 + LightGBM 튜닝: Accuracy 76.82%, Macro-F1 73.08%, ECE 4.34.
- CSTNet 기본 모델 gain은 flow 통계 71.73%, 5-tuple 17.85%, 문맥 7.90%, 이름/L7 2.52%다. 상위는 `bwd_byte`, `fwd_byte`, `duration`, `dst_ip_c`이므로, 서비스별로 비슷한 TLS flow가 많으면 45피처만으로 분리하기 어렵다.
- WS 추가 후 `ws_win_min`은 gain 10.17%(튜닝 후 9.85%)로 상위 피처가 됐다. 암호화된 payload 대신 TCP 전송 패턴이 서비스별 보조 식별 신호가 된 결과다.
- 다른 데이터셋에 WS 피처를 적용하려면 해당 데이터셋에도 동일 형식의 `ws_col_info`가 있어야 한다. 없거나 캡처 도구·방향 표기·결측률이 다르면 모델 입력 스키마와 분포가 달라져 재학습·별도 검증이 필요하며, 기존 45피처 모델 자체는 영향받지 않는다.
- 평가는 하나의 고정 랜덤 80:20 분할이므로, 이 수치는 CSTNet 내부 분리 성능이다. 다른 날짜·환경·데이터셋으로의 일반화 성능은 아직 증명되지 않았다.
- 관련 코드: `03_ML/lab_dashboard_ver0.1/feat45_cstnet.py`, `03_ML/lab_dashboard_ver0.1/feat45_cstnet_improve.py`
- 관련 결과: `03_ML/lab_dashboard_ver0.1/feat45_cstnet_cstnet.json`, `03_ML/lab_dashboard_ver0.1/feat45_improve_cstnet.json`, `03_ML/lab_dashboard_ver0.1/feat45_improve_cstnet_seq.json`
- 관련: [[07_24 LightGBM]]

## 다음 할 일
- [ ] WS 피처를 같은 데이터셋의 날짜/세션 분리와 LODO 조건에서 재평가한다.
- [ ] 데이터셋별 `ws_col_info` 존재율·파싱 성공률·분포를 먼저 비교한다.
- [ ] WS 피처를 배포한다면 결측 처리와 피처 스키마를 모델 번들에 고정한다.

### 원본 PCAP 표준 시퀀스 추출 파이프라인  <!-- (2026-07-27) -->
- `lab_dashboard_ver0.1/extract_pcap_sequences.py`를 추가했다. `ws_col_info`는 입력으로 쓰지 않고, PCAP의 TCP/UDP를 양방향 5-tuple flow로 묶어 앞 **20/50/100개** 패킷을 표준 배열로 저장한다.
- 패킷별 배열: `packet_size`, client 기준 `direction`(+1/-1), `iat_ms`, `tcp_window`, `retrans`, `payload_size`, `mask`. 동행 CSV에는 flow 메타와 burst 수·최장 burst·업로드 비율·재전송 수를 기록한다.
- 출력은 chunk별 압축 NPZ + 동행 CSV + `manifest.json`이며, CSV와 NPZ 행 순서가 일치한다. `100`으로 한 번 추출하면 앞부분을 잘라 20/50 실험을 재사용한다.
- 서버 실행 전 주 사용자에게 예상 시간과 CPU/메모리 제한을 공유해야 한다. Ubuntu 간 Samba 마운트를 새로 만들지 않으며, 필요한 PCAP가 있는 서버에서 직접 실행한다.
- 다음: 소량 `--limit-pcaps` 스모크 테스트 → 전체 추출 → 45+고정 시퀀스 LightGBM와 1D-CNN/작은 Transformer를 날짜·세션 분리 조건으로 비교.

- 최신 실험 정리: [[CSTNET 패킷 시퀀스 LightGBM 실험]]

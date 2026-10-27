# L4 reasoning probe — 초미니 검증 실험

**질문:** 암호화 트래픽(여기선 먼저 애플리케이션 타이밍 프록시)만으로 "추론 ON vs OFF"가
출력 길이와 무관하게 갈리나? → 갈리면 L4(작업단계 추론) 연구가 산다.

## 준비
```bash
pip install anthropic matplotlib   # (이미 설치됨)
setx ANTHROPIC_API_KEY "sk-ant-..."   # Windows: 본인 API 키. Linux: export ANTHROPIC_API_KEY=...
```
API 키는 console.anthropic.com 에서 발급(유료). 소량이면 몇 백원 수준.

## 실행
```bash
# 1) 스모크테스트 (질문 2개 × 조건 3 × 1회 = 6콜, 비용 극소)
python mini_probe.py --limit 2 --repeats 1

# 2) 본 실행 (질문 8 × 조건 3 × 3회 = 72콜)
python mini_probe.py --repeats 3

# 3) 그림 + 요약
python plot_probe.py
```

## 볼 것
- `out/fig1_scatter.png` ← **핵심.** x=답 길이, y=첫-답변 지연(ttft_answer), 색=조건.
  - ON(on_low/on_high) 점들이 **같은 길이에서 OFF보다 위로** 뜨면 = "길이 아니라 추론이 신호" = 성공.
  - 겹쳐 안 갈리면 → 방향 재검토(값싼 실패, 하루면 앎).
- `out/fig2_ttft_hist.png`, `fig3_total_hist.png` = 분포 겹침.
- 콘솔 요약 = 조건별 중앙값.

## 측정 지표 (out/probe_results.csv)
- `ttft_answer_ms` — 요청→첫 '답변' 텍스트 토큰. **추론 지연의 핵심 신호.**
- `think_dur_ms` — 생각 구간(스트리밍형 추론=Claude식)에서 답 시작 전 시간.
- `total_ms`, `output_tokens`, `n_think_delta` 등.

## 제공자별 신호 차이(중요)
- Claude(여기) = 생각을 스트리밍(display=summarized) → 답 전 thinking 토큰이 흐름.
- OpenAI o1/o3 = 생각을 숨김 → 요청 후 **긴 침묵** 뒤 답. (별도 스크립트로 확장 권장)

## 다음(Phase 1)
이 애플리케이션 타이밍이 갈리면 → 같은 요청을 던지며 `tcpdump`로 pcap 동시 캡처,
패킷 크기·방향·IAT로 같은 판별이 되는지 = 진짜 '네트워크 side-channel' 실험으로 승격.
작성일: 2026-09-01

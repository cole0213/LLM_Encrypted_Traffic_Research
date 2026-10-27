"""
defense_sim.py — 방어(패딩·배칭·지연 균일화)를 걸었을 때 추론 신호가 얼마나 남는가.

목적:
  '언제 새고 안 새나'를 아는 것이 방어 설계의 근거라고 주장해 왔으나, 지금까지 방어 하
  성능은 측정한 적이 없다. 실제 방어를 서버에 걸 수는 없으므로, 이미 수집한 피처에
  방어의 효과를 모사해 정확도가 얼마나 떨어지는지를 잰다.
  (Whisper Leak 가 random padding 적용 시 97.5% -> 92.9% 로 보고한 것과 같은 방식.)

예측(실측 가시성 축에서 유도):
  Gemini(추론 요약이 결국 내려옴) = 크기와 타이밍 양쪽으로 새므로, 한쪽만 막으면 덜 떨어진다.
  Groq(추론 은닉)                 = 타이밍으로만 새므로, 패딩은 거의 소용없고
                                    지연 균일화가 치명적이어야 한다.
  예측이 맞으면 '방어는 provider 의 스트리밍 방식에 따라 달라야 한다'는 처방이 선다.

방어 모사 방식 — 두 종류:
  (A) 완전 차단 = 해당 채널의 피처를 제거한다. 그 채널을 완벽히 가렸을 때 남는 성능의 상한.
      패딩      : 크기 피처 제거(down_bytes, down_pkt_mean, down_pkt_max)
      배칭      : 크기 + 개수 피처 제거(패킷을 묶으면 개수·크기가 뭉개짐)
      지연 균일화: 타이밍 피처 제거(pkt_gap, down_iat_mean)
  (B) 부분 방어 = 타이밍을 격자로 반올림한다(100ms / 500ms). 현실의 지연 균일화에 가깝다.

한계:
  CSV 에는 집계 피처만 있고 원본 패킷 열은 없다. 따라서 (A)는 '완벽한 방어'라는 상한이고,
  실제 패딩은 패킷 개수를 남기는 등 더 약하다. 정확한 모사는 pcap 수준에서 다시 해야 한다.

입력: label=경로.csv (여러 개).
  예) python3 defense_sim.py gemini=out/gem_strict.csv groq=out/groq_strict.csv
출력: 콘솔 — 방어별 정확도와 하락폭.
작성일: 2026-10-02
"""
import sys
import csv

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score

# 하향 피처만. 업링크는 요청 크기로 설정값이 누출되므로 처음부터 제외한다.
SIZE_FEATS = ["down_bytes", "down_pkt_mean", "down_pkt_max"]   # 패딩이 가리는 것
COUNT_FEATS = ["down_pkts"]                                     # 배칭이 가리는 것
TIME_FEATS = ["pkt_gap_ms", "down_iat_mean_ms"]                 # 지연 균일화가 가리는 것
ALL_FEATS = TIME_FEATS + SIZE_FEATS + COUNT_FEATS
PAIR = ["think_low", "think_high"]      # 두 provider 공통 조건

# (A) 완전 차단 시나리오 — 이름: 남길 피처
SCENARIOS = [
    ("방어 없음",                 ALL_FEATS),
    ("패딩(크기 가림)",           TIME_FEATS + COUNT_FEATS),
    ("배칭(크기+개수 가림)",      TIME_FEATS),
    ("지연 균일화(타이밍 가림)",  SIZE_FEATS + COUNT_FEATS),
    ("패딩+지연 균일화",          COUNT_FEATS),
]
# (B) 부분 방어 — 타이밍을 이 격자(ms)로 반올림
QUANT_MS = [100, 500]


def load(path):
    """지정 조건만, 피처 결측 없는 행만."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("condition") not in PAIR:
                continue
            try:
                rec = {k: float(r[k]) for k in ALL_FEATS}
            except (TypeError, ValueError, KeyError):
                continue
            if any(np.isnan(v) for v in rec.values()):
                continue
            rec["y"] = r["condition"]; rec["q"] = int(float(r["q_idx"]))
            rows.append(rec)
    return rows


def cv_acc(rows, feats):
    """질문별 교차검증 정확도. 피처가 하나도 없으면 찍기(0.5)로 본다."""
    if not feats:
        return 0.5
    X = np.array([[r[f] for f in feats] for r in rows], float)
    y = np.array([r["y"] for r in rows])
    g = np.array([r["q"] for r in rows])
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=len(set(g))).split(X, y, g):
        m = RandomForestClassifier(n_estimators=300, random_state=42).fit(X[tr], y[tr])
        yt.extend(y[te]); yp.extend(m.predict(X[te]))
    return accuracy_score(yt, yp)


def quantized(rows, step_ms):
    """타이밍 피처를 step_ms 격자로 반올림 — 현실적인 지연 균일화 모사."""
    out = []
    for r in rows:
        c = dict(r)
        for f in TIME_FEATS:
            c[f] = round(c[f] / step_ms) * step_ms
        out.append(c)
    return out


def main():
    args = sys.argv[1:]
    if not args:
        print("사용: python3 defense_sim.py gemini=out/gem_strict.csv groq=out/groq_strict.csv")
        return
    for item in args:
        label, _, path = item.partition("=")
        rows = load(path)
        if not rows:
            print(f"[skip] {path} 에 {PAIR} 데이터 없음"); continue
        print(f"\n{'='*64}")
        print(f"{label or path}   n={len(rows)}   ({PAIR[0]} vs {PAIR[1]}, 하향 피처만)")
        print(f"{'='*64}")
        base = cv_acc(rows, ALL_FEATS)
        print(f"{'방어 시나리오':28s}{'정확도':>8s}{'하락폭':>10s}")
        print("-" * 64)
        for name, feats in SCENARIOS:
            a = cv_acc(rows, feats)
            drop = "" if name == "방어 없음" else f"{a - base:+.3f}"
            print(f"{name:28s}{a:>8.3f}{drop:>10s}")
        print("-" * 64)
        for step in QUANT_MS:
            a = cv_acc(quantized(rows, step), ALL_FEATS)
            print(f"{'타이밍 ' + str(step) + 'ms 격자로 반올림':28s}{a:>8.3f}{a - base:>+10.3f}")
    print("\n해석:")
    print("  크기를 가렸을 때 많이 떨어지면 = 추론이 '내려오는 양'으로 새는 provider (패딩이 유효)")
    print("  타이밍을 가렸을 때 많이 떨어지면 = 추론이 '기다리는 시간'으로 새는 provider (지연 균일화가 유효)")
    print("  → 어느 방어를 걸어야 하는지가 provider 마다 다르다는 뜻이며, 그것이 경계 지도의 쓸모다.")
    print("\n주의: 집계 피처 수준의 모사라 '완전 차단'은 상한값이다.")
    print("      실제 패딩은 패킷 개수를 남기므로 더 약하며, 정확한 수치는 pcap 수준 재모사가 필요하다.")


if __name__ == "__main__":
    main()

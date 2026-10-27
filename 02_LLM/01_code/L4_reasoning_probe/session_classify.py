"""
session_classify.py — L5: 세션 단위로 human vs agent 구별.

목적: session_log.jsonl + pcap에서 세션별 패킷/리듬 피처를 뽑아 human/agent 분류.
      단위 = 세션(활동 창). 피처 = 요청률·턴간 gap 통계·추론 밀도(pkt_gap)·바이트.
평가: 세션 수가 적으니 leave-one-session-out CV. 베이스라인 대조.
사용: python3 session_classify.py <pcap> <session_log.jsonl> [--local-ip ...]
작성일: 2026-09-02
"""
import sys
import json
import argparse
import statistics as st

import numpy as np
from scapy.all import rdpcap, IP, TCP
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import accuracy_score, confusion_matrix

BUF = 1.0
FEATS = ["n_turns", "gap_mean_s", "gap_std_s", "gap_min_s", "turns_per_min",
         "pktgap_mean_ms", "pktgap_max_ms", "frac_deep", "down_bytes_total",
         "dur_s"]


def turn_pkt_features(recs, local, t0, t1):
    """한 턴 구간의 (pkt_gap_ms, down_bytes) 반환."""
    win = [r for r in recs if t0 <= r[0] <= t1]
    out = [r for r in win if r[1] == local and r[3] > 0]
    inc = [r for r in win if r[2] == local and r[3] > 0]
    t_req = out[0][0] if out else None
    t_resp = None
    if t_req is not None:
        later = [r for r in inc if r[0] >= t_req]
        t_resp = later[0][0] if later else None
    gap = (t_resp - t_req) * 1000 if (t_req and t_resp) else np.nan
    return gap, sum(r[3] for r in inc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap"); ap.add_argument("log")
    ap.add_argument("--local-ip", default="163.152.223.17")
    ap.add_argument("--deep-ms", type=float, default=1200.0, help="깊은추론 판정 pkt_gap 문턱")
    args = ap.parse_args()
    LOCAL = args.local_ip

    turns = [json.loads(l) for l in open(args.log, encoding="utf-8")]
    turns = [t for t in turns if not t.get("error") and t.get("t_start")]
    pkts = rdpcap(args.pcap)
    recs = sorted((float(p.time), p[IP].src, p[IP].dst, len(p[TCP].payload))
                  for p in pkts if IP in p and TCP in p)

    # 세션별로 묶기.
    sids = sorted({t["session_id"] for t in turns})
    rows = []
    for sid in sids:
        ts = sorted([t for t in turns if t["session_id"] == sid], key=lambda z: z["t_start"])
        stype = ts[0]["session_type"]
        starts = [t["t_start"] for t in ts]
        gaps = [starts[i+1] - starts[i] for i in range(len(starts)-1)]  # 턴간 간격(초)
        pktgaps, downs = [], []
        for t in ts:
            g, d = turn_pkt_features(recs, LOCAL, t["t_start"], (t.get("t_end") or t["t_start"]) + BUF)
            if not np.isnan(g):
                pktgaps.append(g)
            downs.append(d)
        dur = starts[-1] - starts[0] if len(starts) > 1 else 1.0
        rows.append({
            "session_id": sid, "type": stype,
            "n_turns": len(ts),
            "gap_mean_s": st.mean(gaps) if gaps else 0.0,
            "gap_std_s": st.pstdev(gaps) if len(gaps) > 1 else 0.0,
            "gap_min_s": min(gaps) if gaps else 0.0,
            "turns_per_min": len(ts) / (dur/60) if dur > 0 else 0.0,
            "pktgap_mean_ms": st.mean(pktgaps) if pktgaps else 0.0,
            "pktgap_max_ms": max(pktgaps) if pktgaps else 0.0,
            "frac_deep": sum(1 for g in pktgaps if g >= args.deep_ms) / len(pktgaps) if pktgaps else 0.0,
            "down_bytes_total": sum(downs),
            "dur_s": dur,
        })

    print(f"세션 {len(rows)}개 (human {sum(r['type']=='human' for r in rows)}, "
          f"agent {sum(r['type']=='agent' for r in rows)})")
    for r in rows:
        print(f"  s{r['session_id']:>2d} {r['type']:6s} 턴={r['n_turns']:>2d} "
              f"gap_mean={r['gap_mean_s']:>5.1f}s tpm={r['turns_per_min']:>5.1f} "
              f"pktgap_mean={r['pktgap_mean_ms']:>6.0f}ms frac_deep={r['frac_deep']:.2f}")

    X = np.array([[r[f] for f in FEATS] for r in rows], dtype=float)
    y = np.array([r["type"] for r in rows])
    groups = np.array([r["session_id"] for r in rows])
    logo = LeaveOneGroupOut()

    def cv(model, Xin):
        yt, yp = [], []
        for tr, te in logo.split(Xin, y, groups):
            model.fit(Xin[tr], y[tr]); yt.extend(y[te]); yp.extend(model.predict(Xin[te]))
        return accuracy_score(yt, yp), np.array(yt), np.array(yp)

    print("\n=== human vs agent (leave-one-session-out) ===")
    a_maj, *_ = cv(DummyClassifier(strategy="most_frequent"), X)
    a_all, yt, yp = cv(RandomForestClassifier(n_estimators=300, random_state=42), X)
    # 리듬만(gap 계열) vs 추론만(pktgap 계열) 분해.
    idx_rhythm = [FEATS.index(f) for f in ["gap_mean_s","gap_std_s","gap_min_s","turns_per_min","n_turns"]]
    idx_reason = [FEATS.index(f) for f in ["pktgap_mean_ms","pktgap_max_ms","frac_deep"]]
    a_rhy, *_ = cv(RandomForestClassifier(n_estimators=300, random_state=42), X[:, idx_rhythm])
    a_rea, *_ = cv(RandomForestClassifier(n_estimators=300, random_state=42), X[:, idx_reason])
    print(f"  majority       : {a_maj:.3f}")
    print(f"  리듬 피처만    : {a_rhy:.3f}")
    print(f"  추론 피처만    : {a_rea:.3f}")
    print(f"  전체 피처      : {a_all:.3f}")
    print(f"  혼동행렬 labels=['agent','human']:")
    for lab, row in zip(["agent","human"], confusion_matrix(yt, yp, labels=["agent","human"])):
        print(f"    {lab:6s} {row}")
    m = RandomForestClassifier(n_estimators=300, random_state=42).fit(X, y)
    imp = sorted(zip(FEATS, m.feature_importances_), key=lambda z:-z[1])
    print("  피처 중요도:", ", ".join(f"{f}={w:.2f}" for f,w in imp[:5]))


if __name__ == "__main__":
    main()

"""
e1_classify.py — E1: 관측 → 예측. 한 턴의 '패킷 피처'만으로 추론 조건을 맞히나?

목적: capture_log.jsonl + pcap에서 턴별 패킷 피처를 뽑아, 추론 조건(no/low/high)을
      분류한다. 핵심 규칙:
        (1) 질문별 split(GroupKFold by q_idx = leave-one-question-out) → 새 질문서 정직 평가.
        (2) 피처는 '패킷만'(길이=output_tokens 제외) → 네트워크만으로의 주장.
        (3) 베이스라인 3종 대조: majority / 길이-only / 패킷모델.
      패킷모델이 길이-only를 이겨야 "길이 이상의 신호"가 증명됨.
사용: python3 e1_classify.py <pcap> <capture_log.jsonl> [--local-ip 163.152.223.17]
출력: 콘솔(정확도·혼동행렬·피처중요도).
작성일: 2026-09-01
"""
import sys
import json
import argparse
import statistics as st

import numpy as np
from scapy.all import rdpcap, IP, TCP
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

BUF = 1.0
PKT_FEATS = ["pkt_gap_ms", "up_bytes", "down_bytes", "up_pkts", "down_pkts",
             "down_iat_mean_ms", "down_pkt_mean", "down_pkt_max"]


def extract(pcap, log, local):
    """pcap+log → 턴별 dict(패킷피처 + 라벨 + q_idx + output_tokens)."""
    entries = [json.loads(l) for l in open(log, encoding="utf-8")]
    entries = [e for e in entries if not e.get("error") and e.get("t_start")]
    pkts = rdpcap(pcap)
    recs = []
    for p in pkts:
        if IP in p and TCP in p:
            recs.append((float(p.time), p[IP].src, p[IP].dst, len(p[TCP].payload)))
    recs.sort()
    rows = []
    for e in entries:
        t0 = e["t_start"]; t1 = (e.get("t_end") or t0) + BUF
        win = [r for r in recs if t0 <= r[0] <= t1]
        out = [r for r in win if r[1] == local and r[3] > 0]
        inc = [r for r in win if r[2] == local and r[3] > 0]
        t_req = out[0][0] if out else None
        t_resp = None
        if t_req is not None:
            later = [r for r in inc if r[0] >= t_req]
            t_resp = later[0][0] if later else None
        dsz = [r[3] for r in inc]
        dt = sorted(r[0] for r in inc)
        iats = [(dt[i+1]-dt[i])*1000 for i in range(len(dt)-1)]
        rows.append({
            "condition": e["condition"], "q_idx": e["q_idx"],
            "output_tokens": e.get("output_tokens") or 0,
            "pkt_gap_ms": (t_resp - t_req) * 1000 if (t_req and t_resp) else np.nan,
            "up_bytes": sum(r[3] for r in out), "down_bytes": sum(dsz),
            "up_pkts": len(out), "down_pkts": len(inc),
            "down_iat_mean_ms": st.mean(iats) if iats else 0.0,
            "down_pkt_mean": st.mean(dsz) if dsz else 0.0,
            "down_pkt_max": max(dsz) if dsz else 0,
        })
    return rows


def cv_eval(X, y, groups, model, n_splits):
    """질문별 GroupKFold 교차검증 → 전체 예측 모아 정확도 + 혼동행렬."""
    gkf = GroupKFold(n_splits=n_splits)
    y_true, y_pred = [], []
    for tr, te in gkf.split(X, y, groups):
        model.fit(X[tr], y[tr])
        y_true.extend(y[te]); y_pred.extend(model.predict(X[te]))
    return accuracy_score(y_true, y_pred), np.array(y_true), np.array(y_pred)


def run_task(rows, labels, title):
    sub = [r for r in rows if r["condition"] in labels and not np.isnan(r["pkt_gap_ms"])]
    y = np.array([r["condition"] for r in sub])
    groups = np.array([r["q_idx"] for r in sub])
    n_q = len(set(groups))
    Xpkt = np.array([[r[f] for f in PKT_FEATS] for r in sub], dtype=float)
    Xlen = np.array([[r["output_tokens"]] for r in sub], dtype=float)
    print(f"\n{'='*58}\n[{title}]  n={len(sub)}, 질문 {n_q}개 (leave-one-question-out)")
    print(f"  클래스 분포: { {c: int((y==c).sum()) for c in labels} }")

    # 베이스라인 + 패킷모델
    maj = DummyClassifier(strategy="most_frequent")
    a_maj, *_ = cv_eval(Xpkt, y, groups, maj, n_q)
    lenm = RandomForestClassifier(n_estimators=300, random_state=42)
    a_len, *_ = cv_eval(Xlen, y, groups, lenm, n_q)
    pktm = RandomForestClassifier(n_estimators=300, random_state=42)
    a_pkt, yt, yp = cv_eval(Xpkt, y, groups, pktm, n_q)

    print(f"  ── 정확도 (질문별 CV) ──")
    print(f"    majority(찍기)     : {a_maj:.3f}")
    print(f"    length-only(길이만): {a_len:.3f}   ← 이걸 이겨야 함")
    print(f"    packet model(패킷) : {a_pkt:.3f}")
    print(f"  혼동행렬 (행=정답, 열=예측) labels={list(labels)}:")
    cm = confusion_matrix(yt, yp, labels=list(labels))
    for lab, row in zip(labels, cm):
        print(f"    {lab:11s} {row}")
    # 피처 중요도(전체 학습으로).
    pktm.fit(Xpkt, y)
    imp = sorted(zip(PKT_FEATS, pktm.feature_importances_), key=lambda z: -z[1])
    print("  피처 중요도:", ", ".join(f"{f}={w:.2f}" for f, w in imp[:5]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap"); ap.add_argument("log")
    ap.add_argument("--local-ip", default="163.152.223.17")
    args = ap.parse_args()
    rows = extract(args.pcap, args.log, args.local_ip)
    print(f"턴 {len(rows)}개 추출 (local IP={args.local_ip})")
    run_task(rows, ["no_think", "think_high"], "이진: no_think vs think_high")
    run_task(rows, ["no_think", "think_low", "think_high"], "3클래스: no/low/high")


if __name__ == "__main__":
    main()

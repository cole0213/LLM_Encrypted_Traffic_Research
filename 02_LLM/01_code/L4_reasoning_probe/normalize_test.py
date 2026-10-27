"""
normalize_test.py — 질문별 기준선 차이를 보정하면 추론 깊이 분류가 얼마나 좋아지는가.

배경(실측):
  질문 하나만 놓고 보면 low 와 high 는 전혀 겹치지 않는다(질문 내 AUC = 1.000, 12문항 전부).
  그런데 질문을 섞어 하나의 기준선으로 가르면 Gemini 0.900 / Groq 0.956 로 떨어진다.
  원인은 질문마다 기준선 자체가 다르기 때문이다. 예)
    Gemini q6(정십이면체)  low    0 -> high  212
    Gemini q4(체스 나이트) low 1002 -> high 1962
    → q4 의 '얕은 추론'이 q6 의 '깊은 추론'보다 5배 많다. 고정 임계값으로는 불가능.

이 스크립트가 재는 것:
  같은 데이터를 세 가지 방식으로 넣어 정확도를 비교한다.
    (A) 잰 그대로            — 지금 방식. 질문을 전혀 모르는 관측자.
    (B) 질문 중앙값으로 나눔 — 그 질문 콜들의 중앙값을 1로 보는 상대값.
    (C) 질문 최솟값으로 나눔 — 그 질문의 가장 빠른 콜을 기준선으로 보는 상대값.

위협 모델 해석:
  (A)는 하한, (B)(C)는 상한이다. 상대값을 만들려면 '어떤 요청들이 같은 프롬프트인지'를
  알아야 하는데, 암호화 환경의 관측자는 보통 그걸 모른다. 반대로 봇·자동화 파이프라인처럼
  같은 프롬프트가 반복되는 상황을 아는 관측자는 (B)(C)에 가깝다.

주의 — 순환 위험:
  정규화에 쓰는 통계(중앙값·최솟값)를 '평가할 질문의 콜들'에서 뽑는다. 라벨은 전혀 안 쓰지만,
  그 질문에 low/high 가 섞여 있다는 사실 자체가 중앙값 위치에 영향을 준다.
  특히 (B)는 섞인 비율에 민감하므로, 실제 관측자가 비율을 모르면 이만큼 안 나올 수 있다.
  (C)는 최솟값(대개 가장 얕은 콜)을 쓰므로 비율 의존이 덜하다.
  따라서 (B)(C)는 '이상적인 경우의 상한'으로 읽어야 하며 보고 시 그렇게 밝혀야 한다.

입력: label=경로.csv (여러 개). 조건 쌍은 --pair 로 지정(기본 think_low,think_high).
  예) python3 normalize_test.py gemini=out/gem_strict2.csv groq=out/groq_strict2.csv
출력: 콘솔 — 방식별 정확도와 혼동행렬.
작성일: 2026-10-05
"""
import sys
import csv

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

# 하향 피처만(업링크는 요청 크기로 설정값 누출 가능하므로 제외).
FEATS = ["pkt_gap_ms", "down_bytes", "down_pkts",
         "down_iat_mean_ms", "down_pkt_mean", "down_pkt_max"]


def load(path, pair):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("condition") not in pair:
                continue
            # 답을 못 낸 콜(추론이 토큰 한계까지 간 경우)은 제외.
            at = r.get("app_ttft_ms")
            if at in ("", "None", None):
                continue
            try:
                rec = {k: float(r[k]) for k in FEATS}
            except (TypeError, ValueError, KeyError):
                continue
            if any(np.isnan(v) for v in rec.values()):
                continue
            rec["y"] = r["condition"]; rec["q"] = int(float(r["q_idx"]))
            rows.append(rec)
    return rows


def normalize(rows, how):
    """질문별로 피처를 상대값으로 바꾼다. 라벨은 쓰지 않는다."""
    if how == "raw":
        return rows
    out = []
    qs = sorted(set(r["q"] for r in rows))
    for q in qs:
        grp = [r for r in rows if r["q"] == q]
        base = {}
        for f in FEATS:
            vals = [r[f] for r in grp]
            b = float(np.median(vals)) if how == "median" else float(np.min(vals))
            # 0 으로 나누는 것을 막는다(크기 피처는 0 이 될 일이 드물지만 방어적으로).
            base[f] = b if abs(b) > 1e-9 else 1.0
        for r in grp:
            c = dict(r)
            for f in FEATS:
                c[f] = r[f] / base[f]
            out.append(c)
    return out


def cv(rows, pair):
    X = np.array([[r[f] for f in FEATS] for r in rows], float)
    y = np.array([r["y"] for r in rows])
    g = np.array([r["q"] for r in rows])
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=len(set(g))).split(X, y, g):
        m = RandomForestClassifier(n_estimators=300, random_state=42).fit(X[tr], y[tr])
        yt.extend(y[te]); yp.extend(m.predict(X[te]))
    return accuracy_score(yt, yp), confusion_matrix(yt, yp, labels=list(pair))


def unbalance(rows, pair, keep):
    """순환 검증용 — 질문마다 첫 조건의 콜을 keep 개만 남겨 5:5 균형을 깬다.

    (B) 중앙값 정규화가 1.000 을 낸 것이 '진짜 신호'인지 '반반 구성이 만든 답'인지 가린다.
    균형이 깨지면 중앙값이 두 집단 사이가 아니라 다수 쪽으로 끌려가므로,
    순환이었다면 성능이 크게 무너지고 진짜 신호였다면 거의 유지돼야 한다.
    """
    out = []
    for q in sorted(set(r["q"] for r in rows)):
        grp = [r for r in rows if r["q"] == q]
        a = [r for r in grp if r["y"] == pair[0]][:keep]
        b = [r for r in grp if r["y"] == pair[1]]
        out.extend(a + b)
    return out


def main():
    args = sys.argv[1:]
    pair = ["think_low", "think_high"]
    if "--pair" in args:
        k = args.index("--pair")
        pair = [c.strip() for c in args[k + 1].split(",")]
        del args[k:k + 2]
    keep = 0
    if "--keep" in args:          # 질문당 pair[0] 조건을 몇 개만 남길지(0=전부)
        k = args.index("--keep")
        keep = int(args[k + 1])
        del args[k:k + 2]
    if not args:
        print("사용: python3 normalize_test.py gemini=out/gem_strict2.csv groq=out/groq_strict2.csv")
        return
    modes = [("A 잰 그대로 (질문 모름)", "raw"),
             ("B 질문 중앙값으로 나눔", "median"),
             ("C 질문 최솟값으로 나눔", "min")]
    for item in args:
        label, _, path = item.partition("=")
        rows = load(path, pair)
        if not rows:
            print(f"[skip] {path} 에 {pair} 데이터 없음"); continue
        if keep:
            rows = unbalance(rows, pair, keep)
        print(f"\n{'='*62}")
        note = f"   [불균형 검증: 질문당 {pair[0]} {keep}개만]" if keep else ""
        print(f"{label or path}   n={len(rows)}   {pair[0]} vs {pair[1]}   하향 피처 {len(FEATS)}개{note}")
        cnt = {c: sum(1 for r in rows if r['y'] == c) for c in pair}
        print(f"클래스 분포 {cnt}   찍기 기준 {max(cnt.values())/len(rows):.3f}")
        print(f"{'='*62}")
        base = None
        for name, how in modes:
            acc, cm = cv(normalize(rows, how), pair)
            if base is None:
                base = acc; delta = ""
            else:
                delta = f"  ({acc - base:+.3f})"
            print(f"\n  {name:26s} 정확도 {acc:.3f}{delta}")
            for lab, row in zip(pair, cm):
                print(f"      {lab:11s} {row}")
    print("\n해석:")
    print("  A = 프롬프트를 모르는 관측자(하한). B·C = 같은 프롬프트가 반복됨을 아는 관측자(상한).")
    print("  둘의 간격이 '프롬프트를 아느냐'가 만드는 누출 폭의 차이다.")
    print("  단, B·C 는 평가할 질문의 콜들에서 기준선을 뽑으므로 이상적 조건의 상한으로 읽어야 한다.")


if __name__ == "__main__":
    main()

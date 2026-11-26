#!/usr/bin/env python3
"""
cutoff_importance.py — 조기 탐지 창이 전체 창보다 정확한 이유를 가른다.

왜 필요한가
-----------
2026-11-24 측정에서 **정보를 덜 보는 쪽이 더 잘 맞히는** 현상이 나왔다.
OpenAI 전 모델이 cutoff 500~2000ms 에서 70~84% 인데 전체 창은 26~59% 다(+19~48%p).
Anthropic 은 반대로 단조 증가라 조기 이득이 0 이다.

`early_eval.py` 는 피처 중요도를 **전체 창에서만** 낸다. 그래서 "초반 창에는 무엇이 보이고
전체 창에서는 그것이 왜 묻히는가" 를 못 묻는다. 이 스크립트가 그 자리를 채운다.

무엇을 재는가 (cutoff 마다)
---------------------------
  1. 전체 피처 정확도 — early_eval.py 와 같은 값이어야 한다(배선 검증).
  2. **채널별 정확도** — 타이밍만 / 바이트만 / 개수만. 신호가 어느 채널에 실리는지 가른다.
     초반 창에서 타이밍만으로 높고 전체 창에서 바이트만으로 높다면,
     "창이 커지면서 바이트 분산이 타이밍 신호를 덮는다" 는 설명이 선다.
  3. 피처 중요도 상위 3개.
  4. **최고 cutoff 와 전체 창에서, 상위 피처의 조건별 중앙값.**
     분리가 실제로 줄어드는지를 눈으로 확인한다. 중요도만 보면 "무엇을 쓰는지" 는 알아도
     "왜 못 맞히는지" 는 모른다.

주의
----
- 피처는 `early_eval.py` 의 WIRE 와 **글자 그대로 같아야** 한다. 여기서만 하나 더 넣으면
  두 결과를 비교할 수 없다. `total_ms`·`seen_frac`·`finished_by_cutoff` 는 공격자가 못 보는
  값이라 어느 쪽에도 없다.
- 중요도는 **전체 데이터 적합**이라 참고치다. 정확도는 family 단위 GroupKFold 교차검증이다.
  둘을 같은 줄에 적되 성격이 다르다는 것을 잊지 마라.

입력: out/early_<tag>.csv (early_detect.py 산출물. cutoff_ms 열 필요)
출력: 표준출력 표. --out 을 주면 CSV 로도 쓴다.

사용:
  python3 cutoff_importance.py out/early_luna250.csv
  python3 cutoff_importance.py out/early_*.csv --out out/cutoff_imp.csv

작성일: 2026-11-24
"""
import csv
import sys
import argparse

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score

# early_eval.py 의 WIRE 와 동일해야 한다. 바꾸면 두 결과가 비교 불가가 된다.
WIRE = ["pkt_gap_ms", "up_pkts", "down_pkts", "up_bytes", "down_bytes",
        "down_pkt_mean", "down_pkt_max", "down_iat_mean_ms", "down_iat_max_ms",
        "down_iat_p90_ms", "down_iat_p99_ms", "stall_total_ms", "stall_count",
        "down_iat_first_ms", "n_pkts_window", "responded"]

# 채널 분해. 합집합이 WIRE 이고 서로 겹치지 않는다.
CH = {
    "타이밍": ["pkt_gap_ms", "down_iat_mean_ms", "down_iat_max_ms", "down_iat_p90_ms",
             "down_iat_p99_ms", "stall_total_ms", "stall_count", "down_iat_first_ms"],
    "바이트": ["up_bytes", "down_bytes", "down_pkt_mean", "down_pkt_max"],
    "개수": ["up_pkts", "down_pkts", "n_pkts_window", "responded"],
}

ORD = ["think_low", "think_medium", "think_high", "think_xhigh", "think_max"]


def num(v, default=0.0):
    """CSV 는 전부 문자열이다. 빈 칸과 None 을 0 으로 접는다."""
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def cv_acc(rows, feats, trees, seed, folds):
    """family 단위 GroupKFold 정확도(%). 폴드가 안 나오면 None."""
    X = np.array([[num(r.get(f)) for f in feats] for r in rows], dtype=float)
    y = np.array([r["condition"] for r in rows])
    groups = np.array([r.get("family") or r["q_idx"] for r in rows])
    k = min(folds, len(set(groups)))
    if k < 2:
        return None
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=k).split(X, y, groups):
        if len(set(y[tr])) < 2:
            continue
        clf = RandomForestClassifier(n_estimators=trees, random_state=seed, n_jobs=-1)
        clf.fit(X[tr], y[tr])
        yp.extend(clf.predict(X[te]))
        yt.extend(y[te])
    return 100.0 * accuracy_score(yt, yp) if yt else None


def importances(rows, trees, seed):
    """전체 데이터 적합 중요도(참고치)."""
    X = np.array([[num(r.get(f)) for f in WIRE] for r in rows], dtype=float)
    y = np.array([r["condition"] for r in rows])
    clf = RandomForestClassifier(n_estimators=trees, random_state=seed, n_jobs=-1).fit(X, y)
    return sorted(zip(WIRE, clf.feature_importances_), key=lambda z: -z[1])


def dist_by_cond(rows, feat):
    """조건별 분위수.

    2026-11-24: 처음에는 중앙값만 찍었는데, luna 500ms 에서 조건별 중앙값이
    3492~3498 로 **전부 같은데 정확도가 75%** 였다. 중앙값이 틀린 요약이었던 것이다.
    분리가 분포의 가운데가 아니라 꼬리에 있으면 중앙값은 아무것도 안 보여준다.
    그래서 p25/p50/p75/p90 을 같이 본다.
    """
    out = {}
    for c in ORD:
        v = [num(r.get(feat)) for r in rows if r["condition"] == c]
        if v:
            q = np.percentile(v, [25, 50, 75, 90])
            out[c] = (q[0], q[1], q[2], q[3], float(np.mean(v)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--trees", type=int, default=300)
    ap.add_argument("--seed", type=int, default=20261106)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    recs = []
    for path in a.csvs:
        rows = read(path)
        if not rows or "cutoff_ms" not in rows[0]:
            print(f"[건너뜀] {path} — cutoff_ms 열이 없다")
            continue
        tag = path.split("early_")[-1].replace(".csv", "")
        cuts = sorted({int(num(r["cutoff_ms"])) for r in rows})
        cuts = [c for c in cuts if c != 0] + [0]          # 전체(0)를 맨 뒤로

        print(f"\n########## {tag}")
        print(f"{'cutoff':>8} {'n':>6} {'전체':>7} {'타이밍':>7} {'바이트':>7} {'개수':>6}   상위 피처 3개")
        print("-" * 86)
        best_cut, best_acc = None, -1.0
        for cut in cuts:
            g = [r for r in rows if int(num(r["cutoff_ms"])) == cut]
            if len(g) < 50:
                continue
            acc = cv_acc(g, WIRE, a.trees, a.seed, a.folds)
            if acc is None:
                continue
            per = {k: cv_acc(g, v, a.trees, a.seed, a.folds) for k, v in CH.items()}
            top = importances(g, a.trees, a.seed)[:3]
            lab = "전체" if cut == 0 else f"{cut}ms"
            cells = "".join(f"{(per[k] if per[k] is not None else 0):>7.1f}" for k in CH)
            print(f"{lab:>8} {len(g):>6} {acc:>6.1f}%{cells}   " +
                  "  ".join(f"{f}({v:.2f})" for f, v in top))
            recs.append({"tag": tag, "cutoff_ms": cut, "n": len(g),
                         "acc_all": round(acc, 2),
                         **{f"acc_{k}": (round(per[k], 2) if per[k] is not None else "")
                            for k in CH},
                         "top1": top[0][0], "top1_imp": round(top[0][1], 4)})
            if cut != 0 and acc > best_acc:
                best_acc, best_cut = acc, cut

        # 최고 cutoff 와 전체 창에서 상위 피처의 조건별 분포를 나란히 본다.
        # 가운데가 같아도 꼬리가 갈리면 분류는 된다 — 그 경우를 놓치지 않으려고 분위수를 쓴다.
        full = [r for r in rows if int(num(r["cutoff_ms"])) == 0]
        if best_cut is not None and full:
            for cut, name in ((best_cut, f"최고 {best_cut}ms"), (0, "전체 창")):
                g = [r for r in rows if int(num(r["cutoff_ms"])) == cut]
                f1 = importances(g, a.trees, a.seed)[0][0]
                d = dist_by_cond(g, f1)
                print(f"\n  [{name}] 상위피처 {f1} 조건별 분포")
                print(f"    {'조건':<8}{'p25':>10}{'p50':>10}{'p75':>10}{'p90':>10}{'평균':>10}")
                for c in ORD:
                    if c in d:
                        q25, q50, q75, q90, mu = d[c]
                        print(f"    {c.replace('think_',''):<8}{q25:>10.0f}{q50:>10.0f}"
                              f"{q75:>10.0f}{q90:>10.0f}{mu:>10.0f}")
                # 분위수별 max/low 배수 — 어느 분위에서 갈리는지 한 줄로 본다.
                lo, hi = d.get("think_low"), d.get("think_max")
                if lo and hi:
                    labs = ["p25", "p50", "p75", "p90", "평균"]
                    print("    max/low 배수:  " + "  ".join(
                        f"{labs[i]}={hi[i]/lo[i]:.2f}" if lo[i] else f"{labs[i]}=-"
                        for i in range(5)))

    if a.out and recs:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
            w.writeheader()
            w.writerows(recs)
        print(f"\n[out] {a.out}  ({len(recs)}행)")


if __name__ == "__main__":
    sys.exit(main())

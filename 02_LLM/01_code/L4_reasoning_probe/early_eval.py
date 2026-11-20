#!/usr/bin/env python3
"""early_detect.py 가 낸 long CSV 로 '관측 시간 vs 탐지 정확도' 곡선을 낸다.

왜 필요한가
-----------
RQ6(조기 탐지)의 본 수치다. 그리고 지금까지 보고한 Task A 정확도는 node 로 급히 짠
대각 공분산 가우시안 분류기로 뽑은 **참고치**였다(피처끼리 상관이 0.97 이상이라
조건부 독립 가정이 크게 깨진다). 여기서는 e1_from_csv.py 와 같은
RandomForest + GroupKFold 로 다시 잰다. `--cutoffs 0` 만 주면 그게 곧 Task A 정본이다.

중요한 통제
-----------
공격자는 응답이 언제 끝나는지 **모른다**. 그래서 total_ms / seen_frac /
finished_by_cutoff 는 피처에서 반드시 뺀다 — 전부 전체 소요시간을 담고 있어
넣는 순간 미래를 보는 셈이 된다. app_ttft_ms 도 뺀다(앱 계층 계측치).

분할은 **family(템플릿) 단위 GroupKFold** 다. 파라메트릭 갈래는 한 템플릿의 변형
수십 개가 서로 닮아 독립 표본이 아니다. 행 단위나 문항 단위로 쪼개면 같은 틀이
학습·시험에 동시에 들어가 정확도가 부풀려진다.

입력 : early_detect.py 의 --out CSV (cutoff_ms 열이 있는 long 형식)
출력 : 표준출력 표. --out 을 주면 CSV 로도 저장
비용 : 0

사용:
    python3 early_eval.py out/early_sol250.csv
    python3 early_eval.py out/early_sol250.csv --task level --levels low,medium,high
    python3 early_eval.py out/early_sol250.csv --cutoffs 0 --out out/taskA_rf_sol.csv

작성일: 2026-11-20
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

# 전선에서 관측 가능한 피처만. 여기 없는 열은 라벨이거나 공격자가 못 보는 값이다.
WIRE = ["pkt_gap_ms", "up_pkts", "down_pkts", "up_bytes", "down_bytes",
        "down_pkt_mean", "down_pkt_max", "down_iat_mean_ms", "down_iat_max_ms",
        "down_iat_p90_ms", "down_iat_p99_ms", "stall_total_ms", "stall_count",
        "down_iat_first_ms", "n_pkts_window", "responded"]

ORD = ["think_low", "think_medium", "think_high", "think_xhigh", "think_max"]


def read(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def num(v, default=0.0):
    """빈칸은 0 으로 본다. 조기 탐지에서 '아직 안 왔다'는 결측이 아니라 0 이다."""
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_path")
    ap.add_argument("--cutoffs", default="",
                    help="평가할 cutoff 만 고른다(쉼표). 비우면 파일에 있는 전부")
    ap.add_argument("--levels", default="",
                    help="쓸 조건만(쉼표, think_ 접두어 없이). 비우면 전부. "
                         "예) low,medium,high 로 주면 provider 공통 3단 축")
    ap.add_argument("--clean-only", action="store_true", default=True,
                    help="순응·비잘림·1글자 답만 쓴다(기본). --no-clean-only 로 끈다")
    ap.add_argument("--no-clean-only", dest="clean_only", action="store_false")
    ap.add_argument("--trees", type=int, default=300)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="", help="결과를 CSV 로도 저장")
    a = ap.parse_args()

    rows = read(a.csv_path)
    if a.clean_only:
        rows = [r for r in rows
                if r.get("complied") == "1" and r.get("truncated") == "0"
                and num(r.get("answer_chars"), -1) == 1]
    keep_lv = [f"think_{x.strip()}" for x in a.levels.split(",") if x.strip()]
    if keep_lv:
        rows = [r for r in rows if r["condition"] in keep_lv]
    if not rows:
        raise SystemExit("조건에 맞는 행이 없다. --levels / --no-clean-only 를 확인하라.")

    cuts_all = sorted({int(num(r["cutoff_ms"])) for r in rows},
                      key=lambda c: (c == 0, c))   # 0(전체)을 맨 뒤로
    if a.cutoffs:
        want = {int(x.strip()) for x in a.cutoffs.split(",") if x.strip()}
        cuts_all = [c for c in cuts_all if c in want]

    conds = [c for c in ORD if any(r["condition"] == c for r in rows)]
    chance = 100.0 / len(conds)
    print(f"행 {len(rows)}  조건 {len(conds)}종 {','.join(x.replace('think_','') for x in conds)}"
          f"  우연 {chance:.1f}%")
    print(f"분할: family 단위 GroupKFold({a.folds})  분류기: RandomForest({a.trees})\n")

    header = f"{'cutoff':>8} {'n':>6} {'정확도':>8} {'우연대비':>9} {'응답시작%':>9} {'이미완료%':>9}"
    print(header)
    print("-" * len(header))

    out_rows = []
    for cut in cuts_all:
        g = [r for r in rows if int(num(r["cutoff_ms"])) == cut]
        if len(g) < 50:
            continue
        X = np.array([[num(r.get(f)) for f in WIRE] for r in g], dtype=float)
        y = np.array([r["condition"] for r in g])
        groups = np.array([r.get("family") or r["q_idx"] for r in g])
        n_groups = len(set(groups))
        folds = min(a.folds, n_groups)
        if folds < 2:
            print(f"  cutoff {cut}: 그룹이 {n_groups}개뿐이라 건너뜀")
            continue

        gkf = GroupKFold(n_splits=folds)
        yt, yp = [], []
        for tr, te in gkf.split(X, y, groups):
            # 학습 폴드에 조건이 하나뿐이면 분류가 성립하지 않는다.
            if len(set(y[tr])) < 2:
                continue
            clf = RandomForestClassifier(n_estimators=a.trees, random_state=a.seed,
                                         n_jobs=-1)
            clf.fit(X[tr], y[tr])
            yp.extend(clf.predict(X[te]))
            yt.extend(y[te])
        if not yt:
            continue
        acc = 100.0 * accuracy_score(yt, yp)
        resp = 100.0 * sum(int(num(r["responded"])) for r in g) / len(g)
        fin = 100.0 * sum(int(num(r["finished_by_cutoff"])) for r in g) / len(g)
        lab = "전체" if cut == 0 else f"{cut}ms"
        print(f"{lab:>8} {len(g):>6} {acc:>7.1f}% {acc/chance:>8.2f}x {resp:>8.1f}% {fin:>8.1f}%")
        out_rows.append({"cutoff_ms": cut, "n": len(g), "acc": round(acc, 2),
                         "chance": round(chance, 2), "responded_pct": round(resp, 1),
                         "finished_pct": round(fin, 1)})

    # 전체 창에서의 혼동행렬 — 어느 단계가 서로 섞이는지가 Task A 해석의 핵심이다.
    full = [r for r in rows if int(num(r["cutoff_ms"])) == 0]
    if full:
        X = np.array([[num(r.get(f)) for f in WIRE] for r in full], dtype=float)
        y = np.array([r["condition"] for r in full])
        groups = np.array([r.get("family") or r["q_idx"] for r in full])
        folds = min(a.folds, len(set(groups)))
        if folds >= 2:
            yt, yp = [], []
            for tr, te in GroupKFold(n_splits=folds).split(X, y, groups):
                if len(set(y[tr])) < 2:
                    continue
                clf = RandomForestClassifier(n_estimators=a.trees, random_state=a.seed,
                                             n_jobs=-1).fit(X[tr], y[tr])
                yp.extend(clf.predict(X[te])); yt.extend(y[te])
            labs = [c for c in ORD if c in set(yt)]
            cm = confusion_matrix(yt, yp, labels=labs)
            print("\n=== 전체 창 혼동행렬 (행=실제, 열=예측) ===")
            short = [c.replace("think_", "") for c in labs]
            print("        " + "".join(f"{s:>8}" for s in short))
            for i, s in enumerate(short):
                print(f"{s:>8}" + "".join(f"{v:>8}" for v in cm[i]))
            # 피처 중요도 — 전체 데이터로 한 번 더 적합(참고치)
            clf = RandomForestClassifier(n_estimators=a.trees, random_state=a.seed,
                                         n_jobs=-1).fit(X, y)
            imp = sorted(zip(WIRE, clf.feature_importances_), key=lambda z: -z[1])
            print("\n=== 피처 중요도 상위 6 (전체 적합, 참고치) ===")
            for f, v in imp[:6]:
                print(f"  {f:<20} {v:.3f}")

    if a.out and out_rows:
        with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader(); w.writerows(out_rows)
        print(f"\n[out] {a.out}")

    print("\n→ 작은 cutoff 의 정확도가 전체에 가까우면 조기 탐지가 성립한다.")
    print("→ '이미완료%'가 높은 cutoff 는 조기 관측이 아니라 사실상 전체 관측이다. 같이 읽어라.")


if __name__ == "__main__":
    main()

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

# --quantize 가 반올림할 피처. '바이트를 세는' 열만 넣는다.
# 패킷 수·시간 열은 에코의 영향을 안 받으므로 건드리지 않는다.
BYTE_FEATS = ["down_bytes", "up_bytes", "down_pkt_mean", "down_pkt_max"]

# effort 문자열의 글자 수. --echo-sub 가 '피처 - k x 글자수' 를 뺄 때 쓴다.
# 깊이 순서(3<6<4<5<3)와 일치하지 않는다는 점이 이 교정의 근거다.
STRLEN = {"think_low": 3, "think_medium": 6, "think_high": 4,
          "think_xhigh": 5, "think_max": 3}


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
    # 2026-11-24 추가. 라벨 에코 누출을 죽이려고 바이트 피처를 버킷으로 반올림한다.
    # 배경: OpenAI 응답이 effort 문자열("low"/"medium"/...)을 그대로 되돌려보내고
    # 그 값이 스트림에 두 번 실려, down_bytes 가 **설정 글자 수 x 2 바이트**만큼 달라진다.
    # 500ms 창에서는 다른 피처가 전부 상수라 이 6바이트만으로 75% 가 나왔다 — 추론이 아니라
    # 라벨을 베낀 것이다. 전체 창의 진짜 신호는 수천 바이트라 100바이트 버킷이면
    # 에코는 죽고 신호는 남는다. --quantize 100 으로 돌려 두 수치를 비교하라.
    ap.add_argument("--quantize", type=int, default=0, metavar="B",
                    help="바이트 피처를 B 바이트 버킷으로 반올림(0=끄기). "
                         "라벨 에코 누출 제거용. 권장 100")
    # 2026-11-24 추가. 양자화는 '라벨을 안 보는' 둔기라 신호도 같이 깎는다(하한만 준다).
    # echo_fit.py 로 잰 글자당 바이트 k 를 그만큼만 빼면 신호를 안 깎는다.
    # 단 이쪽은 **라벨을 본다** — k 가 틀리면 그 오차가 다시 라벨에 정렬된 신호로 남는다.
    # 그래서 교정판은 양자화판을 대체하지 않고 '중간 추정' 으로 같이 보고한다.
    ap.add_argument("--echo-sub", default="", metavar="FEAT:K[,FEAT:K]",
                    help="피처값에서 k x len(effort문자열) 을 뺀다. "
                         "예) down_bytes:2.0,up_bytes:1.0. k 는 echo_fit.py 로 잰다")
    # 2026-11-26 추가. Gemini 캡처(out/gem_v2_all.csv)는 parse_pcap 산출 wide CSV 라
    # cutoff_ms 열이 없다. 그 경우 전체 창(cutoff 0) 한 줄짜리로 보고 같은 코드로 돌린다.
    # 분류기·분할·피처를 똑같이 써야 다른 provider 와 숫자를 나란히 놓을 수 있다.
    ap.add_argument("--qfile", default="",
                    help="선별 JSON 의 'good' q_idx 만 남긴다. 공통 문항 축으로 맞출 때 쓴다")
    a = ap.parse_args()

    # --echo-sub 파싱은 행을 읽기 전에 해서, 오타면 비싼 계산 전에 바로 죽게 한다.
    echo_k = {}
    for part in (p.strip() for p in a.echo_sub.split(",") if p.strip()):
        if ":" not in part:
            raise SystemExit(f"--echo-sub 형식 오류: {part!r} (FEAT:K 로 적어라)")
        f, k = part.rsplit(":", 1)
        f = f.strip()
        if f not in WIRE:
            raise SystemExit(f"--echo-sub: {f!r} 는 WIRE 피처가 아니다")
        echo_k[f] = float(k)

    rows = read(a.csv_path)
    # wide CSV(cutoff_ms 없음) 는 전체 창 한 줄짜리 long CSV 로 취급한다.
    if rows and "cutoff_ms" not in rows[0]:
        for r in rows:
            r["cutoff_ms"] = "0"
            r.setdefault("finished_by_cutoff", "1")
            r.setdefault("responded", "1")
        print("[wide CSV] cutoff_ms 열이 없어 전체 창(cutoff 0) 으로만 평가한다.\n")
    if a.qfile:
        import json
        from pathlib import Path
        good = {str(int(x)) for x in
                json.loads(Path(a.qfile).read_text(encoding="utf-8"))["good"]}
        before = len(rows)
        rows = [r for r in rows if str(r.get("q_idx", "")).strip() in good]
        print(f"[선별] {a.qfile} -> {len(rows)}/{before}행\n")
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

    # 에코 정확 교정. 양자화보다 먼저 적용한다 — 에코를 뺀 뒤에 버킷을 나눠야
    # 순서가 말이 된다(반대로 하면 이미 뭉갠 값에서 몇 바이트를 빼는 꼴이다).
    # 보통은 둘 중 하나만 쓴다.
    if echo_k:
        miss = sorted({r["condition"] for r in rows} - set(STRLEN))
        if miss:
            raise SystemExit(f"--echo-sub: 글자 수를 모르는 조건이 있다 {miss}")
        for r in rows:
            L = STRLEN[r["condition"]]
            for f, k in echo_k.items():
                if r.get(f) not in (None, ""):
                    r[f] = str(num(r[f]) - k * L)
        print("[에코 교정] " + ", ".join(f"{f} -= {k}x글자수" for f, k in echo_k.items())
              + "  — 이 수치는 라벨을 쓴 교정판이다. 양자화판과 같이 읽어라.\n")

    # 바이트 피처 양자화. 라벨 에코는 6바이트 규모라 버킷 하나에 흡수되고,
    # 진짜 추론 신호(수천 바이트)는 버킷을 넘나들어 그대로 남는다.
    # 행을 직접 고치므로 아래 모든 적합·중요도 계산에 일괄 적용된다.
    if a.quantize > 0:
        q = a.quantize
        for r in rows:
            for f in BYTE_FEATS:
                if r.get(f) not in (None, ""):
                    r[f] = str(round(num(r[f]) / q) * q)
        print(f"[양자화] {', '.join(BYTE_FEATS)} 를 {q}바이트 버킷으로 반올림했다 "
              f"— 설정 문자열 에코(글자당 2B) 제거용\n")

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
        resp = 100.0 * sum(int(num(r.get("responded"), 1)) for r in g) / len(g)
        fin = 100.0 * sum(int(num(r.get("finished_by_cutoff"), 1)) for r in g) / len(g)
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

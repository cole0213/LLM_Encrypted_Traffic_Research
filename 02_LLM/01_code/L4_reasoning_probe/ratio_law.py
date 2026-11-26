#!/usr/bin/env python3
"""
ratio_law.py — "추론 토큰 배수가 탐지 성능을 예측한다" 의 배수 쪽을 낸다.

왜 필요한가
-----------
2026-11-24 에 모델의 추론 토큰 **배수** `(max+1)/(low+1)` 이 RF Task A 정확도 순위를
거의 그대로 예측한다는 것을 찾았다(n=6, 순위상관 0.94). 그런데 그 배수는 캡처마다
손으로 뽑고 있었다. 캡처가 늘 때마다 다시 뽑아야 하므로 도구로 만든다.

+1 보정을 왜 하나
-----------------
중앙값이 0 인 칸이 있다(sonnet low·medium, terra 쉬운 문항 전 단계).
그냥 나누면 0 으로 나누기가 된다. 전 모델에 같은 보정을 걸므로 **순위는 안 바뀐다.**
다만 sonnet 처럼 분모가 0 인 경우 배수의 **절대값에 의미를 두면 안 된다** —
"가장 크다" 만 쓰고, 축에 그릴 때는 로그축에 따로 표시한다.

배수의 절대값은 문항 집합에 의존한다
------------------------------------
같은 모델이라도 문항 집합이 다르면 배수가 달라진다(sol: 250문항 10.1배 · 교차 50문항 4.2배).
**따라서 캡처 간 비교에는 쓸 수 없고, 같은 문항 축 위에서만 비교한다.**
`--qfile out/qfile_anth250.json` 으로 공통 250문항에 맞춰서 돌려라.

provider 공통 축
----------------
Gemini 는 `xhigh`·`max` 를 지원하지 않는다(gemini_level_probe.py 로 실측 확인).
그래서 Gemini 를 같은 그림에 올리려면 `--levels low,medium,high` 로 **3단 공통축**에서
전 모델을 다시 재야 한다. 5단 수치와 3단 수치를 같은 표에 섞으면 안 된다.

입력 : parse_pcap 산출 CSV 또는 early_detect 산출 long CSV
       (condition · thoughts_tokens · q_idx 열 필요. long CSV 면 cutoff_ms=0 행만 쓴다)
출력 : 표준출력 표. --out 을 주면 CSV 로도 쓴다.
비용 : 0

사용:
    python3 ratio_law.py out/early_*.csv out/gem_v2_all.csv \
        --levels low,medium,high --qfile out/qfile_anth250.json

작성일: 2026-11-26
"""
import csv
import sys
import json
import argparse
from pathlib import Path

import numpy as np

ORD = ["think_low", "think_medium", "think_high", "think_xhigh", "think_max"]


def num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--levels", default="",
                    help="쓸 단계만(쉼표, think_ 접두어 없이). 비우면 파일에 있는 전부. "
                         "Gemini 를 같이 놓으려면 low,medium,high")
    ap.add_argument("--qfile", default="",
                    help="선별 JSON 의 'good' q_idx 만 남긴다. 공통 문항 축으로 맞출 때 필수")
    ap.add_argument("--clean-only", action="store_true", default=True,
                    help="순응·비잘림·1글자 답만(기본). --no-clean-only 로 끈다")
    ap.add_argument("--no-clean-only", dest="clean_only", action="store_false")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    keep_lv = [f"think_{x.strip()}" for x in a.levels.split(",") if x.strip()]
    good = None
    if a.qfile:
        good = {str(int(x)) for x in
                json.loads(Path(a.qfile).read_text(encoding="utf-8"))["good"]}

    recs = []
    print(f"{'캡처':<16}{'n':>6}  {'단계별 추론토큰 중앙값':<34}{'배수':>9}  {'단계':>5}")
    print("-" * 78)
    for path in a.csvs:
        rows = read(path)
        if not rows or "thoughts_tokens" not in rows[0]:
            continue
        tag = Path(path).stem.replace("early_", "")
        # long CSV 면 전체 창만. wide CSV 면 그대로.
        if "cutoff_ms" in rows[0]:
            rows = [r for r in rows if int(num(r["cutoff_ms"])) == 0]
        if good is not None:
            rows = [r for r in rows if str(r.get("q_idx", "")).strip() in good]
        if a.clean_only:
            rows = [r for r in rows
                    if r.get("complied") in ("1", "True", "true")
                    and r.get("truncated") in ("0", "False", "false")
                    and num(r.get("answer_chars"), -1) == 1]
        if keep_lv:
            rows = [r for r in rows if r.get("condition") in keep_lv]
        if not rows:
            print(f"{tag:<16}     0  (조건에 맞는 행 없음)")
            continue

        conds = [c for c in ORD if any(r["condition"] == c for r in rows)]
        med = {}
        for c in conds:
            v = [num(r.get("thoughts_tokens"), 0.0) for r in rows if r["condition"] == c]
            med[c] = float(np.median(v))
        lo, hi = med[conds[0]], med[conds[-1]]
        ratio = (hi + 1.0) / (lo + 1.0)
        shown = " · ".join(f"{med[c]:.0f}" for c in conds)
        flag = " *" if lo == 0 else ""      # 분모가 0 이면 절대값에 의미 없음
        print(f"{tag:<16}{len(rows):>6}  {shown:<34}{ratio:>8.1f}배{flag:<2}{len(conds):>4}단")
        recs.append({"tag": tag, "n": len(rows), "n_levels": len(conds),
                     "medians": shown, "low": lo, "high": hi,
                     "ratio": round(ratio, 3), "zero_denom": int(lo == 0)})

    print("\n* 표시 = low 중앙값이 0 이라 +1 보정에 전적으로 의존한다. "
          "'가장 크다' 외에는 값을 쓰지 마라.")
    print("→ 배수의 절대값은 문항 집합에 의존한다. --qfile 로 같은 문항 축에 맞춘 뒤에만 비교하라.")

    if a.out and recs:
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(recs[0].keys()))
            w.writeheader()
            w.writerows(recs)
        print(f"\n[out] {a.out}  ({len(recs)}행)")


if __name__ == "__main__":
    sys.exit(main())

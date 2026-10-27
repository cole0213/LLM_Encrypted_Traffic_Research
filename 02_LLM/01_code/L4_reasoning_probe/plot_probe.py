"""
plot_probe.py — mini_probe 결과 시각화: 추론 신호가 '길이와 무관하게' 갈리나?

목적:
  probe_results.csv를 읽어 3개 그림을 만든다.
  ① 산점도(핵심): x=output_tokens(답 길이) vs y=ttft_answer_ms, 색=조건.
     → ON 점들이 '같은 길이'에서 위(더 지연)로 뜨면 = 길이 환원 아님 = 연구 성립 신호.
  ② ttft_answer 히스토그램(조건별 겹침).
  ③ total 시간 히스토그램.
  + 조건별 요약 통계 출력.

입력: out/probe_results.csv
출력: out/fig1_scatter.png, out/fig2_ttft_hist.png, out/fig3_total_hist.png
작성일: 2026-09-01
"""

import sys
import csv
import statistics as st
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 인자로 CSV 경로 지정 가능(기본 anthropic 결과). Gemini면:
#   python3 plot_probe.py out/probe_results_gemini.csv
CSV = Path(sys.argv[1] if len(sys.argv) > 1 else "out/probe_results.csv")


def load(path):
    """CSV 로드 + 숫자 파싱, 에러행 제외."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("error"):
                continue
            for k in ["ttft_answer_ms", "total_ms", "output_tokens", "think_dur_ms"]:
                try:
                    r[k] = float(r[k]) if r[k] not in ("", None) else None
                except (ValueError, TypeError):
                    r[k] = None
            rows.append(r)
    return rows


def main():
    if not CSV.exists():
        raise SystemExit(f"{CSV} 없음 — 먼저 mini_probe.py 실행")
    rows = load(CSV)
    conds = sorted({r["condition"] for r in rows})
    colors = {"off": "#888888", "on_low": "#2AA7B0", "on_high": "#0E7C86",
              "on_max": "#E0A63A",
              "think_low": "#2AA7B0", "think_high": "#0E7C86", "think_med": "#E0A63A", "no_think": "#888888"}

    # ① 산점도 — 핵심 (길이 vs 첫 답변 지연)
    plt.figure(figsize=(7, 5))
    for c in conds:
        xs = [r["output_tokens"] for r in rows
              if r["condition"] == c and r["output_tokens"] and r["ttft_answer_ms"]]
        ys = [r["ttft_answer_ms"] for r in rows
              if r["condition"] == c and r["output_tokens"] and r["ttft_answer_ms"]]
        plt.scatter(xs, ys, label=c, alpha=0.7, s=40,
                    color=colors.get(c, None))
    plt.xlabel("output tokens (answer length)")
    plt.ylabel("ttft_answer (ms): request -> first answer token")
    plt.title("Time-to-first-answer vs answer length\n(reasoning=high sits high regardless of length = length-independent signal)")
    plt.legend()
    plt.tight_layout()
    plt.savefig("out/fig1_scatter.png", dpi=130)
    plt.close()

    # ② ttft_answer 히스토그램
    plt.figure(figsize=(7, 4.5))
    for c in conds:
        vs = [r["ttft_answer_ms"] for r in rows
              if r["condition"] == c and r["ttft_answer_ms"]]
        if vs:
            plt.hist(vs, bins=20, alpha=0.55, label=c, color=colors.get(c, None))
    plt.xlabel("ttft_answer (ms)")
    plt.ylabel("count")
    plt.title("Time-to-first-answer distribution by condition")
    plt.legend()
    plt.tight_layout()
    plt.savefig("out/fig2_ttft_hist.png", dpi=130)
    plt.close()

    # ③ total 시간 히스토그램
    plt.figure(figsize=(7, 4.5))
    for c in conds:
        vs = [r["total_ms"] for r in rows if r["condition"] == c and r["total_ms"]]
        if vs:
            plt.hist(vs, bins=20, alpha=0.55, label=c, color=colors.get(c, None))
    plt.xlabel("total (ms)")
    plt.ylabel("count")
    plt.title("Total response time distribution by condition")
    plt.legend()
    plt.tight_layout()
    plt.savefig("out/fig3_total_hist.png", dpi=130)
    plt.close()

    # 요약 통계
    print("=== 조건별 요약 (중앙값) ===")
    print(f"{'condition':10s} {'n':>4s} {'ttft_answer':>12s} {'total_ms':>10s} {'out_tok':>8s}")
    for c in conds:
        sub = [r for r in rows if r["condition"] == c]
        def med(k):
            vs = [r[k] for r in sub if r[k] is not None]
            return round(st.median(vs), 1) if vs else None
        print(f"{c:10s} {len(sub):>4d} {str(med('ttft_answer_ms')):>12s} "
              f"{str(med('total_ms')):>10s} {str(med('output_tokens')):>8s}")
    print("\n그림: out/fig1_scatter.png (핵심), fig2_ttft_hist.png, fig3_total_hist.png")


if __name__ == "__main__":
    main()

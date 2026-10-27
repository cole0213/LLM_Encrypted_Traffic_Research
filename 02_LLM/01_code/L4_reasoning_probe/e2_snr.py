"""
e2_snr.py — E2: 추론깊이 누출의 '세기'를 분포·효과크기(SNR)로 정량화.

목적:
  지금까지 "96% / 평평"은 점 추정. 반복을 늘린 데이터로 pkt_gap 분포를 보고
  서비스마다 짧은추론 vs 긴추론이 '얼마나 갈리는지'를 효과크기(Cohen's d)와
  95% 부트스트랩 신뢰구간으로 표기한다. = 목적 A의 "언제/얼마나 새나"를 수치로.

입력:
  하나 이상의 "label=경로.csv" 인자. 각 CSV = parse_pcap.py 산출(요청별 피처).
  예) python e2_snr.py gemini=out/gem_feats.csv groq=out/groq_feats.csv
  인자 없으면 out/packet_features.csv 를 단일 서비스로 분석.

출력:
  콘솔 표(조건별 분포 + shallow vs deep 효과크기 d + 95% CI + 겹침률).
  선택: --plot 이면 out/e2_snr_<label>.png 분포 히스토그램.

핵심 지표:
  AUC(주 지표) = 무작위 deep 한 건이 무작위 shallow 한 건보다 클 확률.
    0.5 = 구별 불가(우연), 1.0 = 완전 분리. 순위만 쓰므로 극단값에 흔들리지 않는다.
  * Cohen's d 를 주 지표에서 내린 이유: gem_strict 에서 think_high 36콜 중 3콜이
    10초를 넘어(최대 27.5초) 표준편차를 24배 부풀렸고, 그 결과 d 가 0.61로 눌렸다
    (해당 3콜 제외 시 2.88). 같은 데이터에서 AUC 는 0.994로 정확도 0.986과 일치한다.
    d 는 [참고]로만 출력한다.
  * AUC 는 순위만 보므로 '차이의 크기'를 말하지 않는다 → 중앙값 차이를 함께 출력한다.
  * 신뢰구간은 두 가지: 콜 단위 재표집과 질문 단위 재표집(cluster). 후자가 반복 측정
    구조를 반영해 더 보수적이며, 발표·논문에는 이쪽을 쓰는 것이 안전하다.

작성일: 2026-09-05
"""
import sys
import csv
import argparse
import statistics as st
from pathlib import Path

import numpy as np

# 조건 정렬: 얕은 것 → 깊은 것. 서비스마다 있는 것만 사용.
SHALLOW_ORDER = ["no_think", "think_low"]   # 이 중 존재하는 가장 얕은 것을 shallow로
DEEP = "think_high"
FEAT = "pkt_gap_ms"


def load(csv_path):
    """요청별 행 로드. 숫자 필드는 float 변환(빈값=None)."""
    rows = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            for k in (FEAT, "output_tokens", "q_idx"):
                v = r.get(k)
                r[k] = float(v) if v not in (None, "", "None") else None
            rows.append(r)
    return [r for r in rows if r.get(FEAT) is not None]


def cohens_d(a, b):
    """두 표본의 Cohen's d = 평균차 / pooled_std. (b - a 방향)"""
    a, b = np.asarray(a, float), np.asarray(b, float)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return None
    sp = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    return float((b.mean() - a.mean()) / sp) if sp > 0 else None


def boot_ci(a, b, n=2000, seed=0):
    """Cohen's d 의 95% 부트스트랩 신뢰구간(요청 재표집)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    ds = []
    for _ in range(n):
        da = rng.choice(a, len(a), replace=True)
        db = rng.choice(b, len(b), replace=True)
        d = cohens_d(da, db)
        if d is not None:
            ds.append(d)
    if not ds:
        return (None, None)
    return (round(np.percentile(ds, 2.5), 2), round(np.percentile(ds, 97.5), 2))


def auc(a, b):
    """분리도(AUC) = 무작위 deep 한 건이 무작위 shallow 한 건보다 클 확률.

    순위만 쓰므로 이상치에 흔들리지 않는다(Cohen's d 와의 결정적 차이).
    0.5 = 구별 불가(우연), 1.0 = 완전 분리. Cliff's delta = 2*AUC - 1.
    """
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 1 or len(b) < 1:
        return None
    gt = (b[:, None] > a[None, :]).sum()
    eq = (b[:, None] == a[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(a) * len(b)))


def boot_ci_auc(a, b, n=2000, seed=0):
    """AUC 의 95% 부트스트랩 신뢰구간(요청 재표집)."""
    rng = np.random.default_rng(seed)
    a, b = np.asarray(a, float), np.asarray(b, float)
    vals = []
    for _ in range(n):
        v = auc(rng.choice(a, len(a), replace=True), rng.choice(b, len(b), replace=True))
        if v is not None:
            vals.append(v)
    if not vals:
        return (None, None)
    return (round(np.percentile(vals, 2.5), 3), round(np.percentile(vals, 97.5), 3))


def boot_ci_cluster(pairs_a, pairs_b, stat, n=2000, seed=0):
    """질문 단위 재표집(cluster bootstrap) 신뢰구간.

    한 질문의 반복 콜들은 서로 닮아 독립이 아니다. 콜 단위로 재표집하면
    표본이 실제보다 많은 정보를 가진 것처럼 취급돼 구간이 좁게 나온다(과신).
    질문을 통째로 뽑아 그 질문의 콜 전부를 넣는 방식으로 이를 바로잡는다.
    pairs_* = {q_idx: [값,...]} 형태. stat = auc 또는 cohens_d.
    """
    rng = np.random.default_rng(seed)
    qs = sorted(set(pairs_a) | set(pairs_b))
    if len(qs) < 2:
        return (None, None)
    vals = []
    for _ in range(n):
        pick = rng.choice(qs, len(qs), replace=True)
        a = [v for q in pick for v in pairs_a.get(q, [])]
        b = [v for q in pick for v in pairs_b.get(q, [])]
        if len(a) < 2 or len(b) < 2:
            continue
        v = stat(a, b)
        if v is not None:
            vals.append(v)
    if not vals:
        return (None, None)
    r = 3 if stat is auc else 2
    return (round(np.percentile(vals, 2.5), r), round(np.percentile(vals, 97.5), r))


def overlap_rate(a, b):
    """두 분포 겹침 근사: 임계값을 최적으로 잡아도 남는 오분류율(1-분리도).
    간단히 두 표본을 합쳐 최적 단일 임계값의 최소 오류율을 계산."""
    a, b = sorted(a), sorted(b)
    allv = sorted(set(a + b))
    best = 1.0
    for t in allv:
        # a<t 를 shallow, b>=t 를 deep 로 봤을 때 오류율
        err = (sum(x >= t for x in a) + sum(x < t for x in b)) / (len(a) + len(b))
        best = min(best, err, 1 - err)
    return round(best, 3)


def analyze(label, csv_path, plot=False):
    rows = load(csv_path)
    byc = {}
    byq = {}          # {조건: {q_idx: [값,...]}} — 질문 단위 재표집용
    for r in rows:
        byc.setdefault(r["condition"], []).append(r[FEAT])
        q = r.get("q_idx")
        if q is not None:
            byq.setdefault(r["condition"], {}).setdefault(int(q), []).append(r[FEAT])
    print(f"\n===== {label}  (n={len(rows)}, {csv_path}) =====")
    print(f"{'condition':11s} {'n':>3s} {'mean':>8s} {'median':>8s} {'std':>8s}")
    for c, vals in byc.items():
        print(f"{c:11s} {len(vals):>3d} {st.mean(vals):>8.0f} "
              f"{st.median(vals):>8.0f} {(st.pstdev(vals)):>8.0f}")

    shallow_c = next((c for c in SHALLOW_ORDER if c in byc), None)
    if shallow_c is None or DEEP not in byc:
        print("  [주의] shallow/deep 조건이 없어 SNR 생략.")
        return
    a, b = byc[shallow_c], byc[DEEP]
    ov = overlap_rate(a, b)
    # 주 지표 = AUC. 순위 기반이라 이상치(예: 추론이 폭주한 소수 콜)에 흔들리지 않는다.
    au = auc(a, b)
    alo, ahi = boot_ci_auc(a, b)
    acl = boot_ci_cluster(byq.get(shallow_c, {}), byq.get(DEEP, {}), auc)
    verdict = ("큰 분리(잘 샘)" if au and au > 0.80
               else "중간" if au and au > 0.65 else "거의 겹침(안 샘)")
    print(f"\n  [{shallow_c} vs {DEEP}]  중앙값 {st.median(a):.0f}ms → {st.median(b):.0f}ms "
          f"(차이 {st.median(b)-st.median(a):.0f}ms)")
    print(f"  AUC(분리도) = {au:.3f}  (95% CI {alo}~{ahi})  → {verdict}")
    print(f"    질문 단위 재표집 CI = {acl[0]}~{acl[1]}   ← 반복 측정 구조 반영(더 보수적)")
    print(f"    뜻: 무작위로 {DEEP} 한 건과 {shallow_c} 한 건을 뽑으면 "
          f"{au*100:.1f}% 확률로 {DEEP} 쪽이 크다 (0.5=우연)")
    print(f"  최적 임계값 오분류율 = {ov*100:.1f}%  (0=완전분리, 50=구별불가)")
    # 참고용 Cohen's d. 평균·표준편차를 쓰므로 소수의 극단값에 크게 눌린다 → 주 지표로 쓰지 않음.
    d = cohens_d(a, b)
    lo, hi = boot_ci(a, b)
    if d is not None:
        print(f"  [참고] Cohen's d = {d:.2f} (95% CI {lo}~{hi}) "
              f"— 평균·표준편차 기반이라 극단값에 눌림. 판단은 위 AUC로")

    if plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(6, 3))
        plt.hist(a, bins=20, alpha=0.6, label=shallow_c)
        plt.hist(b, bins=20, alpha=0.6, label=DEEP)
        plt.xlabel("pkt_gap_ms"); plt.ylabel("count"); plt.title(f"{label} pkt_gap 분포")
        plt.legend(); plt.tight_layout()
        outp = Path("out") / f"e2_snr_{label}.png"
        plt.savefig(outp, dpi=120); print(f"  [plot] {outp}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data", nargs="*", help="label=경로.csv (여러 개 가능)")
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()
    pairs = []
    if args.data:
        for item in args.data:
            label, _, path = item.partition("=")
            pairs.append((label or "svc", path))
    else:
        pairs = [("service", "out/packet_features.csv")]
    for label, path in pairs:
        if not Path(path).exists():
            print(f"[skip] 파일 없음: {path}"); continue
        analyze(label, path, plot=args.plot)
    print("\n해석: AUC가 0.5에서 멀고 CI 하한이 0.5를 넘으면 = 그 서비스에서 추론깊이가 유의하게 샌다.")
    print("      AUC가 0.5 근처이고 CI가 0.5를 포함하면 = 안 샌다.")
    print("      (순수 네트워크 지터와의 분리는 별도 RTT ping 베이스라인 필요 = 현재 미측정)")


if __name__ == "__main__":
    main()

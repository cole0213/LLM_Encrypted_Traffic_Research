"""
e3_regress.py — Task B: 추론 '양'을 연속값으로 복원한다(회귀).

왜 분류가 아니라 회귀인가:
  Task A 의 정답은 "내가 think_low 로 설정했다"이다. 그런데 설정은 요청이지 사실이 아니다.
  실측상 Gemini think_low 의 83%가 추론 토큰 0 이고, 반대로 low 설정인데 high 중앙값을
  넘는 콜도 4~12% 있다(provider 별). 즉 같은 라벨 안에 0 토큰짜리와 767 토큰짜리가
  같이 들어 있다. 하나로 묶을 수 있는 집단이 아니다.
  → 라벨을 thoughts_tokens(모델이 실제로 한 일)로 바꾸면 이 잡음이 구조적으로 사라진다.

무엇을 재는가 — '정확도' 하나가 아니라 **해상도 곡선**:
  "추론량이 Δ 토큰 이상 차이나는 두 콜을, 트래픽만 보고 올바른 순서로 세울 확률"
  을 Δ 를 키워가며 잰다. Δ 가 작을수록 어렵다. 이 곡선이
  "몇 토큰 단위까지 구분 가능한가"에 대한 답이고, 연구의 '경계 특성화' 주장에 맞는 형태다.

평가 규칙은 e1_from_csv.py 와 동일하게 맞춘다 — 질문별 GroupKFold(leave-one-question-out).
같은 질문이 학습·평가에 동시에 들어가면 난도를 외워서 성능이 부풀기 때문이다.

입력: parse_pcap.py 산출 CSV(복수 가능). thoughts_tokens·q_idx 필수.
출력: 표준출력 — 피처군별 순위상관/오차, 해상도 곡선, 대조군.
사용: python3 e3_regress.py out/groq3_120b.csv
      python3 e3_regress.py out/groq3_*.csv --reasoned-only
작성일: 2026-11-03
"""
import csv
import argparse
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold

# e1_from_csv.py 와 같은 피처 정의를 쓴다. 두 Task 의 수치를 나란히 놓으려면
# 입력이 같아야 한다 — 여기서만 피처를 바꾸면 "회귀가 더 낫다"가 피처 덕인지
# 라벨 덕인지 구분할 수 없게 된다.
PKT_FEATS = ["pkt_gap_ms", "up_bytes", "down_bytes", "up_pkts", "down_pkts",
             "down_iat_mean_ms", "down_pkt_mean", "down_pkt_max",
             "down_iat_max_ms", "down_iat_p90_ms", "stall_total_ms", "down_iat_first_ms"]
DOWN_FEATS = [f for f in PKT_FEATS if not f.startswith("up_")]
TIME_FEATS = ["pkt_gap_ms", "down_iat_mean_ms",
              "down_iat_max_ms", "down_iat_p90_ms", "stall_total_ms", "down_iat_first_ms"]


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load(path):
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = []
    for r in rows:
        # Gemini no_think 는 thoughts_tokens 가 빈칸으로 온다 = 추론 0.
        th = _num(r.get("thoughts_tokens"))
        if th is None:
            th = 0.0
        # 토큰 한계까지 간 콜은 추론량이 '잘린' 값이라 회귀 타깃으로 쓰면 안 된다.
        if r.get("truncated") in ("1", "True", "true"):
            continue
        out.append({
            "y": th,
            "q": r.get("q_idx"),
            "cond": r.get("condition", ""),
            "feat": {k: _num(r.get(k)) for k in PKT_FEATS},
            # 0.0 은 falsy 라 or 체인이 다음 값으로 넘어간다. Groq 의 output_tokens 는
            # 추론을 포함하므로 그게 '길이 대조군'에 섞이면 라벨을 보는 셈이 된다.
            "alen": (_num(r.get("answer_tokens"))
                     if _num(r.get("answer_tokens")) is not None
                     else (_num(r.get("output_tokens")) or 0.0)),
            "achars": _num(r.get("answer_chars")) or 0.0,
            "arm": r.get("arm") or "",
        })
    return out


def _ranks(a):
    """동점 평균순위. 순위상관 계산용."""
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="mergesort")
    r = np.empty(len(a), dtype=float)
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and a[order[j + 1]] == a[order[i]]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = _ranks(a), _ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def matrix(rows, feats):
    """결측은 열 중앙값으로 채운다(옛 CSV 에 없는 열 대비)."""
    X = np.array([[r["feat"].get(f) for f in feats] for r in rows], dtype=float)
    for c in range(X.shape[1]):
        col = X[:, c]
        if np.all(np.isnan(col)):
            X[:, c] = 0.0
        elif np.any(np.isnan(col)):
            X[np.isnan(col), c] = np.nanmedian(col)
    return X


def cv_predict(X, y, groups):
    """질문별 GroupKFold. 각 폴드에서 '그 질문을 한 번도 안 본' 모델이 예측한다."""
    n_q = len(set(groups))
    gkf = GroupKFold(n_splits=min(n_q, len(y)))
    pred = np.zeros(len(y))
    for tr, te in gkf.split(X, y, groups):
        m = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
        m.fit(X[tr], y[tr])
        pred[te] = m.predict(X[te])
    return pred


def resolution_curve(y, pred, deltas):
    """추론량이 Δ 이상 차이나는 쌍을 올바른 순서로 세울 확률.

    Δ=0 이면 보통의 순위 일치율(AUC 와 같은 계열)이고, Δ 를 키우면
    '확실히 다른 두 콜'만 남아 쉬워진다. 곡선이 꺾이는 지점이 실질 해상도다.

    주의 — 추론량이 **똑같은** 쌍은 애초에 정답 순서가 없으므로 Δ 와 무관하게 제외한다.
    예전엔 Δ=0 에서 이 쌍들이 전부 '오답'으로 세어져, Gemini 처럼 추론 0 이 많은
    데이터(270콜 중 165개)에서 13,530 쌍이 통째로 깎여 0.718 이 나왔다.
    데이터의 성질이지 탐지력이 아니다.
    """
    y = np.asarray(y, dtype=float)
    p = np.asarray(pred, dtype=float)
    out = []
    n = len(y)
    for d in deltas:
        ok = tot = 0
        for i in range(n):
            dy = y[i + 1:] - y[i]
            dp = p[i + 1:] - p[i]
            # dy == 0 인 쌍은 정답 순서가 정의되지 않는다. 항상 뺀다.
            sel = (np.abs(dy) >= d) & (dy != 0)
            if not np.any(sel):
                continue
            tot += int(sel.sum())
            # 예측 차이가 0 이면 동점 → 0.5 로 센다(무작위와 같음).
            agree = np.sign(dy[sel]) == np.sign(dp[sel])
            ties = dp[sel] == 0
            ok += float((agree & ~ties).sum()) + 0.5 * float(ties.sum())
        out.append((d, ok / tot if tot else None, tot))
    return out


def report(rows, title, args):
    y = np.array([r["y"] for r in rows], dtype=float)
    groups = [r["q"] for r in rows]
    n_q = len(set(groups))
    print(f"\n{'=' * 78}\n  {title}\n{'=' * 78}")
    print(f"n = {len(rows)},  문항 {n_q}개")
    if n_q < 3:
        print("문항이 3개 미만이라 질문별 CV 불가. 건너뜀.")
        return
    if y.std() == 0:
        print("추론 토큰이 전부 같은 값이라 회귀 불가. 건너뜀.")
        return

    # 조건별 실제 분포 — 무엇을 회귀하는지 먼저 보여준다.
    print(f"\n  [타깃 분포] thoughts_tokens")
    for c in sorted({r["cond"] for r in rows}):
        v = np.array([r["y"] for r in rows if r["cond"] == c])
        print(f"    {c:<12} n={len(v):>4}  중앙 {np.median(v):>7.0f}  "
              f"범위 {v.min():>5.0f}~{v.max():>6.0f}  추론0 {int((v == 0).sum())}건")

    # --- 피처군별 ---
    sets = [("packet-down (크기+타이밍)", DOWN_FEATS),
            ("timing-only (정본)", TIME_FEATS),
            ("packet-all (업링크 포함)", PKT_FEATS)]
    print(f"\n  [회귀 성능] 질문별 GroupKFold")
    print(f"    {'피처군':<26}{'순위상관':>9}{'MAE':>9}{'중앙오차':>9}{'R2':>8}")

    best = None
    for name, fs in sets:
        X = matrix(rows, fs)
        p = cv_predict(X, y, groups)
        rho = spearman(y, p)
        mae = float(np.mean(np.abs(y - p)))
        med = float(np.median(np.abs(y - p)))
        ss = float(1 - np.sum((y - p) ** 2) / np.sum((y - y.mean()) ** 2))
        print(f"    {name:<26}{(f'{rho:.3f}' if rho else '-'):>9}"
              f"{mae:>9.1f}{med:>9.1f}{ss:>8.3f}")
        if name.startswith("timing-only"):
            best = (name, p)

    # --- 대조군: 답 길이만 / 평균만 ---
    # 답 길이가 완전히 고정되면(arm 0 에서 Groq 10, Gemini 1) 분산이 0 이라
    # 모델이 폴드별 평균만 뱉는다. 그 평균이 폴드마다 조금씩 달라 ±0.3 수준의
    # 가짜 상관이 찍힌다(3차에서 -0.391 이 나왔다). 분산 0 이면 '신호 없음'으로 못박는다.
    Xlen = np.array([[r["alen"]] for r in rows], dtype=float)
    if np.std(Xlen) == 0:
        plen = np.full(len(y), y.mean())
        rlen = None
    else:
        plen = cv_predict(Xlen, y, groups)
        rlen = spearman(y, plen)
    mae_mean = float(np.mean(np.abs(y - y.mean())))
    ltag = "[대조] length-only" + (" (분산0)" if rlen is None else "")
    print(f"    {ltag:<26}{(f'{rlen:.3f}' if rlen is not None else '-'):>9}"
          f"{float(np.mean(np.abs(y - plen))):>9.1f}"
          f"{float(np.median(np.abs(y - plen))):>9.1f}"
          f"{float(1 - np.sum((y - plen) ** 2) / np.sum((y - y.mean()) ** 2)):>8.3f}")
    print(f"    {'[대조] 평균만 예측':<26}{'0.000':>9}{mae_mean:>9.1f}"
          f"{float(np.median(np.abs(y - y.mean()))):>9.1f}{0.0:>8.3f}")
    print(f"\n    MAE 가 '평균만 예측'보다 작아야 의미가 있다. 순위상관은 해상도의 요약값이다.")

    # --- 해상도 곡선 ---
    if best:
        name, p = best
        print(f"\n  [해상도 곡선] {name} 기준")
        print(f"    추론량이 Δ 이상 차이나는 두 콜을 올바른 순서로 세울 확률")
        print(f"    {'Δ(토큰)':>9}{'정확도':>9}{'쌍 수':>10}")
        curve = resolution_curve(y, p, args.deltas)
        for d, acc, tot in curve:
            if acc is None:
                print(f"    {d:>9}{'-':>9}{0:>10}   (해당 쌍 없음)")
            else:
                print(f"    {d:>9}{acc:>9.3f}{tot:>10}")
        for target in (0.80, 0.90):
            hit = next((d for d, a, _ in curve if a is not None and a >= target), None)
            if hit is not None:
                print(f"    → {target:.0%} 정확도는 Δ ≥ {hit} 토큰부터")
            else:
                print(f"    → {target:.0%} 정확도에 도달하는 Δ 없음(시험 범위 내)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument("--reasoned-only", action="store_true",
                    help="추론>0 콜만. Gemini 처럼 0 에 쏠린 데이터에서 "
                         "'0 vs 그외'가 아니라 '양'을 정말 재는지 확인용.")
    ap.add_argument("--deltas", type=int, nargs="+",
                    default=[0, 10, 25, 50, 100, 200, 400, 800],
                    help="해상도 곡선의 Δ 목록(토큰).")
    ap.add_argument("--by-arm", action="store_true",
                    help="arm 열이 있으면 arm 별로 나눠서 평가.")
    a = ap.parse_args()

    for path in a.csv:
        rows = load(path)
        if a.reasoned_only:
            rows = [r for r in rows if r["y"] > 0]
        if not rows:
            print(f"\n[빈 데이터] {path}")
            continue
        tag = " (추론>0만)" if a.reasoned_only else ""
        # 답 길이를 제목에 박는다. 같은 수치라도 '답 1글자에서 잰 상한'인지
        # '현실 길이에서 잰 값'인지가 해석을 완전히 바꾸기 때문이다.
        if a.by_arm and len({r["arm"] for r in rows}) > 1:
            for arm in sorted({r["arm"] for r in rows}):
                sr = [r for r in rows if r["arm"] == arm]
                am = np.median([r["achars"] for r in sr])
                report(sr, f"{path}{tag}  [arm={arm or '0'}, 답 중앙 {am:.0f}자]", a)
        else:
            am = np.median([r["achars"] for r in rows])
            arm = next(iter({r["arm"] for r in rows}), "")
            report(rows, f"{path}{tag}  [arm={arm or '0'}, 답 중앙 {am:.0f}자]", a)


if __name__ == "__main__":
    main()

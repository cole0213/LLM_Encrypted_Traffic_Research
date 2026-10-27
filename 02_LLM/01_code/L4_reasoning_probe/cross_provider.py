"""
cross_provider.py — 교차 전이 실험: 한 provider에서 학습한 분류기가 다른 provider에 통하는가.

목적:
  설계의 'within-provider 평가' 원칙을 논리가 아니라 숫자로 뒷받침한다.
  gem_strict / groq_strict 실측에서 같은 피처가 provider별로 방향이 반대였다.
    Gemini : down_iat_mean 27 -> 18ms  (깊은 추론일수록 간격이 좁아짐)
    Groq   : down_iat_mean 21 -> 99ms  (깊은 추론일수록 간격이 넓어짐)
  방향이 뒤집혔으므로 교차 전이 시 우연(0.5) 이하로 떨어질 것으로 예상한다.
  떨어지면 = provider를 섞어 학습/평가하면 안 된다는 직접 근거가 된다.

비교 조건:
  두 CSV에 공통으로 있는 think_low vs think_high 만 사용한다.
  (Gemini 는 no_think 가 있고 Groq 는 think_med 가 있어 서로 다르므로 교집합으로 맞춘다.)

피처:
  하향(응답) 피처만 사용한다. 업링크는 요청 크기로 설정값이 누출되므로 제외
  (gem_strict 에서 up_bytes 중앙값 no 808 / low 875 / high 876 — no 만 설정 필드를 안 보냄).

입력: label=경로.csv 두 개 이상.
  예) python3 cross_provider.py gemini=out/gem_strict.csv groq=out/groq_strict.csv
출력: 콘솔 — 자기 자신 평가(참고), 교차 전이 정확도, 혼동행렬, 합쳐서 학습한 경우.
작성일: 2026-10-02
"""
import sys
import csv
import itertools

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

# 하향 피처만. 업링크(up_*)는 요청에 실린 설정값을 누출하므로 쓰지 않는다.
FEATS = ["pkt_gap_ms", "down_bytes", "down_pkts",
         "down_iat_mean_ms", "down_pkt_mean", "down_pkt_max"]
PAIR = ["think_low", "think_high"]      # 두 provider 공통 조건


def load(path):
    """feats CSV → 지정 조건만, 피처 결측 없는 행만."""
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("condition") not in PAIR:
                continue
            try:
                vals = [float(r[k]) for k in FEATS]
            except (TypeError, ValueError, KeyError):
                continue            # 결측(예: 토큰 한계로 답이 없던 콜)은 버린다
            if any(np.isnan(v) for v in vals):
                continue
            rows.append({"X": vals, "y": r["condition"], "q": int(float(r["q_idx"]))})
    return rows


def mat(rows):
    return (np.array([r["X"] for r in rows], float),
            np.array([r["y"] for r in rows]),
            np.array([r["q"] for r in rows]))


def rf():
    return RandomForestClassifier(n_estimators=300, random_state=42)


def within(rows, label):
    """참고용: 같은 provider 안에서 질문별 교차검증(기존 결과와 맞춰보기 위함)."""
    X, y, g = mat(rows)
    n_q = len(set(g))
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=n_q).split(X, y, g):
        m = rf().fit(X[tr], y[tr])
        yt.extend(y[te]); yp.extend(m.predict(X[te]))
    acc = accuracy_score(yt, yp)
    print(f"  [{label} 안에서] 질문별 교차검증 정확도 = {acc:.3f}  (n={len(rows)})")
    return acc


def transfer(src, dst, s_label, d_label):
    """src 전체로 학습 → dst 전체로 평가. 데이터셋이 달라 교차검증이 필요 없다."""
    Xs, ys, _ = mat(src)
    Xd, yd, _ = mat(dst)
    m = rf().fit(Xs, ys)
    pred = m.predict(Xd)
    acc = accuracy_score(yd, pred)
    print(f"\n  [{s_label} 학습 → {d_label} 평가] 정확도 = {acc:.3f}   (우연 = 0.500)")
    print("    혼동행렬 (행=정답, 열=예측) " + str(PAIR) + ":")
    for lab, row in zip(PAIR, confusion_matrix(yd, pred, labels=PAIR)):
        print(f"      {lab:11s} {row}")
    if acc < 0.5:
        print("    → 우연보다 낮음 = 학습한 규칙이 거꾸로 적용되고 있다는 뜻")
    return acc


def pooled(sets):
    """두 provider를 섞어 학습/평가하면 어떻게 되는지(= '합쳐서 하면 안 되냐'에 대한 답).

    질문 번호가 provider마다 겹치므로 provider별로 떼어 group 을 만든다.
    """
    rows, groups = [], []
    for k, (label, rs) in enumerate(sets):
        for r in rs:
            rows.append(r); groups.append(k * 1000 + r["q"])
    X = np.array([r["X"] for r in rows], float)
    y = np.array([r["y"] for r in rows])
    g = np.array(groups)
    n_q = len(set(g))
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=n_q).split(X, y, g):
        m = rf().fit(X[tr], y[tr])
        yt.extend(y[te]); yp.extend(m.predict(X[te]))
    print(f"\n  [둘을 섞어 학습·평가] 정확도 = {accuracy_score(yt, yp):.3f}  (n={len(rows)})")
    print("    ※ 각 provider 안에서 따로 돌린 값보다 낮으면 = 섞으면 손해라는 뜻")


def direction(sets):
    """피처별로 '깊은 추론일 때 커지나 작아지나'를 provider끼리 비교한다.

    방향이 반대인 피처가 있으면 전이가 실패하는 직접 원인이 된다.
    """
    print("\n=== 피처 방향 비교 (깊은 추론일 때 ↑커짐 / ↓작아짐) ===")
    print("  " + "피처".ljust(20) + "".join(l.ljust(16) for l, _ in sets))
    for i, f in enumerate(FEATS):
        line = "  " + f.ljust(20)
        signs = []
        for _, rs in sets:
            lo = np.median([r["X"][i] for r in rs if r["y"] == "think_low"])
            hi = np.median([r["X"][i] for r in rs if r["y"] == "think_high"])
            s = "↑" if hi > lo else ("↓" if hi < lo else "=")
            signs.append(s)
            line += f"{s} {lo:.0f}->{hi:.0f}".ljust(16)
        if len(set(signs)) > 1:
            line += "  ← 방향 반대"
        print(line)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print("사용: python3 cross_provider.py gemini=out/gem_strict.csv groq=out/groq_strict.csv")
        return
    sets = []
    for item in args:
        label, _, path = item.partition("=")
        rows = load(path)
        if not rows:
            print(f"[skip] {path} 에 {PAIR} 조건 데이터가 없음"); continue
        sets.append((label or path, rows))
    if len(sets) < 2:
        print("provider 가 2개 이상 필요함"); return

    print(f"\n{'='*60}\n비교 조건: {PAIR[0]} vs {PAIR[1]}   |   피처: 하향 {len(FEATS)}개 (업링크 제외)")
    print(f"{'='*60}\n[기준선] 같은 provider 안에서의 성능")
    for label, rows in sets:
        within(rows, label)

    print(f"\n{'-'*60}\n[본 실험] 교차 전이")
    for (la, ra), (lb, rb) in itertools.permutations(sets, 2):
        transfer(ra, rb, la, lb)

    print(f"\n{'-'*60}")
    pooled(sets)
    direction(sets)
    print("\n해석: 교차 전이가 우연(0.5) 근처나 그 아래면, 추론 신호가 트래픽에 실리는 방식이")
    print("      provider마다 달라 한쪽에서 배운 규칙이 다른 쪽에 통하지 않는다는 뜻이다.")
    print("      = 모델/서비스를 섞지 않고 같은 provider 안에서 평가해야 한다는 근거.")


if __name__ == "__main__":
    main()

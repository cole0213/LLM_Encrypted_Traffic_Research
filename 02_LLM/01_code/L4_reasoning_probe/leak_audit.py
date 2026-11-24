#!/usr/bin/env python3
"""
leak_audit.py — "추론을 읽은 것"과 "설정의 흔적을 읽은 것"을 가른다.

왜 필요한가
-----------
이 연구는 같은 종류의 누출에 **세 번** 물렸다.
  ① `up_bytes` 67바이트 — `no_think` 만 `thinking_config` 를 안 보내 요청이 짧았다 (0.722 → 0.602)
  ② Groq `down_bytes` — usage 객체에 찍힌 토큰 수의 **자릿수** 차이 (AUC 0.85~0.91 → 0)
  ③ OpenAI effort 문자열 에코 — 응답이 "low"/"medium"/... 을 그대로 되돌려보내고 그 값이
     스트림에 두 번 실려, `down_bytes` 가 **설정 글자 수 x 2 바이트**만큼 달라진다.
     500ms 창에서는 다른 피처가 전부 상수라 이 6바이트만으로 75% 가 나왔다 (2026-11-24).

셋 다 **분류기는 잘 맞히는데 맞힌 근거가 추론이 아닌** 경우다. 조용히 틀리기 때문에
에러도 안 나고 수치는 오히려 좋아 보인다. ③ 에서는 피처 *이름* 만 보고
"누출 아님" 이라고 적었다가 놓쳤다 — **이름이 깨끗해도 값이 라벨을 베낄 수 있다.**

두 가지 검사
------------
**검사 A — 같은 문항 안에서, 둘 다 추론 0 인 조건 쌍을 비교한다 (핵심).**
  모델이 추론을 **하지 않은** 콜만 남기면(`thoughts_tokens == 0`) 조건 간 차이는
  **원리적으로 추론일 수 없다.** 다만 그냥 모아서 분류하면 **선택 효과**에 걸린다 —
  low 에서 0 이 되는 문항은 가장 쉬운 것들이고 medium 에서 0 이 되는 문항은 더 넓은
  집합이라, 분류기가 '조건' 이 아니라 '문항 난도' 를 맞히고도 점수가 오른다.
  그래서 **같은 문항 안에서 둘 다 0 인 조건 쌍**만 본다. 문항이 상수가 되므로
  남는 차이는 추론도 난도도 아니고 **설정 그 자체뿐**이다.
  판정은 부호검정 — 한 피처가 한쪽으로 쏠리면(50% 에서 멀면) 누출이다.
  `--reasoned-only` 대조(추론한 콜만 보기)의 정확한 반대편이다.

**검사 B — 피처가 설정 '문자열 길이' 를 따라가는가.**
  effort 문자열 길이는 low 3 · medium 6 · high 4 · xhigh 5 · max 3 으로
  **추론 깊이 순서와 전혀 다르다.** 어떤 피처가 깊이가 아니라 이 길이를 따라간다면
  그것은 에코 누출이다. 피처별로 (길이 → 값) 최소제곱 기울기와 상관을 재서,
  상관이 높고 기울기가 0 이 아니면 표시한다.
  검사 B 는 추론 0 행이 없어도 돌아가므로 검사 A 의 보완이다.

읽는 법
-------
  검사 A 가 우연 근처(±5%p) → 그 캡처에는 추론과 무관한 라벨 누출이 없다.
  검사 A 가 우연보다 한참 높다 → **그 캡처의 Task A 수치를 전부 보류한다.**
    이어서 검사 B 와 피처별 표를 보고 어느 열이 범인인지 찾는다.
  검사 B 에서 `<<` 가 붙은 피처 → 설정 문자열 길이를 베끼고 있다. 양자화하거나 뺀다.
    (`early_eval.py --quantize 100` 이 바이트 계열에 대한 처방이다.)

입력: out/early_<tag>.csv (cutoff_ms · condition · thoughts_tokens 열 필요)
출력: 표준출력 표

사용:
  python3 leak_audit.py out/early_luna250.csv
  python3 leak_audit.py out/early_*.csv --cutoff 0

작성일: 2026-11-24
"""
import csv
import sys
import argparse

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score

WIRE = ["pkt_gap_ms", "up_pkts", "down_pkts", "up_bytes", "down_bytes",
        "down_pkt_mean", "down_pkt_max", "down_iat_mean_ms", "down_iat_max_ms",
        "down_iat_p90_ms", "down_iat_p99_ms", "stall_total_ms", "stall_count",
        "down_iat_first_ms", "n_pkts_window", "responded"]

ORD = ["think_low", "think_medium", "think_high", "think_xhigh", "think_max"]

# effort 문자열의 글자 수. 추론 깊이 순서(3<6<4<5<3)와 일치하지 않는다는 점이 핵심이다 —
# 그래서 깊이를 읽은 것과 문자열을 읽은 것을 구별할 수 있다.
STRLEN = {"think_low": 3, "think_medium": 6, "think_high": 4,
          "think_xhigh": 5, "think_max": 3}


def num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def thoughts(r):
    """추론 토큰. **빈칸은 0 이다.**

    2026-11-24 에 여기서 한 번 틀렸다. OpenAI 는 추론이 0 이면 usage 에서 필드를 아예
    빼버려 CSV 에 빈칸으로 들어온다(terra250 110행 · sol250 43행). 빈칸을 '모름' 으로
    치고 제외했더니 "추론 0 행 0개" 가 나와 검사 A 가 통째로 안 돌았다.

    주의: 이 치환은 **직결 캡처에만** 안전하다. 게이트웨이(BAZE) 경유 데이터는
    빈칸이 '안 알려줌'(정보 부재)이라 0 으로 접으면 전체가 '추론 0' 으로 둔갑한다.
    → 노트 "게이트웨이는 추론 토큰을 안 준다" 항목. 본 저장소의 early_*.csv 는 전부 직결이다.
    """
    return num(r.get("thoughts_tokens"), 0.0)


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def cv_acc(rows, trees, seed, folds):
    """family 단위 GroupKFold 정확도(%)와 실제 폴드 수."""
    X = np.array([[num(r.get(f)) for f in WIRE] for r in rows], dtype=float)
    y = np.array([r["condition"] for r in rows])
    groups = np.array([r.get("family") or r["q_idx"] for r in rows])
    k = min(folds, len(set(groups)))
    if k < 2:
        return None, 0
    yt, yp = [], []
    for tr, te in GroupKFold(n_splits=k).split(X, y, groups):
        if len(set(y[tr])) < 2:
            continue
        clf = RandomForestClassifier(n_estimators=trees, random_state=seed, n_jobs=-1)
        clf.fit(X[tr], y[tr])
        yp.extend(clf.predict(X[te]))
        yt.extend(y[te])
    return (100.0 * accuracy_score(yt, yp) if yt else None), k


def median_by_cond(rows, feat):
    out = {}
    for c in ORD:
        v = [num(r.get(feat)) for r in rows if r["condition"] == c]
        if v:
            out[c] = float(np.median(v))
    return out


def strlen_fit(med):
    """설정 글자 수 -> 피처 중앙값 최소제곱 기울기와 피어슨 상관."""
    pts = [(STRLEN[c], med[c]) for c in med if c in STRLEN]
    if len(pts) < 3:
        return 0.0, 0.0
    x = np.array([p[0] for p in pts], dtype=float)
    y = np.array([p[1] for p in pts], dtype=float)
    if x.std() == 0 or y.std() == 0:
        return 0.0, 0.0
    slope = np.polyfit(x, y, 1)[0]
    r = float(np.corrcoef(x, y)[0, 1])
    return float(slope), r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csvs", nargs="+")
    ap.add_argument("--cutoff", type=int, default=0,
                    help="검사할 cutoff_ms. 기본 0(전체 창)")
    ap.add_argument("--trees", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--min-pairs", type=int, default=20,
                    help="검사 A 를 돌릴 최소 조건 쌍 수")
    ap.add_argument("--skew", type=float, default=15.0,
                    help="검사 A 에서 누출로 표시할 50%% 로부터의 쏠림(%%p)")
    ap.add_argument("--min-dec", type=int, default=30,
                    help="부호검정에 쓸 최소 '동률 아닌' 쌍 수")
    ap.add_argument("--z", type=float, default=3.0,
                    help="부호검정 z 임계. 다중검정 보정분 포함(3.0 ≈ 양측 p 0.0027)")
    ap.add_argument("--corr", type=float, default=0.90,
                    help="검사 B 에서 의심 표시할 |상관| 임계값")
    a = ap.parse_args()

    for path in a.csvs:
        rows = read(path)
        if not rows or "thoughts_tokens" not in rows[0]:
            print(f"[건너뜀] {path} — thoughts_tokens 열이 없다")
            continue
        tag = path.split("early_")[-1].replace(".csv", "")
        g = [r for r in rows if int(num(r["cutoff_ms"])) == a.cutoff]
        if not g:
            print(f"[건너뜀] {tag} — cutoff {a.cutoff} 행이 없다")
            continue

        lab = "전체 창" if a.cutoff == 0 else f"{a.cutoff}ms 창"
        print(f"\n########## {tag}   ({lab})")

        # ── 검사 A — 같은 문항 안에서, 둘 다 추론 0 인 조건 쌍을 비교한다 ──────
        #
        # 왜 짝지어야 하나 (2026-11-24 설계 수정):
        #   추론 0 행만 모아 그냥 분류하면 **선택 효과**에 걸린다. low 에서 0 이 되는 문항은
        #   가장 쉬운 것들이고, medium 에서 0 이 되는 문항은 더 넓은 집합이다. 즉 조건마다
        #   문항 구성이 달라서, 분류기가 '조건' 이 아니라 '문항 난도' 를 맞히고도 점수가 오른다.
        #   그것을 누출로 오판하면 멀쩡한 결과를 버리게 된다.
        #   그래서 **같은 문항 안에서 둘 다 추론 0 인 조건 쌍**만 본다. 문항이 상수가 되므로
        #   남는 차이는 추론도 난도도 아니다 — 설정 그 자체뿐이다.
        #
        # 판정: 부호검정. 한 피처가 두 조건 사이에서 한쪽으로 쏠리면(50% 에서 멀면) 누출이다.
        zero_by_q = {}
        for r in g:
            if thoughts(r) == 0:
                zero_by_q.setdefault(r["q_idx"], {})[r["condition"]] = r
        pairs = []          # (문항, 조건A, 조건B, 행A, 행B)
        for q, by_c in zero_by_q.items():
            cs = [c for c in ORD if c in by_c]
            for i in range(len(cs)):
                for j in range(i + 1, len(cs)):
                    pairs.append((q, cs[i], cs[j], by_c[cs[i]], by_c[cs[j]]))
        if len(pairs) < a.min_pairs:
            n_zero = sum(len(v) for v in zero_by_q.values())
            print(f"  [검사 A] 추론 0 행 {n_zero}개 → 같은 문항 안 조건 쌍 {len(pairs)}개 "
                  f"— {a.min_pairs}개 미만이라 판정 불가")
        else:
            print(f"  [검사 A] 같은 문항·둘 다 추론 0 인 조건 쌍 {len(pairs)}개 "
                  f"(문항 {len(zero_by_q)}개). 부호검정 — 50% 에서 멀면 누출")
            worst = []
            for f in WIRE:
                hi = lo = tie = 0
                for _, ca, cb, ra, rb in pairs:
                    va, vb = num(ra.get(f)), num(rb.get(f))
                    # 조건 순서를 ORD 기준으로 맞춘다(뒤 조건이 더 깊은 설정).
                    if va < vb:
                        hi += 1
                    elif va > vb:
                        lo += 1
                    else:
                        tie += 1
                dec = hi + lo
                # 동률이 많으면 판정 쌍이 몇 개 안 남는다. 그 상태의 쏠림은 못 믿는다
                # (2026-11-24: haiku 의 stall_total_ms 가 판정 쌍 10개로 80% 가 떠서
                #  누출처럼 보였는데, n=10 이면 p≈0.11 이라 아무 말도 못 한다).
                if dec < a.min_dec:
                    continue
                pct = 100.0 * hi / dec
                # 부호검정 정규근사 z. 다중검정을 감안해 임계를 따로 둔다.
                z = abs(hi - dec / 2.0) / (dec ** 0.5 / 2.0)
                worst.append((z, f, pct, dec, tie))
            worst.sort(reverse=True)
            # 다중검정 보정: 피처 수 x 캡처 수만큼 검정하므로 p<0.05 하나는 우연으로 나온다.
            # 본페로니 근사로 z 임계를 올린다(기본 3.0 ≈ 양측 p 0.0027).
            flagged = [w for w in worst if w[0] >= a.z and abs(w[2] - 50.0) >= a.skew]
            if not flagged:
                near = worst[0] if worst else None
                extra = (f"  (최대 쏠림 {near[1]} {near[2]:.1f}%, z={near[0]:.1f})"
                         if near else "")
                print(f"           임계(쏠림 {a.skew:.0f}%p 이상 & z≥{a.z}) 넘는 피처 없음  "
                      f"→  깨끗{extra}")
            else:
                print(f"           {'피처':<20}{'뒤 조건이 큼':>12}{'z':>7}{'동률':>7}{'판정 쌍':>8}")
                for z, f, pct, dec, tie in flagged[:6]:
                    print(f"           {f:<20}{pct:>11.1f}%{z:>7.1f}{tie:>7}{dec:>8}  <<")
                print("           → 같은 문항·추론 0 인데 피처가 쏠린다 = 설정이 직접 새고 있다.")
                print("           ※ 전체 캡처를 한 번에 돌리면 피처 x 캡처 만큼 검정한다. "
                      "하나쯤 걸리는 것은 우연일 수 있으니 기전까지 확인하라.")

        # ── 검사 B ──────────────────────────────────────────────────────
        print(f"  [검사 B] 설정 문자열 길이(low3 med6 high4 xhigh5 max3)를 따라가는 피처")
        hits = []
        for f in WIRE:
            med = median_by_cond(g, f)
            if len(med) < 3:
                continue
            vals = list(med.values())
            if max(vals) - min(vals) == 0:
                continue                       # 완전 상수는 누출도 신호도 아니다
            slope, r = strlen_fit(med)
            if abs(r) >= a.corr and slope != 0:
                hits.append((f, slope, r, med))
        if not hits:
            print("           없음")
        for f, slope, r, med in sorted(hits, key=lambda h: -abs(h[2])):
            print(f"           {f:<20} 기울기 {slope:>9.2f}/글자  상관 {r:>6.3f}  <<")
            print("                                " +
                  "  ".join(f"{c.replace('think_','')}={med[c]:.0f}"
                            for c in ORD if c in med))

        # 참고: 추론 깊이 순서를 따라가는지도 같이 본다. 둘 다 높으면 섞여 있는 것이다.
        depth = {c: i for i, c in enumerate(ORD)}
        both = []
        for f in WIRE:
            med = median_by_cond(g, f)
            if len(med) < 3 or max(med.values()) - min(med.values()) == 0:
                continue
            x = np.array([depth[c] for c in med if c in depth], dtype=float)
            y = np.array([med[c] for c in med if c in depth], dtype=float)
            if x.std() == 0 or y.std() == 0:
                continue
            rd = float(np.corrcoef(x, y)[0, 1])
            _, rs = strlen_fit(med)
            if abs(rd) >= a.corr:
                both.append((f, rd, rs))
        if both:
            print("  [참고] 추론 깊이 순서를 따라가는 피처 (이쪽이 진짜 신호여야 한다)")
            for f, rd, rs in sorted(both, key=lambda h: -abs(h[1])):
                note = "  (문자열 길이와도 상관 높음 — 섞여 있다)" if abs(rs) >= a.corr else ""
                print(f"           {f:<20} 깊이상관 {rd:>6.3f}  문자열상관 {rs:>6.3f}{note}")


if __name__ == "__main__":
    sys.exit(main())

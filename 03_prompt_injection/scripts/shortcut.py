"""
가설 검증: S-Labs는 '의문문=정상 / 명령문=공격'이라는 지름길(shortcut)을 학습시킨다.
그래서 명령문 형태의 정상 프롬프트가 많은 외부 데이터에서 FPR이 폭발한다.

검증 방법:
 1) S-Labs train에서 라벨별 의문문 비율 / 길이를 본다 (지름길이 실제로 존재하나)
 2) 의문문 여부 + 길이, 단 두 피처만으로 S-Labs test를 얼마나 맞히나 (지름길 강도)
 3) 외부 데이터의 오탐이 의문문 여부에 따라 갈리나 (지름길이 원인인가)
작성일: 2026-11-05
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.tree import DecisionTreeClassifier

CACHE = "ext_cache"
tr = pd.read_csv("train.csv"); te = pd.read_csv("test.csv")


def feats(s):
    s = s.astype(str)
    return pd.DataFrame({
        "q": s.str.contains(r"\?").astype(int),
        "wh": s.str.match(r"(?i)\s*(what|how|why|when|where|who|which|can|could|do|does|is|are)\b").astype(int),
        "wc": s.str.split().str.len(),
    })


print("=== 1. S-Labs train: 라벨별 표면 형태 ===")
f = feats(tr.text); f["label"] = tr.label
print(f.groupby("label")[["q", "wh", "wc"]].mean().round(3))
print("\n   test:")
ft = feats(te.text); ft["label"] = te.label
print(ft.groupby("label")[["q", "wh", "wc"]].mean().round(3))

print("\n=== 2. 지름길 피처 3개(물음표/의문사/길이)만으로 분류 ===")
dt = DecisionTreeClassifier(max_depth=4, random_state=0).fit(feats(tr.text), tr.label)
p = dt.predict(feats(te.text))
print(f"   S-Labs test acc = {(p == te.label).mean():.4f}   (어휘 전혀 안 씀)")

print("\n=== 3. 외부 데이터: 오탐이 의문문 여부로 갈리나 ===")
model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
                      LogisticRegression(max_iter=2000, C=10)).fit(tr.text.astype(str), tr.label)

SPECS = [("deepset__prompt-injections", "text", "label", None),
         ("xTRam1__safe-guard-prompt-injection", "text", "label", None),
         ("jackhhao__jailbreak-classification", "prompt", "type", "jailbreak")]
for fn, tcol, lcol, pos in SPECS:
    p_ = f"{CACHE}/{fn}.parquet"
    if not os.path.exists(p_):
        continue
    d = pd.read_parquet(p_)
    y = (d[lcol].astype(str).str.lower() == pos).astype(int) if pos else d[lcol].astype(int)
    X = d[tcol].astype(str)
    pred = model.predict(X)
    isq = X.str.contains(r"\?")
    print(f"\n  {fn}")
    for lab, nm in [(0, "정상"), (1, "공격")]:
        for q, qn in [(True, "의문문"), (False, "평서/명령문")]:
            m = (y == lab) & (isq == q)
            if m.sum():
                err = (pred[m] != y[m]).mean()
                print(f"    {nm} / {qn:11s} n={m.sum():5d}  오류율={err:.3f}")

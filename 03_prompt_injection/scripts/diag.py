"""
S-Labs/prompt-injection-dataset 진단 스크립트.

목적: 과제 설계 전에 이 데이터셋이 "어려운 문제"인지 "이미 포화된 문제"인지 먼저 판정한다.
입력: 같은 폴더의 train.csv / validation.csv / test.csv (text, label)
출력: 콘솔에 라벨분포 / 길이통계 / 중복·누수 / TF-IDF 베이스라인 성능 / 상위 판별 토큰
작성일: 2026-11-05
"""
import pandas as pd, numpy as np, re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report

sp = {s: pd.read_csv(f"{s}.csv") for s in ["train", "validation", "test"]}

print("=== 1. 라벨 분포 / 크기 ===")
for s, d in sp.items():
    vc = d.label.value_counts().sort_index()
    print(f"{s:11s} n={len(d):6d}  label0={vc.get(0,0):5d}  label1={vc.get(1,0):5d}  pos율={d.label.mean():.3f}")

print("\n=== 2. 텍스트 길이 (문자/단어) ===")
for s, d in sp.items():
    ch = d.text.astype(str).str.len()
    wd = d.text.astype(str).str.split().str.len()
    print(f"{s:11s} 문자 median={ch.median():.0f} p95={ch.quantile(.95):.0f} max={ch.max()}  "
          f"단어 median={wd.median():.0f} p95={wd.quantile(.95):.0f}")
# 라벨별 길이차 = 지름길(shortcut) 가능성
tr = sp["train"]
print("  라벨별 평균 단어수: ",
      {int(l): round(tr[tr.label == l].text.astype(str).str.split().str.len().mean(), 1) for l in [0, 1]})

print("\n=== 3. 중복 / 분할 간 누수 ===")
def norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())
for s, d in sp.items():
    n = d.text.map(norm)
    print(f"{s:11s} 내부 정확중복 {len(d)-n.nunique():5d}건 ({(len(d)-n.nunique())/len(d):.1%})")
trn = set(sp["train"].text.map(norm))
for s in ["validation", "test"]:
    n = sp[s].text.map(norm)
    ov = n.isin(trn).sum()
    print(f"train<->{s:11s} 정확중복 누수 {ov:5d}건 ({ov/len(n):.1%})")

print("\n=== 4. TF-IDF + LogisticRegression 베이스라인 ===")
vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1)
Xtr = vec.fit_transform(sp["train"].text.astype(str))
clf = LogisticRegression(max_iter=2000, C=10).fit(Xtr, sp["train"].label)
for s in ["validation", "test"]:
    X = vec.transform(sp[s].text.astype(str)); y = sp[s].label
    p = clf.predict(X)
    print(f"{s:11s} acc={accuracy_score(y,p):.4f}  f1={f1_score(y,p):.4f}")
print(classification_report(sp["test"].label, clf.predict(vec.transform(sp["test"].text.astype(str))), digits=4))

print("\n=== 5. 문자 n-gram 베이스라인 (난독화 대응력 확인용) ===")
vec2 = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
X2 = vec2.fit_transform(sp["train"].text.astype(str))
clf2 = LogisticRegression(max_iter=2000, C=10).fit(X2, sp["train"].label)
yt = sp["test"].label; pt = clf2.predict(vec2.transform(sp["test"].text.astype(str)))
print(f"test acc={accuracy_score(yt,pt):.4f} f1={f1_score(yt,pt):.4f}")

print("\n=== 6. 상위 판별 토큰 (키워드 암기 여부) ===")
names = np.array(vec.get_feature_names_out()); w = clf.coef_[0]
print("  악성(1) 쪽:", ", ".join(names[np.argsort(w)[-25:]][::-1]))
print("  정상(0) 쪽:", ", ".join(names[np.argsort(w)[:25]]))

print("\n=== 7. 단일 키워드 규칙만으로 얼마나 잡히나 ===")
kw = ["ignore", "instruction", "prompt", "system", "reveal", "disregard", "override", "pretend", "jailbreak", "dan"]
pat = re.compile("|".join(kw), re.I)
hit = sp["test"].text.astype(str).str.contains(pat)
print(f"  키워드 규칙 test acc={accuracy_score(yt, hit.astype(int)):.4f} f1={f1_score(yt, hit.astype(int)):.4f}")

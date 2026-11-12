"""
diag.py 후속: TF-IDF 베이스라인의 오분류를 직접 들여다보고
"주제(topic) vs 의도(intent) 혼동" 가설을 검증한다.

목적: 차별점 설계의 근거가 될 실패 패턴을 확보.
입력: train/validation/test.csv
출력: FP/FN 샘플, 보안 주제어 포함 여부별 오류율, train/test 분포 차이
작성일: 2026-11-05
"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

sp = {s: pd.read_csv(f"{s}.csv") for s in ["train", "validation", "test"]}
vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
Xtr = vec.fit_transform(sp["train"].text.astype(str))
clf = LogisticRegression(max_iter=2000, C=10).fit(Xtr, sp["train"].label)

te = sp["test"].copy()
te["pred"] = clf.predict(vec.transform(te.text.astype(str)))
te["prob"] = clf.predict_proba(vec.transform(te.text.astype(str)))[:, 1]

fn = te[(te.label == 1) & (te.pred == 0)]   # 놓친 공격
fp = te[(te.label == 0) & (te.pred == 1)]   # 정상인데 공격으로 오인
print(f"FN(놓친 공격) {len(fn)}건 / FP(오탐) {len(fp)}건\n")

print("--- FN 샘플 25 (확신 낮은 순으로 정렬 안 함, 무작위) ---")
for t in fn.text.sample(min(25, len(fn)), random_state=0):
    print("  ", t[:140])
print("\n--- FP 샘플 25 ---")
for t in fp.text.sample(min(25, len(fp)), random_state=0):
    print("  ", t[:140])

# 가설 A: 보안 주제어를 포함한 '정상' 질문이 FP를 유발하는가
sec = re.compile(r"prompt|inject|jailbreak|system|guardrail|safety|security|instruction|align|red.?team|llm|ai\b", re.I)
te["sec"] = te.text.astype(str).str.contains(sec)
print("\n=== 가설A: 보안 주제어 포함 여부별 오류율 ===")
for lab in [0, 1]:
    sub = te[te.label == lab]
    for s in [True, False]:
        q = sub[sub.sec == s]
        if len(q):
            err = (q.label != q.pred).mean()
            print(f"  label={lab} 보안주제어={str(s):5s} n={len(q):5d} 오류율={err:.3f}")

# 가설 B: 난독화(leetspeak/특수문자) 샘플
obf = re.compile(r"[0-9@$!]{1,}[a-z]|[a-z][0-9@$!]{1,}[a-z]|\b[a-z]\s[a-z]\s[a-z]\b", re.I)
te["obf"] = te.text.astype(str).str.contains(obf)
print("\n=== 가설B: 난독화 의심 샘플 오류율 ===")
for s in [True, False]:
    q = te[te.obf == s]
    print(f"  난독화={str(s):5s} n={len(q):5d} 오류율={(q.label!=q.pred).mean():.3f}")

# 가설 C: train/test 길이 분포 차이가 성능차(val .971 vs test .951)를 만드는가
print("\n=== 가설C: 길이 구간별 test 오류율 ===")
te["wc"] = te.text.astype(str).str.split().str.len()
for lo, hi in [(0, 5), (6, 8), (9, 12), (13, 20), (21, 999)]:
    q = te[(te.wc >= lo) & (te.wc <= hi)]
    if len(q):
        print(f"  단어수 {lo:>2}-{hi:<3} n={len(q):5d} 오류율={(q.label!=q.pred).mean():.3f}")

# train 쪽 긴 샘플이 다른 생성기인지 눈으로 확인
print("\n--- train 긴 샘플(>30단어) 8개 ---")
tr = sp["train"]; lng = tr[tr.text.astype(str).str.split().str.len() > 30]
print(f"  (총 {len(lng)}건)")
for _, r in lng.sample(min(8, len(lng)), random_state=0).iterrows():
    print(f"   [{r.label}] {str(r.text)[:200]}")

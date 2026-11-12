"""
S-Labs로 학습한 모델이 '바깥 세상' 프롬프트 인젝션에서도 통하는지 측정한다.

가설: S-Labs test 0.95는 in-distribution 점수일 뿐이고,
      다른 출처 데이터에서는 크게 떨어진다 (= 일반화 실패).
입력: 로컬 train.csv (S-Labs) + HF에서 받는 외부 데이터셋 4종
출력: 데이터셋별 accuracy / FNR / FPR
작성일: 2026-11-05
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd, numpy as np, requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

CACHE = "ext_cache"
os.makedirs(CACHE, exist_ok=True)


def load_hf(name):
    """datasets-server의 parquet 변환본 URL을 받아 전 split을 하나로 합쳐 돌려준다."""
    safe = name.replace("/", "__")
    p = f"{CACHE}/{safe}.parquet"
    if not os.path.exists(p):
        meta = requests.get("https://datasets-server.huggingface.co/parquet",
                            params={"dataset": name}, timeout=60).json()
        files = meta["parquet_files"]
        dfs = [pd.read_parquet(io.BytesIO(requests.get(f["url"], timeout=120).content))
               for f in files]
        pd.concat(dfs, ignore_index=True).to_parquet(p)
    return pd.read_parquet(p)


# (이름, 텍스트컬럼, 라벨만드는 함수)
SPECS = [
    ("deepset/prompt-injections", "text", lambda d: d["label"].astype(int)),
    ("xTRam1/safe-guard-prompt-injection", "text", lambda d: d["label"].astype(int)),
    ("jackhhao/jailbreak-classification", "prompt",
     lambda d: (d["type"].astype(str).str.lower() == "jailbreak").astype(int)),
    ("Lakera/gandalf_ignore_instructions", "text", lambda d: pd.Series(1, index=d.index)),
]

# --- S-Labs 학습 ---
tr = pd.read_csv("train.csv")
model = make_pipeline(
    TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True),
    LogisticRegression(max_iter=2000, C=10),
).fit(tr.text.astype(str), tr.label)

rows = []
# 기준점: S-Labs 자기 test
te = pd.read_csv("test.csv")
sets = [("S-Labs test (in-dist)", te.text.astype(str), te.label.astype(int))]

for name, tcol, labfn in SPECS:
    try:
        d = load_hf(name)
        y = labfn(d)
        sets.append((name, d[tcol].astype(str), y))
        print(f"[로드] {name}: n={len(d)}, 양성비율={y.mean():.3f}")
        print(f"       예시(1): {d[tcol].astype(str)[y == 1].iloc[0][:110]!r}")
        if (y == 0).any():
            print(f"       예시(0): {d[tcol].astype(str)[y == 0].iloc[0][:110]!r}")
    except Exception as e:
        print(f"[실패] {name}: {e}")

print("\n=== S-Labs 학습 모델의 데이터셋별 성능 ===")
print(f"{'데이터셋':42s} {'n':>6s} {'acc':>7s} {'FNR':>7s} {'FPR':>7s}")
for name, X, y in sets:
    p = model.predict(X)
    acc = (p == y).mean()
    fnr = ((y == 1) & (p == 0)).sum() / max((y == 1).sum(), 1)
    fpr = ((y == 0) & (p == 1)).sum() / max((y == 0).sum(), 1)
    nz = f"{fpr:.3f}" if (y == 0).any() else "  -  "
    print(f"{name:42s} {len(y):6d} {acc:7.3f} {fnr:7.3f} {nz:>7s}")

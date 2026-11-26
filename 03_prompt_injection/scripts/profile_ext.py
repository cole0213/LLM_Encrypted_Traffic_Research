"""외부 데이터셋의 언어/길이 프로파일 확인. deepset FNR 0.55의 원인이 '다국어'인지 '표현 양식'인지 가른다. 2026-11-05"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd

DE = r"\b(der|die|das|und|ich|nicht|sie|ist|wie|was|fur|mir|du|eine|mit)\b"

d = pd.read_parquet("ext_cache/deepset__prompt-injections.parquet")
t = d.text.astype(str)
print("deepset n=", len(d))
print("  독일어 단어 포함 비율 전체:", round(t.str.contains(DE, case=False).mean(), 3))
print("  라벨별:", {int(k): round(v, 3) for k, v in
                 t.str.contains(DE, case=False).groupby(d.label).mean().items()})
print("  비ASCII 포함 비율:", round(t.str.contains(r"[^\x00-\x7F]").mean(), 3))
print("  길이 중앙값(단어):", int(t.str.split().str.len().median()))

j = pd.read_parquet("ext_cache/jackhhao__jailbreak-classification.parquet")
print("\njackhhao 길이 중앙값(단어):",
      {k: int(v) for k, v in j.prompt.astype(str).str.split().str.len().groupby(j.type).median().items()})

x = pd.read_parquet("ext_cache/xTRam1__safe-guard-prompt-injection.parquet")
print("xTRam1 길이 중앙값(단어):",
      {int(k): int(v) for k, v in x.text.astype(str).str.split().str.len().groupby(x.label).median().items()})
print("\nS-Labs test 길이 중앙값(단어): 6")

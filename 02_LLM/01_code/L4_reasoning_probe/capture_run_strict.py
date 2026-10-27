"""
capture_run_strict.py — 길이 완전통제판 캡처 요청 생성기(Gemini).

목적: 모든 조건서 출력을 '한 글자(A/B/C/D)'로 강제해 출력 길이를 완전히 고정한다.
      그래야 짧추/긴추 차이가 '답 길이'가 아니라 '추론 깊이'에서만 오는 것으로 격리됨.
      no_think / think_low / think_high 3조건 x 객관식 문항 x 반복.

2026-10-02 개정 — 1차 캡처(2026-09-23) 분석에서 드러난 결함 3건을 반영:
  (1) 요청 크기 누출: no_think 만 thinking_config 를 안 보내 요청이 약 67바이트 짧았다.
      그 차이가 up_bytes 로 새서 분류기가 '추론'이 아니라 '설정 필드 유무'를 읽을 수 있었다
      (실측 up_bytes 중앙값 no 808 / low 875 / high 876, 3클래스 정확도 0.722 -> 0.602).
      → 조건별로 프롬프트 끝에 공백을 덧붙여 요청 바이트를 맞춘다(PAD_CHARS).
  (2) 조건 순서 고정: 질문마다 항상 no -> low -> high 순으로 돌아 시간 추세(워밍업·부하 변동)가
      조건과 엉켰다. → 전체 시행을 섞어서(shuffle) 돌리고 실행 순서를 로그에 남긴다.
  (3) 토큰 한계: 추론이 폭주해 한계까지 가면 답이 안 나온다(Groq 1차서 4콜 발생).
      → max_output_tokens 를 명시하고, 답이 비면 truncated 플래그로 표시해 분석서 제외한다.
  그리고 반복 기본값을 3 -> 5 로 올려 표본을 108 -> 180 으로 늘린다.

사용: capture.sh 가 tcpdump와 함께 호출(직접도 가능).
  python3 capture_run_strict.py --repeats 5 --log out/capture_log_strict.jsonl
입력: GEMINI_API_KEY. 출력: out/capture_log_strict.jsonl (요청별 시각·조건·앱지표)
비고: 파싱은 parse_pcap.py --out out/gem_strict.csv, 분류는 e1_from_csv.py out/gem_strict.csv.
작성일: 2026-09-23 (개정 2026-10-02)
"""
import os
import json
import time
import random
import argparse
from pathlib import Path

from google import genai
from google.genai import types

MODEL = "gemini-3.5-flash-lite"

# 객관식 문항: 정답은 한 글자(A/B/C/D). 난도 다양(추론 유발)하되 출력은 항상 1토큰.
# (짧추/긴추 차이가 답 길이가 아니라 추론 깊이에서만 오도록 출력 완전 고정)
QUESTIONS = [
    "17 x 23 = ? A) 291 B) 391 C) 401 D) 411",
    "1~100 정수 중 3의 배수도 5의 배수도 아닌 수의 개수는? A) 47 B) 53 C) 60 D) 73",
    "수열 2,6,12,20,30 의 다음 항은? A) 40 B) 42 C) 44 D) 46",
    "A>B>C>D 이고 D>A 이면? A) 모순 없음 B) 모순 있음 C) 알 수 없음 D) A=D",
    "체스 나이트가 a1에서 h8까지 가는 최소 이동 수는? A) 4 B) 5 C) 6 D) 7",
    "물이 100도에서 끓는 주된 이유는? A) 중력 B) 증기압=대기압 C) 밀도 D) 표면장력",
    "정십이면체의 면 개수는? A) 8 B) 10 C) 12 D) 20",
    "3 5 8 13 21 다음 피보나치 항은? A) 29 B) 31 C) 34 D) 42",
    "한 변 7인 정사각형 넓이는? A) 14 B) 28 C) 49 D) 56",
    "논리: 모든 A는 B, 어떤 B는 C. 참인가 '어떤 A는 C'? A) 항상참 B) 항상거짓 C) 알수없음 D) 무의미",
    "2진수 1011 의 10진수 값은? A) 9 B) 11 C) 13 D) 15",
    "소수(prime)가 아닌 것은? A) 2 B) 3 C) 9 D) 11",
    "13 x 17 = ? A) 201 B) 211 C) 221 D) 231",
    "2의 10제곱은? A) 512 B) 1024 C) 2048 D) 4096",
    "1부터 20까지 자연수의 합은? A) 190 B) 200 C) 210 D) 220",
    "수열 1,4,9,16,25 의 다음 항은? A) 30 B) 32 C) 36 D) 49",
    "수열 3,7,15,31 의 다음 항은? A) 47 B) 55 C) 63 D) 71",
    "동전 3개를 던져 앞면이 정확히 2개 나오는 경우의 수는? A) 2 B) 3 C) 4 D) 6",
    "주사위 2개의 합이 7이 되는 경우의 수는? A) 4 B) 5 C) 6 D) 7",
    "5명 중 2명을 뽑는 경우의 수는? A) 10 B) 15 C) 20 D) 25",
    "모든 고래는 포유류, 어떤 포유류는 육식. '어떤 고래는 육식'은? A) 항상참 B) 항상거짓 C) 알수없음 D) 무의미",
    "P이면 Q 가 참일 때 Q 가 거짓이면 P 는? A) 참 B) 거짓 C) 알수없음 D) 무관",
    "8진수 17 의 10진수 값은? A) 13 B) 15 C) 17 D) 19",
    "16진수 FF 의 10진수 값은? A) 255 B) 256 C) 15 D) 16",
    "반지름 3인 원의 넓이는? (파이=3.14) A) 18.84 B) 28.26 C) 9.42 D) 37.68",
    "한 변이 4인 정육면체의 부피는? A) 16 B) 48 C) 64 D) 96",
    "물이 어는 온도를 화씨로 하면? A) 0 B) 32 C) 100 D) 212",
    "빛의 속도에 가장 가까운 것은? A) 3만 km/s B) 30만 km/s C) 300만 km/s D) 3천만 km/s",
    "DNA 염기가 아닌 것은? A) 아데닌 B) 구아닌 C) 라이신 D) 시토신",
    "1킬로그램은 몇 그램인가? A) 10 B) 100 C) 1000 D) 10000",
]
# 2026-10-05 추가 — 위 12문항은 1·2차와 비교 가능하도록 순서까지 그대로 두고 18문항을 덧붙였다.
#   늘린 이유: 반복(3->5)을 올려도 질문은 12개뿐이라 '처음 보는 질문에서 되는가'는 좋아지지 않는다.
#   질문별 교차검증에서 독립 표본은 사실상 질문 수이므로, 일반화를 보려면 문항을 늘려야 한다.
#   q4(체스 나이트)처럼 경로 탐색을 요구해 추론이 토큰 한계까지 폭주하는 유형은 새로 넣지 않았다.
INSTR = "\n\n정답 한 글자(A, B, C, D 중 하나)만 출력하라. 설명·다른 말·문장부호 금지."

# --- 응답 길이 arm (2026-10-27 추가) -------------------------------------------
# 지금까지의 결과는 전부 '답 1글자' 조건이라, 탐지 성능이 아니라 상한(best case)이다.
# 실제 LLM 응답은 수백 토큰이고 그때 추론 신호가 응답 스트림에 묻히는지는 측정한 적이 없다.
# → 답 뒤에 '정해진 문자열'을 붙여 응답을 길게 만들되, 길이는 콜마다 완전히 동일하게 둔다.
#   길이가 콜마다 달라지면 지금까지 쌓은 출력 길이 통제가 무너져 "추론이냐 길이냐"로 되돌아간다.
# 단일 문자 반복(AAAA...)은 토크나이저가 뭉쳐 토큰 수가 비선형이 되므로 10자 블록을 쓴다.
FILLER_BLOCK = "ABCDEFGHIJ"


# 자유 응답 arm. 길이를 고정하지 않고 '실제로 몇 토큰이 나오는지' 재는 쪽이다.
#   고정 arm 과 역할이 다르다:
#     고정 arm  = arm 안에서 길이가 상수 → low vs high 비교에서 길이 교란이 없다(인과 분리).
#     자유 arm  = 길이를 통제하지 않음  → 실제 배포 조건의 관측 성능. 단 추론과 길이가 섞인다.
#   둘을 섞어 한 덩어리로 평가하면 안 되고, 보고할 때도 성격을 구분해 적어야 한다.
FREE_ARMS = {
    "free_brief": "\n\n정답을 고르고, 이유를 두세 문장으로 간단히 설명하라.",
    "free_full":  "\n\n정답을 고르고, 풀이 과정을 단계별로 자세히 설명하라.",
}


def build_arm(arm):
    """arm → (지시문, 기대 답변 글자수 또는 None, max_output_tokens).

    arm 은 정수(덧붙일 글자 수) 또는 FREE_ARMS 의 키.
      0            = 기존 1글자 프로토콜(3차와 비교 가능한 기준선)
      양의 정수     = 답 뒤에 고정 문자열을 붙여 길이를 정확히 고정
      free_*       = 길이 통제 없음. 기대 글자수는 None(준수 판정 대상 아님)
    max_output_tokens 는 추론 여유에 답변 몫을 더해 잡는다. 답변이 길어지면 기존 2048 로는
    추론이 멀쩡해도 답이 잘려 '토큰 한계' 결함이 되살아난다.
    """
    if isinstance(arm, str) and arm in FREE_ARMS:
        return FREE_ARMS[arm], None, MAX_OUTPUT_TOKENS + 1024
    n_chars = int(arm)
    if n_chars <= 0:
        return INSTR, 1, MAX_OUTPUT_TOKENS
    k = n_chars // len(FILLER_BLOCK)
    instr = ("\n\n먼저 정답 한 글자(A, B, C, D 중 하나)를 출력하고, 이어서 "
             f"'{FILLER_BLOCK}' 를 정확히 {k}번 반복해 출력하라. "
             "줄바꿈·공백·설명·다른 말 금지.")
    return instr, 1 + k * len(FILLER_BLOCK), MAX_OUTPUT_TOKENS + n_chars // 2


def parse_arms(spec):
    """--arms 문자열 → arm 목록. 정수와 free_* 키를 섞어 쓸 수 있다."""
    out = []
    for a in spec.split(","):
        a = a.strip()
        if not a:
            continue
        out.append(a if a in FREE_ARMS else int(a))
    return out

CONDITIONS = [
    ("no_think",   None),
    ("think_low",  {"thinking_level": "low"}),
    ("think_high", {"thinking_level": "high"}),
]

# 요청 바이트를 조건 간에 맞추기 위한 패딩(프롬프트 끝 공백 수).
#   no_think 는 thinking_config 자체가 빠져 약 67바이트 짧고,
#   think_low 는 "low"(3) vs "high"(4) 로 1바이트 짧다.
# 공백은 모델 응답에 영향이 거의 없으면서 전송 바이트에는 그대로 더해진다.
# 재보정법: 캡처 후 parse_pcap 산출 CSV 에서 조건별 up_bytes 중앙값이 같은지 확인하고 차이만큼 조정.
#
# 보정 이력:
#   1차(2026-09-23, 패딩 없음)      up_bytes 중앙값  no 808 / low 875 / high 876
#   2차(2026-10-02, no 67·low 1)    up_bytes 중앙값  no 922 / low 901 / high 901
#     → low vs high 는 정확히 일치(901=901). no 는 21바이트 초과.
#       max_output_tokens 를 모든 조건에 넣으면서 no_think 에 설정 객체가 새로 생겨
#       예상보다 바이트가 더 늘었기 때문. 그래서 67 -> 46 으로 내린다.
PAD_CHARS = {"no_think": 46, "think_low": 1, "think_high": 0}

# 추론 폭주로 한계까지 가면 답이 안 나온다. 한계를 명시하고 그런 콜은 플래그로 걸러낸다.
MAX_OUTPUT_TOKENS = 2048


def run_one(client, question, think, pad, instr=INSTR, max_tok=None):
    """스트리밍 요청. 벽시계 시각(pcap 정렬용) + 앱지표 반환."""
    kw = {"max_output_tokens": max_tok or MAX_OUTPUT_TOKENS}
    if think:
        kw["thinking_config"] = types.ThinkingConfig(**think)
    cfg = types.GenerateContentConfig(**kw)
    contents = question + instr + (" " * pad)      # 조건별 요청 바이트 맞추기
    t_start = time.time()
    t_first_answer = None
    answer_chars = 0
    thoughts_tok = answer_tok = None
    # 3차 분석에서 Gemini down_bytes 가 추론토큰당 약 3.9바이트로 선형 증가하는 것이 확인됐다.
    # usage 숫자 자릿수로는 설명이 안 되는 크기라, thought(추론 요약) 텍스트가 실제로
    # 스트리밍돼 내려오는지 의심된다. 답 글자수에서 빼는 것과 별개로 그 양을 기록해 둔다.
    thought_chars = 0
    had_thought = False
    # 추론 중 빈 keep-alive 청크가 바이트를 밀어올렸을 가능성을 배제하기 위한 대조.
    chunk_count = 0
    stream = client.models.generate_content_stream(
        model=MODEL, contents=contents, config=cfg)
    for chunk in stream:
        t = time.time()
        chunk_count += 1
        cand = (getattr(chunk, "candidates", None) or [None])[0]
        content = getattr(cand, "content", None) if cand else None
        for part in (getattr(content, "parts", None) or []):
            txt = getattr(part, "text", None)
            if not txt:
                continue
            if getattr(part, "thought", False):
                had_thought = True
                thought_chars += len(txt)
                continue
            if t_first_answer is None:
                t_first_answer = t
            answer_chars += len(txt)
        um = getattr(chunk, "usage_metadata", None)
        if um is not None:
            thoughts_tok = getattr(um, "thoughts_token_count", None) or thoughts_tok
            answer_tok = getattr(um, "candidates_token_count", None) or answer_tok
    t_end = time.time()
    return {
        "t_start": t_start, "t_first_answer": t_first_answer, "t_end": t_end,
        "app_ttft_ms": round((t_first_answer - t_start) * 1000, 1) if t_first_answer else None,
        "app_total_ms": round((t_end - t_start) * 1000, 1),
        "answer_chars": answer_chars,
        "thoughts_tokens": thoughts_tok, "output_tokens": answer_tok,
        "thought_chars": thought_chars, "had_thought": had_thought,
        "chunk_count": chunk_count,
        "pad_chars": pad,
        # 답이 한 글자도 안 나왔으면 추론이 한계까지 간 것으로 본다(분석서 제외 대상).
        "truncated": answer_chars == 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=4.0)
    ap.add_argument("--log", default="out/capture_log_strict.jsonl")
    ap.add_argument("--seed", type=int, default=20261002,
                    help="시행 순서 섞기용 시드(재현 가능하게 고정)")
    ap.add_argument("--no-shuffle", action="store_true",
                    help="섞지 않고 예전처럼 순서대로(비교용)")
    ap.add_argument("--arms", default="0",
                    help="응답 길이 arm. 정수=답 뒤에 덧붙일 글자 수(길이 고정), "
                         "free_brief/free_full=길이 통제 없는 자유 응답. "
                         "예) --arms 0,400,1600,free_brief,free_full")
    args = ap.parse_args()
    arms = parse_arms(args.arms)

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY 없음")
    client = genai.Client(api_key=key)
    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS

    # 전체 시행을 만든 뒤 섞는다. 조건 순서가 고정이면 시간 추세가 조건과 엉킨다.
    trials = [(qi, cond, think, rep, arm)
              for qi, _ in enumerate(qs)
              for cond, think in CONDITIONS
              for rep in range(args.repeats)
              for arm in arms]
    if not args.no_shuffle:
        random.Random(args.seed).shuffle(trials)

    logp = Path(args.log)
    logp.parent.mkdir(parents=True, exist_ok=True)
    total = len(trials)
    time.sleep(1.0)
    with open(logp, "w", encoding="utf-8") as f:
        for i, (qi, cond, think, rep, arm) in enumerate(trials, 1):
            instr, expect, max_tok = build_arm(arm)
            try:
                m = run_one(client, qs[qi], think, PAD_CHARS.get(cond, 0),
                            instr=instr, max_tok=max_tok); m["error"] = None
            except Exception as e:
                m = {"error": f"{type(e).__name__}: {e}"}
            # order_idx = 실제 실행 순서. 나중에 시간 추세가 남았는지 확인할 때 쓴다.
            # complied = 지시한 글자 수를 정확히 지켰는가. arm 이 길수록 떨어질 수 있어,
            #   분석에서 쓸 수 있는 유효 표본이 얼마나 남는지 재는 데 쓴다.
            m.update({"idx": i, "order_idx": i, "q_idx": qi, "condition": cond, "rep": rep,
                      "arm": arm, "expect_chars": expect,
                      # 자유 arm 은 기대 길이가 없으므로 준수 판정 대상이 아니다(None).
                      "complied": None if expect is None else m.get("answer_chars") == expect,
                      "model": MODEL, "shuffled": not args.no_shuffle})
            f.write(json.dumps(m, ensure_ascii=False) + "\n"); f.flush()
            tag = m.get("error") or (
                f"ttft={m.get('app_ttft_ms')}ms out_tok={m.get('output_tokens')} "
                f"think={m.get('thoughts_tokens')} "
                f"chars={m.get('answer_chars')}" + ("" if expect is None else f"/{expect}")
                + ("" if m.get("complied") is not False else " [불일치]")
                + (" [잘림]" if m.get("truncated") else ""))
            print(f"[{i}/{total}] q{qi} {cond:10s} arm={str(arm):<10s} {tag}")
            time.sleep(args.sleep)
    print(f"\n[done] 로그 -> {logp}")
    print("→ 확인 1: answer_chars 가 조건 무관 1로 고정됐는지(길이 통제 성공 여부)")
    print("→ 확인 2: truncated=true 가 몇 건인지(추론 폭주로 답이 없던 콜 — 분석서 제외)")
    print("→ 확인 3: 파싱 후 조건별 up_bytes 중앙값이 같은지(요청 크기 통제 성공 여부)")


if __name__ == "__main__":
    main()

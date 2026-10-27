"""
mini_probe.py — L4 초미니 검증: reasoning ON/OFF가 응답 타이밍에 흔적을 남기나?

목적:
  같은 질문을 Claude에 (a) 추론 끄고(thinking disabled) (b) 추론 켜고(adaptive, effort별)
  던져, 스트리밍 이벤트의 시각을 기록한다. 핵심 측정 = "요청 → 첫 '답변' 토큰까지의 지연
  (ttft_answer)"이 출력 길이와 무관하게 ON일 때 커지는가. 커지면 L4(작업단계 추론)를
  트래픽/타이밍으로 식별할 수 있다는 첫 근거.
  ※ 이 스크립트는 '애플리케이션 레벨' 타이밍(값싼 프록시)만 잰다. 진짜 네트워크 패킷
    캡처(tcpdump)는 Phase 1에서 이 위에 얹는다.

입력: 없음(아래 QUESTIONS/CONDITIONS 상수). 인증은 Claude Code 프로필 자동 사용.
출력: out/probe_results.csv (조건×질문×반복별 타이밍·토큰 행).

주의: API 호출 = 토큰 소비(비용). REPEATS·질문 수 조절해서 소량부터.
작성일: 2026-09-01
"""

import csv
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

import anthropic

# ---- 실험 설정 ----
MODEL = "claude-opus-5"          # 추론 지원 모델. 필요시 claude-sonnet-5 등으로.
MAX_TOKENS = 16000               # 스트리밍이라 크게 잡아도 안전.

# 같은 질문을 ON/OFF 양쪽에 던진다(=출력 길이 통제의 출발점).
# 난이도 섞음: 추론이 필요한 것(논리/수학) + 단순한 것.
QUESTIONS = [
    "다음 논리 퍼즐을 풀어줘: A는 B보다 크고, B는 C보다 크며, C는 D보다 크다. 그리고 D는 A보다 크다면 모순이 있는가? 결론만 한 문장.",
    "17 x 23을 암산 과정 없이 답만.",
    "1부터 100까지 정수 중 3의 배수도 5의 배수도 아닌 수의 개수는? 답만.",
    "'배는 과일이자 탈것이자 신체부위다'라는 문장이 왜 중의적인지 한 문장으로.",
    "체스에서 나이트가 a1에서 h8까지 최소 몇 번 이동으로 갈 수 있나? 답만.",
    "물이 100도에서 끓는 이유를 한 문장으로.",
    "다음 수열의 다음 항: 2, 6, 12, 20, 30, ? 답만.",
    "'닭이 먼저냐 달걀이 먼저냐'에 진화론적으로 한 문장 답.",
]

# 조건: (라벨, thinking dict, effort). OFF = 추론 끔. ON_* = 추론 켜고 깊이 조절.
# 참고: opus-5는 thinking disabled가 effort high 이하에서만 허용.
CONDITIONS = [
    ("off",     {"type": "disabled"},                         "high"),
    ("on_low",  {"type": "adaptive", "display": "summarized"}, "low"),
    ("on_high", {"type": "adaptive", "display": "summarized"}, "high"),
    # 깊이(L4 확장) 더 보고 싶으면 주석 해제:
    # ("on_max",  {"type": "adaptive", "display": "summarized"}, "max"),
]


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_one(client, question, thinking, effort):
    """한 요청을 스트리밍하며 이벤트 시각을 기록한다.

    반환: dict(측정치). 핵심 = ttft_answer_ms(요청→첫 답변 텍스트 토큰).
    """
    t0 = time.perf_counter()
    t_first_event = None      # 아무 이벤트든 첫 도착
    t_first_think = None      # 첫 thinking 토큰
    t_first_text = None       # 첫 '답변' 텍스트 토큰  ← 핵심
    t_end = None
    n_think_delta = 0
    n_text_delta = 0
    out_tokens = None
    in_tokens = None
    stop_reason = None
    answer_chars = 0

    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking=thinking,
        output_config={"effort": effort},
        messages=[{"role": "user", "content": question}],
    )
    with client.messages.stream(**kwargs) as stream:
        for event in stream:
            t = time.perf_counter()
            if t_first_event is None:
                t_first_event = t
            if event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    if t_first_think is None:
                        t_first_think = t
                    n_think_delta += 1
                elif event.delta.type == "text_delta":
                    if t_first_text is None:
                        t_first_text = t
                    n_text_delta += 1
                    answer_chars += len(event.delta.text)
            elif event.type == "message_delta":
                if getattr(event, "usage", None) and event.usage.output_tokens is not None:
                    out_tokens = event.usage.output_tokens
        final = stream.get_final_message()
        t_end = time.perf_counter()
        stop_reason = final.stop_reason
        if final.usage:
            out_tokens = final.usage.output_tokens
            in_tokens = final.usage.input_tokens

    def ms(a, b):
        return round((b - a) * 1000, 1) if (a is not None and b is not None) else None

    return {
        "ttft_answer_ms": ms(t0, t_first_text),   # ★ 요청→첫 답변 토큰 (추론 지연 신호)
        "ttft_any_ms":    ms(t0, t_first_event),
        "ttft_think_ms":  ms(t0, t_first_think),
        "think_dur_ms":   ms(t_first_think, t_first_text),  # 생각 구간 길이(스트리밍형)
        "total_ms":       ms(t0, t_end),
        "n_think_delta":  n_think_delta,
        "n_text_delta":   n_text_delta,
        "answer_chars":   answer_chars,
        "output_tokens":  out_tokens,
        "input_tokens":   in_tokens,
        "stop_reason":    stop_reason,
    }


def main():
    ap = argparse.ArgumentParser(description="L4 reasoning ON/OFF timing probe")
    ap.add_argument("--repeats", type=int, default=3, help="조건·질문당 반복(노이즈 평균)")
    ap.add_argument("--limit", type=int, default=0, help="질문 수 제한(스모크테스트용, 0=전체)")
    ap.add_argument("--sleep", type=float, default=1.5, help="요청 간 간격(초)")
    ap.add_argument("--out", default="out/probe_results.csv")
    args = ap.parse_args()

    qs = QUESTIONS[: args.limit] if args.limit else QUESTIONS
    client = anthropic.Anthropic()   # Claude Code 인증 프로필 자동 사용
    rows = []
    total = len(qs) * len(CONDITIONS) * args.repeats
    i = 0
    for qi, q in enumerate(qs):
        for cond, thinking, effort in CONDITIONS:
            for rep in range(args.repeats):
                i += 1
                try:
                    m = run_one(client, q, thinking, effort)
                except Exception as e:
                    m = {"error": f"{type(e).__name__}: {e}"}
                m.update({"ts": now_iso(), "q_idx": qi, "condition": cond,
                          "effort": effort, "rep": rep,
                          "question": q[:50]})
                rows.append(m)
                if m.get("error"):
                    print(f"[{i}/{total}] q{qi} {cond:8s} ERROR: {m['error']}")
                else:
                    print(f"[{i}/{total}] q{qi} {cond:8s} "
                          f"ttft_answer={m.get('ttft_answer_ms')}ms "
                          f"total={m.get('total_ms')}ms out={m.get('output_tokens')}tok")
                time.sleep(args.sleep)

    # CSV 저장(원자적).
    cols = ["ts", "q_idx", "condition", "effort", "rep",
            "ttft_answer_ms", "ttft_any_ms", "ttft_think_ms", "think_dur_ms",
            "total_ms", "n_think_delta", "n_text_delta", "answer_chars",
            "output_tokens", "input_tokens", "stop_reason", "question", "error"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(out)
    print(f"\n[done] {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()

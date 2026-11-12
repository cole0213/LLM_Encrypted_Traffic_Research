"""recover_screen.py — 선별 로그(표 출력)에서 선별 결과 JSON 을 되살린다.

왜 필요한가:
  screen_qset.py 는 모든 문항을 돈 뒤에야 JSON 을 쓴다. 중간에 죽으면(무료 등급
  일당 할당량 소진, Ctrl+C, SSH 끊김) 몇 시간치 호출이 통째로 사라진다.
  2026-11-10 Gemini 선별이 q135 부근에서 할당량에 걸렸고, 앞 135문항은 멀쩡히
  측정됐는데 JSON 이 없어 못 쓸 뻔했다. 표 출력에는 행마다 값이 다 찍혀 있으므로
  거기서 되살린다.

입력: screen_qset.py 의 stdout 로그 (nohup 리다이렉트 파일)
출력: out/screen_<provider>_<model>_<qset>.json — screen_qset 이 쓰는 것과 같은 규격

주의:
  로그의 문항 텍스트는 40자로 잘려 있다. 되살린 JSON 의 "text" 도 잘린 채다.
  분석에 쓰는 건 q 번호·vals·spread 뿐이라 문제 없지만, 원문이 필요하면
  questions_all.QUESTIONS_V2_ALL[q] 로 당겨 써라.

작성일: 2026-11-10
"""
import re
import sys
import json
import argparse
from pathlib import Path

from questions_all import FAMILIES_V2_ALL

# "=== gemini / gemini-3.5-flash-lite / qset=v2 / no_think,low,high ===" 를 읽는다.
HEAD = re.compile(r"===\s*(\S+)\s*/\s*(\S+)\s*/\s*qset=(\S+)\s*/\s*(\S+)\s*===")


def parse(log_path, min_spread):
    """로그를 훑어 (헤더, 행 목록) 을 돌려준다."""
    prov = model = qset = None
    efforts = []
    rows = []
    seen = set()
    for line in Path(log_path).read_text(encoding="utf-8", errors="replace").splitlines():
        m = HEAD.search(line)
        if m:
            prov, model, qset, eff = m.groups()
            efforts = eff.split(",")
            continue
        if not efforts:
            continue
        # 데이터 행: 맨 앞이 공백+숫자, 그 뒤로 설정 수만큼 값, 격차/잘림/불응, 문항.
        # 값 칸은 폭 9, 번호 칸은 폭 4로 찍히지만 숫자가 길어지면 밀린다.
        # 그래서 자리수로 자르지 않고 토큰으로 쪼갠다.
        if not re.match(r"^\s*\d+\s", line):
            continue
        toks = line.split()
        need = 1 + len(efforts) + 3
        if len(toks) < need:
            continue
        try:
            qi = int(toks[0])
        except ValueError:
            continue
        vals = []
        ok = True
        for t in toks[1:1 + len(efforts)]:
            if t in ("—", "-"):
                vals.append(None)
            else:
                try:
                    vals.append(int(t))
                except ValueError:
                    ok = False
                    break
        if not ok:
            continue
        try:
            spread = int(toks[1 + len(efforts)])
            trunc = int(toks[2 + len(efforts)])
            nonc = int(toks[3 + len(efforts)])
        except ValueError:
            continue
        if qi in seen:          # 같은 로그에 두 번 돌린 흔적이 있으면 뒤쪽을 쓴다
            rows = [r for r in rows if r["q"] != qi]
        seen.add(qi)
        text = " ".join(toks[need:])
        rows.append({"q": qi, "spread": spread, "trunc": trunc, "nonc": nonc,
                     "vals": vals, "text": text})
    rows.sort(key=lambda r: r["q"])
    return prov, model, qset, efforts, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--min-spread", type=int, default=100)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    prov, model, qset, efforts, rows = parse(a.log, a.min_spread)
    if not rows:
        raise SystemExit("데이터 행을 하나도 못 찾았다 — 로그 형식을 확인하라")

    # 설정을 하나라도 못 잰 행은 격차를 믿을 수 없다. '격차 작음'과 구별해 뺀다.
    incomplete = [r["q"] for r in rows if any(v is None for v in r["vals"])]
    good = [r["q"] for r in rows
            if r["spread"] >= a.min_spread and r["trunc"] == 0 and r["nonc"] == 0
            and r["q"] not in incomplete]

    fams = FAMILIES_V2_ALL if qset == "v2" else None
    outp = Path(a.out) if a.out else (
        Path("out") / f"screen_{prov}_{re.sub(r'[^A-Za-z0-9._-]', '-', model)}_{qset}.json")
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(
        {"provider": prov, "model": model, "qset": qset, "efforts": efforts,
         "min_spread": a.min_spread, "families": fams, "good": good, "rows": rows,
         "incomplete": incomplete, "errors": [],
         "recovered_from": str(a.log)},
        ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{prov} / {model} / qset={qset} / {','.join(efforts)}")
    print(f"로그에서 되살린 행 {len(rows)}개 (q{rows[0]['q']}~q{rows[-1]['q']})")
    print(f"  못 잰 문항(설정 누락) {len(incomplete)}개")
    print(f"  쓸 문항(격차 {a.min_spread}+ · 잘림 0 · 불응 0) {len(good)}개")
    if fams:
        from collections import Counter
        per = Counter(fams[r["q"]] for r in rows)
        hit = Counter(fams[q] for q in good)
        print(f"  템플릿 {len(hit)}/{len(per)}개에서 통과 문항이 나왔다")
        for f, c in sorted(hit.items(), key=lambda z: -z[1]):
            print(f"    {f:18s} {c:3d}/{per[f]}")
        dead = sorted(f for f in per if f not in hit)
        if dead:
            print(f"    통과 0인 템플릿 {len(dead)}개: {', '.join(dead[:10])}")
    print(f"  -> {outp}")


if __name__ == "__main__":
    main()

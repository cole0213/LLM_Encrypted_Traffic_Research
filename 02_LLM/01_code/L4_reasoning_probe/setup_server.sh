#!/usr/bin/env bash
# setup_server.sh — 17서버(Linux)에서 L4 실험/문헌툴 실행 준비.
# 목적: 필요 python 패키지 설치 + Anthropic API 연결 확인.
# 사용: bash setup_server.sh
# 작성일: 2026-09-01
set -e

echo "=== python 확인 ==="
python3 --version || { echo "python3 없음"; exit 1; }

echo "=== 패키지 설치 ==="
# 실험용(google-genai, matplotlib, scapy=pcap파싱) + 문헌툴용(pyyaml, requests, pypdf)
python3 -m pip install --user --quiet google-genai matplotlib scapy pyyaml requests pypdf
python3 -c "import google.genai, matplotlib, scapy, yaml, requests, pypdf; print('  설치 OK (google-genai, scapy 포함)')"

echo "=== tcpdump 확인(Phase1 패킷캡처용) ==="
if command -v tcpdump >/dev/null; then echo "  tcpdump 있음: $(command -v tcpdump)"; else echo "  ✗ tcpdump 없음 → apt install -y tcpdump"; fi

echo "=== API 연결 확인 (키 없이 401이면 정상=닿음) ==="
code=$(curl -s -o /dev/null -w "%{http_code}" https://api.anthropic.com/v1/messages || echo "000")
if [ "$code" = "000" ]; then
  echo "  ✗ api.anthropic.com 안 닿음 — 서버 인터넷 막힘. Windows PC에서 실행 필요."
else
  echo "  ✓ 닿음 (HTTP $code). 401/400이면 정상(키만 넣으면 됨)."
fi

echo
echo "=== 다음 ==="
echo "1) 키 설정:  export ANTHROPIC_API_KEY=\"sk-ant-...\"   (영구는 ~/.bashrc에 추가)"
echo "2) 스모크:   python3 mini_probe.py --limit 2 --repeats 1"
echo "3) 그림:     python3 plot_probe.py"

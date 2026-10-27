"""
httpclient.py — 재시도·백오프 포함 공용 HTTP GET.

목적: 발견 어댑터가 공유하는 견고한 GET. 429/5xx 지수 백오프+jitter,
      Retry-After 준수, polite User-Agent, 타임아웃 분리(마스터 프롬프트 9.1).
      randomness는 실행 재현을 위해 run 단위 시드로 고정한다.
입력: url, params, headers.
출력: (status_code, json 또는 text). 실패 시 예외.
작성일: 2026-08-22
"""

import time
import random

import requests

# 모듈 단위 세션 재사용(호스트 커넥션 풀).
_session = requests.Session()
_rng = random.Random(20260822)  # 고정 시드 — jitter 재현성


class HttpError(Exception):
    """복구 불가 HTTP 실패."""

    def __init__(self, status, msg):
        super().__init__(f"HTTP {status}: {msg}")
        self.status = status


def get(url: str, params: dict | None = None, headers: dict | None = None,
        timeout: int = 45, retry_max: int = 4, backoff_base: float = 2.0,
        expect: str = "json"):
    """GET 요청을 재시도와 함께 수행한다.

    expect="json"이면 파싱된 객체를, "text"면 본문 문자열을 반환한다.
    429/5xx는 백오프 후 재시도, 4xx(429 제외)는 즉시 실패 처리한다.
    """
    last_err = None
    for attempt in range(retry_max):
        try:
            resp = _session.get(url, params=params, headers=headers,
                                timeout=timeout)
        except requests.RequestException as e:
            last_err = e
            _sleep_backoff(attempt, backoff_base)
            continue

        code = resp.status_code
        if code == 200:
            if expect == "json":
                return code, resp.json()
            return code, resp.text
        if code == 429 or 500 <= code < 600:
            # Retry-After 우선, 없으면 지수 백오프.
            ra = resp.headers.get("Retry-After")
            if ra and ra.isdigit():
                time.sleep(min(int(ra), 60))
            else:
                _sleep_backoff(attempt, backoff_base)
            last_err = HttpError(code, resp.reason)
            continue
        # 그 외 4xx = 영구 실패.
        raise HttpError(code, resp.reason)

    if isinstance(last_err, HttpError):
        raise last_err
    raise HttpError(0, f"exhausted retries: {last_err}")


def _sleep_backoff(attempt: int, base: float):
    """지수 백오프 + jitter로 대기한다."""
    delay = base * (2 ** attempt) + _rng.uniform(0, 1.0)
    time.sleep(min(delay, 30))

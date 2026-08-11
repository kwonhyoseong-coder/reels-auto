"""공통 HTTP 클라이언트. 짧은 타임아웃 + 자동 재시도."""
from __future__ import annotations
import time
import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}

# GitHub Actions(미국) → 한국 정부 사이트는 레이턴시가 커서 8초면 충분
DEFAULT_TIMEOUT = 8


def get(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = 2,
        headers: dict | None = None) -> requests.Response | None:
    last_err = None
    h = {**HEADERS, **(headers or {})}
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=h, timeout=timeout)
            if r.status_code < 500:
                return r
            last_err = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last_err = str(e)[:120]
        if attempt < retries:
            time.sleep(1.0 * (attempt + 1))
    print(f"  ⚠ GET 실패 {url}: {last_err}")
    return None

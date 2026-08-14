"""
공통 HTTP 클라이언트.
GitHub Actions(미국) → 한국 정부 사이트 접속이 차단되므로,
여러 무료 CORS/스크래핑 프록시를 차례로 시도한다.

2026-08 기준 신뢰 순서:
  1. cors.sh         (HTML 직접 반환, 안정적)
  2. r.jina.ai       (HTML 옵션, 간헐적 rate limit)
  3. allorigins.win  (간헐적 타임아웃)
  4. corsproxy.io    (가끔 차단)
"""
from __future__ import annotations
import time
from typing import Optional
import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_TIMEOUT = 12


def get(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = 2,
        want_xml: bool = False) -> Optional[requests.Response]:
    # 1) 직접
    r = _direct_get(url, timeout=timeout, retries=retries)
    if r is not None and _looks_ok(r, want_xml=want_xml):
        return r

    # 2) 프록시 체인
    proxies = [
        ("cors.sh", _cors_sh_get),
        ("jina", _jina_get),
        ("allorigins", _allorigins_get),
        ("corsproxy.io", _corsproxy_io_get),
    ]
    for name, fn in proxies:
        print(f"  → 프록시 {name} 시도: {url}", flush=True)
        try:
            r = fn(url, want_xml=want_xml, timeout=max(timeout, 20))
        except Exception as e:
            print(f"  ✗ {name} 예외: {type(e).__name__}: {str(e)[:100]}", flush=True)
            continue
        if r is not None and _looks_ok(r, want_xml=want_xml):
            print(f"  ✓ {name} 성공 ({r.status_code}, {len(r.content)} bytes)", flush=True)
            return r
        print(f"  ✗ {name} 실패 (응답 없음 또는 형식 불일치)", flush=True)
        time.sleep(0.3)

    print(f"  ⚠ 모든 프록시 실패: {url}", flush=True)
    return None


def _direct_get(url, *, timeout, retries) -> Optional[requests.Response]:
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code < 500:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = type(e).__name__ + ": " + str(e)[:100]
        if attempt < retries:
            time.sleep(1.0 * (attempt + 1))
    print(f"  ⚠ 직접 GET 실패 {url}: {last}", flush=True)
    return None


def _wrap(text: str, status: int = 200, ctype: str = "text/html; charset=utf-8") -> requests.Response:
    r = requests.Response()
    r.status_code = status
    r._content = text.encode("utf-8", errors="replace")
    r.encoding = "utf-8"
    r.headers["Content-Type"] = ctype
    return r


# ─────────── 프록시별 구현 ───────────

def _cors_sh_get(url, *, want_xml: bool, timeout: int):
    """proxy.cors.sh - 원본 HTML 그대로 반환. x-cors-api-key 없이도 동작."""
    proxy = f"https://proxy.cors.sh/{url}"
    r = requests.get(
        proxy,
        headers={
            **HEADERS,
            "x-cors-api-key": "free",  # public 무료 키 힌트 (없어도 됨)
            "Origin": "https://localhost",
        },
        timeout=timeout,
    )
    if r.status_code != 200:
        print(f"    cors.sh HTTP {r.status_code}: {r.text[:200]}", flush=True)
        return None
    return _wrap(r.text)


def _jina_get(url, *, want_xml: bool, timeout: int):
    """r.jina.ai - X-Return-Format: html로 HTML 원본 요청."""
    jina_url = "https://r.jina.ai/" + url
    # 1) HTML 모드
    r = requests.get(
        jina_url,
        headers={
            **HEADERS,
            "X-Return-Format": "html",
            "X-With-Links-Summary": "false",
            "X-No-Cache": "true",
        },
        timeout=timeout,
    )
    if r.status_code == 200 and "<html" in r.text[:3000].lower():
        r.encoding = r.apparent_encoding or "utf-8"
        return r
    print(f"    jina(html) {r.status_code}, head: {r.text[:150]!r}", flush=True)
    # 2) XML/text 모드
    if want_xml:
        r2 = requests.get(
            jina_url,
            headers={**HEADERS, "X-Return-Format": "text"},
            timeout=timeout,
        )
        if r2.status_code == 200 and ("<?xml" in r2.text[:500] or "<rss" in r2.text[:500]):
            r2.encoding = "utf-8"
            return r2
    return None


def _allorigins_get(url, *, want_xml: bool, timeout: int):
    """api.allorigins.win/raw - 원본 콘텐츠."""
    r = requests.get(
        "https://api.allorigins.win/raw",
        params={"url": url},
        headers=HEADERS,
        timeout=timeout,
    )
    if r.status_code != 200:
        print(f"    allorigins HTTP {r.status_code}: {r.text[:150]}", flush=True)
        return None
    return r


def _corsproxy_io_get(url, *, want_xml: bool, timeout: int):
    """corsproxy.io (이제는 localhost 전용이라 대부분 403)."""
    from urllib.parse import quote
    proxy = f"https://corsproxy.io/?url={quote(url, safe='')}"
    r = requests.get(proxy, headers=HEADERS, timeout=timeout)
    if r.status_code != 200:
        print(f"    corsproxy.io HTTP {r.status_code}: {r.text[:150]}", flush=True)
        return None
    return r


def _looks_ok(r: requests.Response, want_xml: bool) -> bool:
    if r.status_code >= 400:
        return False
    body = r.text[:5000].lower()
    if want_xml:
        return ("<?xml" in body) or ("<rss" in body) or ("<feed" in body)
    return "<html" in body or "<!doctype" in body

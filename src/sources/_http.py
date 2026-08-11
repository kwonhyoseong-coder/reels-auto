"""
공통 HTTP 클라이언트.

한국 정부 사이트는 해외 IP(예: GitHub Actions 미국 서버)를 차단하는 경우가 많다.
- 직접 요청을 먼저 시도
- 실패 시 r.jina.ai 프록시를 경유해서 같은 HTML을 받아옴
- RSS/XML도 직접 시도 후, 실패하면 프록시로 재시도
"""
from __future__ import annotations
import time
from typing import Optional
import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}

DEFAULT_TIMEOUT = 8
JINA_PREFIX = "https://r.jina.ai/"


def get(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = 1,
        want_xml: bool = False) -> Optional[requests.Response]:
    """
    URL을 GET. 실패/차단 시 jina 프록시로 재시도.
    want_xml=True면 XML(원본 바이트) 우선, False면 HTML로 파싱 가능하면 OK.
    """
    # 1) 직접 시도
    r = _direct_get(url, timeout=timeout, retries=retries)
    if r is not None and _looks_ok(r, want_xml=want_xml):
        return r

    print(f"  ⏎ 직접 요청 실패/차단 → jina 프록시로 우회: {url}")
    # 2) jina 프록시
    return _jina_get(url, timeout=max(timeout * 2, 20), want_xml=want_xml)


def _direct_get(url, *, timeout, retries) -> Optional[requests.Response]:
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code < 500:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = str(e)[:120]
        if attempt < retries:
            time.sleep(0.7 * (attempt + 1))
    print(f"  ⚠ 직접 GET 실패 {url}: {last}")
    return None


def _jina_get(url, *, timeout, want_xml: bool) -> Optional[requests.Response]:
    """
    r.jina.ai는 기본으로 마크다운을 반환하지만,
    X-Return-Format: html 로 보내면 원본 HTML을 그대로 준다.
    XML은 jina가 잘 처리 못하니 텍스트로 받은 뒤 원본인지 확인.
    """
    jina_url = JINA_PREFIX + url
    # HTML 원본
    try:
        r = requests.get(
            jina_url,
            headers={**HEADERS, "X-Return-Format": "html"},
            timeout=timeout,
        )
        if r.status_code == 200 and "<html" in r.text[:2000].lower():
            # requests.Response처럼 보이게 내용물만 그대로 반환
            r.encoding = r.apparent_encoding or "utf-8"
            return r
    except requests.RequestException as e:
        print(f"  ⚠ jina html 실패: {str(e)[:100]}")

    # XML 원본 (RSS)
    if want_xml:
        try:
            r2 = requests.get(
                jina_url,
                headers={**HEADERS, "X-Return-Format": "text"},
                timeout=timeout,
            )
            if r2.status_code == 200 and ("<rss" in r2.text[:500] or "<feed" in r2.text[:500] or "<?xml" in r2.text[:500]):
                r2.encoding = "utf-8"
                return r2
        except requests.RequestException:
            pass

    print(f"  ⚠ jina 프록시도 실패: {url}")
    return None


def _looks_ok(r: requests.Response, want_xml: bool) -> bool:
    if r.status_code >= 400:
        return False
    body = r.text[:2000].lower()
    if want_xml:
        return ("<?xml" in body) or ("<rss" in body) or ("<feed" in body)
    # HTML
    return "<html" in body or "<!doctype" in body

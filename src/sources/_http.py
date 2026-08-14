"""
공통 HTTP 클라이언트.
GitHub Actions(미국) → 한국 정부 사이트 접속이 차단되므로,
여러 무료 프록시를 순서대로 시도한다.
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
    """
    URL을 GET.
    1) 직접 시도 (한국 로컬/Arena에서 동작)
    2) jina 프록시
    3) allorigins 프록시
    4) corsproxy.io 프록시
    """
    # 1) 직접
    r = _direct_get(url, timeout=timeout, retries=retries)
    if r is not None and _looks_ok(r, want_xml=want_xml):
        return r

    # 2) 여러 프록시를 차례로
    for proxy_name, proxy_fn in [
        ("jina", _jina_get),
        ("allorigins", _allorigins_get),
        ("corsproxy", _corsproxy_get),
    ]:
        print(f"  → 프록시 {proxy_name} 시도: {url}", flush=True)
        r = proxy_fn(url, want_xml=want_xml, timeout=max(timeout, 20))
        if r is not None and _looks_ok(r, want_xml=want_xml):
            print(f"  ✓ {proxy_name} 성공", flush=True)
            return r
        else:
            print(f"  ✗ {proxy_name} 실패", flush=True)
        time.sleep(0.5)

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
            time.sleep(1.5 * (attempt + 1))
    print(f"  ⚠ 직접 GET 실패 {url}: {last}", flush=True)
    return None


def _wrap_response(text: str, status: int = 200) -> requests.Response:
    """프록시 응답을 requests.Response처럼 보이게 만든다."""
    r = requests.Response()
    r.status_code = status
    r._content = text.encode("utf-8", errors="replace")
    r.encoding = "utf-8"
    r.headers["Content-Type"] = "text/html; charset=utf-8"
    return r


def _jina_get(url, *, want_xml: bool, timeout: int) -> Optional[requests.Response]:
    jina_url = "https://r.jina.ai/" + url
    try:
        # HTML 원본 우선
        r = requests.get(
            jina_url,
            headers={
                **HEADERS,
                "X-Return-Format": "html",
                "X-With-Links-Summary": "false",
            },
            timeout=timeout,
        )
        if r.status_code == 200 and "<html" in r.text[:3000].lower():
            r.encoding = r.apparent_encoding or "utf-8"
            return r
        # XML 모드 재시도
        if want_xml:
            r2 = requests.get(
                jina_url,
                headers={**HEADERS, "X-Return-Format": "text"},
                timeout=timeout,
            )
            if r2.status_code == 200 and ("<?xml" in r2.text[:500] or "<rss" in r2.text[:500]):
                r2.encoding = "utf-8"
                return r2
    except requests.RequestException as e:
        print(f"    jina 오류: {type(e).__name__}: {str(e)[:120]}", flush=True)
    return None


def _allorigins_get(url, *, want_xml: bool, timeout: int) -> Optional[requests.Response]:
    """allorigins.win - 프록시를 통해 raw 콘텐츠 반환."""
    try:
        endpoint = "https://api.allorigins.win/raw"
        r = requests.get(
            endpoint,
            params={"url": url},
            headers=HEADERS,
            timeout=timeout,
        )
        if r.status_code == 200:
            body = r.text[:500].lower()
            if want_xml:
                if "<?xml" in body or "<rss" in body or "<feed" in body:
                    return r
            else:
                if "<html" in body or "<!doctype" in body:
                    return r
    except requests.RequestException as e:
        print(f"    allorigins 오류: {type(e).__name__}: {str(e)[:120]}", flush=True)
    return None


def _corsproxy_get(url, *, want_xml: bool, timeout: int) -> Optional[requests.Response]:
    """corsproxy.io - 또 다른 무료 프록시."""
    try:
        proxy_url = f"https://corsproxy.io/?url={requests.utils.quote(url, safe='')}"
        r = requests.get(proxy_url, headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            body = r.text[:500].lower()
            if want_xml and ("<?xml" in body or "<rss" in body):
                return r
            if not want_xml and "<html" in body:
                return r
    except requests.RequestException as e:
        print(f"    corsproxy 오류: {type(e).__name__}: {str(e)[:120]}", flush=True)
    return None


def _looks_ok(r: requests.Response, want_xml: bool) -> bool:
    if r.status_code >= 400:
        return False
    body = r.text[:3000].lower()
    if want_xml:
        return ("<?xml" in body) or ("<rss" in body) or ("<feed" in body)
    return "<html" in body or "<!doctype" in body

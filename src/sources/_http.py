"""
공통 HTTP 클라이언트.
한국 정부 사이트는 해외 IP를 차단하므로, Google Apps Script 프록시를 우선 사용한다.
- GitHub Secret에 GAS_PROXY_URL을 설정하면 그것을 최우선 사용
- 없으면 직접 접속 후 공개 프록시 체인 (cors.sh/jina/allorigins/corsproxy.io)
"""
from __future__ import annotations
import os
import time
from typing import Optional
from urllib.parse import quote
import requests

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_TIMEOUT = 15


def get(url: str, *, timeout: int = DEFAULT_TIMEOUT, retries: int = 2,
        want_xml: bool = False) -> Optional[requests.Response]:
    # 1) Google Apps Script 프록시 (가장 신뢰)
    gas_url = os.getenv("GAS_PROXY_URL", "").strip()
    if gas_url:
        r = _gas_get(gas_url, url, timeout=max(timeout, 25), want_xml=want_xml)
        if r is not None:
            return r
        print("  ⚠ GAS 프록시 실패, 직접/다른 프록시 시도", flush=True)

    # 2) 직접 접속
    r = _direct_get(url, timeout=timeout, retries=retries)
    if r is not None and _looks_ok(r, want_xml=want_xml):
        return r

    # 3) 퍼블릭 프록시 체인 (보조)
    for name, fn in [
        ("cors.sh", _cors_sh_get),
        ("jina", _jina_get),
        ("allorigins", _allorigins_get),
    ]:
        print(f"  → 프록시 {name} 시도", flush=True)
        try:
            r = fn(url, timeout=max(timeout, 20), want_xml=want_xml)
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}", flush=True)
            continue
        if r is not None and _looks_ok(r, want_xml=want_xml):
            print(f"  ✓ {name} 성공", flush=True)
            return r
        print(f"  ✗ {name} 실패", flush=True)
        time.sleep(0.3)

    print(f"  ⚠ 모든 경로 실패: {url}", flush=True)
    return None


def _gas_get(gas_base: str, target: str, *, timeout: int, want_xml: bool):
    sep = "&" if "?" in gas_base else "?"
    proxy = f"{gas_base}{sep}url={quote(target, safe='')}"
    try:
        r = requests.get(proxy, headers={"User-Agent": UA}, timeout=timeout)
        if r.status_code != 200:
            print(f"    GAS HTTP {r.status_code}: {r.text[:200]}", flush=True)
            return None
        body = r.text[:500].lower()
        if "proxy error" in body or "<title>error" in body:
            print(f"    GAS 응답 이상: {r.text[:200]}", flush=True)
            return None
        r.encoding = r.apparent_encoding or "utf-8"
        print(f"    GAS OK ({len(r.content)} bytes)", flush=True)
        return r
    except requests.RequestException as e:
        print(f"    GAS 예외: {type(e).__name__}: {str(e)[:120]}", flush=True)
        return None


def _direct_get(url, *, timeout, retries):
    last = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code < 500:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as e:
            last = type(e).__name__
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    print(f"  ⚠ 직접 GET 실패: {last}", flush=True)
    return None


def _cors_sh_get(url, *, timeout, want_xml):
    proxy = f"https://proxy.cors.sh/{url}"
    r = requests.get(proxy, headers={**HEADERS, "Origin": "https://localhost"},
                     timeout=timeout)
    if r.status_code != 200:
        return None
    return r


def _jina_get(url, *, timeout, want_xml):
    jina = "https://r.jina.ai/" + url
    r = requests.get(jina, headers={
        **HEADERS,
        "X-Return-Format": "html",
        "X-With-Links-Summary": "false",
        "X-No-Cache": "true",
    }, timeout=timeout)
    if r.status_code == 200 and "<html" in r.text[:3000].lower():
        r.encoding = r.apparent_encoding or "utf-8"
        return r
    return None


def _allorigins_get(url, *, timeout, want_xml):
    r = requests.get("https://api.allorigins.win/raw",
                     params={"url": url}, headers=HEADERS, timeout=timeout)
    if r.status_code == 200:
        return r
    return None


def _looks_ok(r: requests.Response, want_xml: bool) -> bool:
    if r.status_code >= 400:
        return False
    body = r.text[:5000].lower()
    if want_xml:
        return ("<?xml" in body) or ("<rss" in body) or ("<feed" in body)
    return "<html" in body or "<!doctype" in body

"""HTML → 본문 텍스트 추출 공통 유틸."""
from __future__ import annotations

import html as htmllib
import re


def html_to_text(raw: str) -> str:
    if not raw:
        return ""
    s = htmllib.unescape(raw)
    s = re.sub(r"<script\b.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<textarea\b.*?</textarea>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p\s*>", "\n", s, flags=re.I)
    s = re.sub(r"</div\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<li\b[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_by_patterns(html: str, patterns: list[str]) -> str:
    """정규식 그룹 1을 순서대로 시도해서 가장 긴 유효 텍스트를 반환."""
    best = ""
    for pat in patterns:
        for m in re.finditer(pat, html, re.S | re.I):
            text = html_to_text(m.group(1))
            if len(text) > len(best):
                best = text
    return best

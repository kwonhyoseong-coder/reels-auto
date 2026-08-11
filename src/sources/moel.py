"""
고용노동부 보도자료
- 목록: https://www.moel.go.kr/news/enews/report/enewsList.do
- 본문: enewsView.do?news_seq=XXXX
"""
import re
from datetime import datetime
from ._http import get

BASE = "https://www.moel.go.kr"
LIST_URL = f"{BASE}/news/enews/report/enewsList.do"
VIEW_URL = f"{BASE}/news/enews/report/enewsView.do"


def fetch(limit: int = 10) -> list[dict]:
    resp = get(LIST_URL)
    if resp is None:
        return []
    resp.encoding = "utf-8"
    html = resp.text

    # 목록에서 news_seq + 제목 추출
    rows = re.findall(
        r'enewsView\.do\?[^"\']*news_seq=(\d+)[^"\']*"[^>]*>([^<]+)<',
        html,
    )
    seen = set()
    articles = []
    for seq, title in rows:
        if seq in seen:
            continue
        seen.add(seq)
        title = title.strip()
        url = f"{VIEW_URL}?news_seq={seq}"
        a = {
            "id": f"moel-{seq}",
            "title": title,
            "url": url,
            "source": "고용노동부",
            "category": _category(title),
            "published": "",
            "summary": "",
            "content": "",
        }
        articles.append(a)
        if len(articles) >= limit:
            break

    # 최신 3건만 본문/날짜 enrichment (네트워크 부하 절약)
    for a in articles[:3]:
        _enrich(a)
    return articles


def _enrich(article: dict) -> None:
    r = get(article["url"])
    if r is None:
        return
    r.encoding = "utf-8"
    html = r.text
    m = re.search(r'(\d{4}-\d{2}-\d{2})', html)
    if m:
        article["published"] = m.group(1)
    content = ""
    m = re.search(
        r'<div[^>]*class="[^"]*b_content[^"]*"[^>]*>(.*?)</div>\s*<div[^>]*class="[^"]*(?:related_detail|contents_util)',
        html, re.S,
    )
    if not m:
        m = re.search(
            r'<div[^>]*class="[^"]*b_content[^"]*"[^>]*>(.*?)</div>',
            html, re.S,
        )
    if m:
        content = _strip_html(m.group(1))[:3000]
    article["content"] = content.strip()
    article["summary"] = content[:200].strip()


def _strip_html(s: str) -> str:
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'&nbsp;', ' ', s)
    s = re.sub(r'&[a-z]+;', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def _category(title: str) -> str:
    t = title
    if any(k in t for k in ["육아", "출산", "육아휴직", "부모", "자녀", "보육"]):
        return "육아"
    if any(k in t for k in ["부동산", "전세", "월세", "주택", "임대"]):
        return "부동산"
    if any(k in t for k in ["세금", "세액", "과세", "세정", "연말정산"]):
        return "세금"
    return "일반정책"


if __name__ == "__main__":
    for a in fetch(3):
        print(f"[{a['published']}] {a['title']}")
        print(f"  {a['url']}")
        print(f"  {a['summary'][:120]}")
        print()

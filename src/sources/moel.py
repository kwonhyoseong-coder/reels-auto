"""
고용노동부 보도자료
- 목록: https://www.moel.go.kr/news/enews/report/enewsList.do
- 본문: enewsView.do?news_seq=XXXX
"""
import re

from ._html import html_to_text
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

    rows = re.findall(
        r"enewsView\.do\?[^\"']*news_seq=(\d+)[^\"']*\"[^>]*>([^<]+)<",
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
        articles.append({
            "id": f"moel-{seq}",
            "title": title,
            "url": url,
            "source": "고용노동부",
            "category": _category(title),
            "published": "",
            "summary": "",
            "content": "",
        })
        if len(articles) >= limit:
            break

    for a in articles[: max(8, min(limit, 10))]:
        enrich(a)
    return articles


def enrich(article: dict) -> None:
    r = get(article["url"])
    if r is None:
        return
    r.encoding = "utf-8"
    html = r.text
    m = re.search(r"(20\d{2}-\d{2}-\d{2})", html)
    if m:
        article["published"] = m.group(1)

    content = ""
    m = re.search(
        r'<div[^>]*class="[^"]*b_content[^"]*"[^>]*>(.*?)'
        r'(?:<div[^>]*class="[^"]*(?:related_detail|contents_util|board_btns|synap_view))',
        html, re.S | re.I,
    )
    if not m:
        m = re.search(
            r'<div[^>]*class="[^"]*b_content[^"]*"[^>]*>(.*?)</div>',
            html, re.S | re.I,
        )
    if m:
        content = html_to_text(m.group(1))
    if len(content) < 80:
        return

    article["content"] = content[:5000]
    article["summary"] = content[:200]
    print(f"    본문 {len(article['content'])}자  ← {article['title'][:36]}")


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
        print(f"  content={len(a.get('content') or '')}자")

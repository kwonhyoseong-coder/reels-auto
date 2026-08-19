"""
중소벤처기업부 보도자료 (공식 RSS + 본문 페이지)
- https://www.mss.go.kr/rss/smba/board/86.do  (보도자료)
- https://www.mss.go.kr/rss/smba/board/310.do (사업공고)
"""
import html as htmllib
import re

from ._html import html_to_text
from ._http import get

PRESS_URL = "https://www.mss.go.kr/rss/smba/board/86.do"
BIZ_URL = "https://www.mss.go.kr/rss/smba/board/310.do"


def fetch(limit: int = 10) -> list[dict]:
    import feedparser

    out: list[dict] = []
    for feed_url, _tag in [(PRESS_URL, "보도자료"), (BIZ_URL, "사업공고")]:
        r = get(feed_url, want_xml=True)
        if r is None:
            print(f"  ⚠ {feed_url} 가져오기 실패")
            continue
        r.encoding = "utf-8"
        d = feedparser.parse(r.text)
        for e in d.entries[:limit]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            summary = (e.get("summary") or e.get("description") or "").strip()
            if "<" in summary:
                summary = html_to_text(summary)
            published = (e.get("published") or e.get("updated") or "")[:16]
            bc = ""
            if "bcIdx=" in link:
                bc = link.split("bcIdx=")[-1].split("&")[0]
            out.append({
                "id": f"mss-{bc or link}",
                "title": title,
                "url": link,
                "source": "중소벤처기업부",
                "category": _category(title + " " + summary),
                "published": published,
                "summary": summary[:200],
                "content": summary,
            })
    # 최신 N건 본문 보강 (제목만 있으면 대본이 공허해짐)
    for a in out[: max(limit, 8)]:
        enrich(a)
    return out[:limit]


def enrich(article: dict) -> None:
    url = article.get("url") or ""
    if not url:
        return
    r = get(url)
    if r is None:
        return
    r.encoding = "utf-8"
    html = r.text

    content = ""
    # 숨겨진 textarea에 보도자료 전문이 들어있음
    m = re.search(
        r'<textarea[^>]*id=["\']editContents["\'][^>]*>(.*?)</textarea>',
        html, re.S | re.I,
    )
    if m:
        content = html_to_text(htmllib.unescape(m.group(1)))
    if len(content) < 80:
        m = re.search(
            r'<div[^>]*class="[^"]*boardSubContent[^"]*"[^>]*>(.*?)</div>',
            html, re.S | re.I,
        )
        if m:
            content = html_to_text(m.group(1))
    if len(content) < 80:
        return

    article["content"] = content[:5000]
    if not article.get("summary"):
        article["summary"] = content[:200]
    if not article.get("published"):
        md = re.search(r"등록일</th>\s*<td[^>]*>\s*([\d.]+)", html)
        if not md:
            md = re.search(r"(20\d{2}[.-]\d{2}[.-]\d{2})", html)
        if md:
            article["published"] = md.group(1).replace(".", "-")
    print(f"    본문 {len(article['content'])}자  ← {article['title'][:36]}")


def _category(title: str) -> str:
    t = title
    if any(k in t for k in ["창업", "소상공인", "자영업", "대출", "보증", "지원금"]):
        return "소상공인"
    if any(k in t for k in ["육아", "출산"]):
        return "육아"
    if any(k in t for k in ["세금", "세액"]):
        return "세금"
    return "일반정책"


if __name__ == "__main__":
    for a in fetch(3):
        print(f"[{a['published']}] {a['title']}")
        print(f"  {a['url']}")
        print(f"  content={len(a.get('content') or '')}자")

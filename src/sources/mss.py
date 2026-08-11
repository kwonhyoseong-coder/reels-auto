"""
중소벤처기업부 보도자료 (공식 RSS가 살아있음)
- https://www.mss.go.kr/rss/smba/board/86.do  (보도자료)
- https://www.mss.go.kr/rss/smba/board/310.do (사업공고)
"""
import feedparser
from ._http import HEADERS

PRESS_URL = "https://www.mss.go.kr/rss/smba/board/86.do"
BIZ_URL = "https://www.mss.go.kr/rss/smba/board/310.do"


def fetch(limit: int = 10) -> list[dict]:
    out: list[dict] = []
    for feed_url, source_tag in [(PRESS_URL, "중소벤처기업부 보도자료"), (BIZ_URL, "중소벤처기업부 사업공고")]:
        d = feedparser.parse(feed_url, request_headers=HEADERS)
        for e in d.entries[:limit]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            # description/summary
            summary = (e.get("summary") or e.get("description") or "").strip()
            if "<" in summary:
                summary = _strip(summary)
            published = (e.get("published") or "")[:10]
            out.append({
                "id": f"mss-{link.split('bcIdx=')[-1] if 'bcIdx=' in link else link}",
                "title": title,
                "url": link,
                "source": "중소벤처기업부",
                "category": _category(title + " " + summary),
                "published": published,
                "summary": summary[:200],
                "content": summary,
            })
    return out[:limit]


def _strip(s: str) -> str:
    import re
    s = re.sub(r'<[^>]+>', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


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
    for a in fetch(5):
        print(f"[{a['published']}] {a['title']}")
        print(f"  {a['url']}")

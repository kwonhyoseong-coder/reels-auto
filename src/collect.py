"""
1단계: 뉴스/보도자료 RSS에서 정책·혜택 후보 수집
"""
import feedparser
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

KST = timezone(timedelta(hours=9))

def fetch_candidates(feeds: list[str] | None = None, days: int = 3) -> list[dict]:
    """최근 N일 내 보도자료 중 키워드 필터링"""
    if feeds is None:
        feeds = os.getenv("RSS_FEEDS", "").split(",")
    keywords = ["지원", "혜택", "지급", "신청", "제도", "복지", "감면", "면제",
                "세금", "부동산", "육아", "보조금", "장려금", "환급", "할인"]
    cutoff = datetime.now(KST) - timedelta(days=days)
    out = []
    for url in feeds:
        url = url.strip()
        if not url:
            continue
        d = feedparser.parse(url)
        for e in d.entries:
            title = e.get("title", "")
            summary = e.get("summary", "")[:300]
            published = _parse_time(e)
            if published and published < cutoff:
                continue
            if any(k in title + summary for k in keywords):
                out.append({
                    "title": title,
                    "url": e.get("link", ""),
                    "summary": summary,
                    "published": published.isoformat() if published else "",
                    "source": d.feed.get("title", url),
                })
    return out

def _parse_time(entry):
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc).astimezone(KST)
    return None

if __name__ == "__main__":
    for item in fetch_candidates():
        print(f"[{item['source']}] {item['title']}")
        print(f"  → {item['url']}")

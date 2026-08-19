"""
보건복지부 보도자료
- 목록: https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027
- 본문: 같은 경로에 act=view&list_no=XXXX
"""
import re

from ._html import html_to_text
from ._http import get

BASE = "https://www.mohw.go.kr/board.es"
LIST_PARAMS = {"mid": "a10503000000", "bid": "0027"}


def fetch(limit: int = 10) -> list[dict]:
    r = get(BASE + "?" + "&".join(f"{k}={v}" for k, v in LIST_PARAMS.items()))
    if r is None:
        return []
    r.encoding = "utf-8"
    html = r.text

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    out = []
    seen = set()
    for row in rows:
        m = re.search(r"act=view(?:&amp;|&)list_no=(\d+)", row)
        if not m:
            continue
        no = m.group(1)
        if no in seen:
            continue
        mt = re.search(r'<a[^>]*class="txt_title"[^>]*title="([^"]+)"', row)
        if not mt:
            ma = re.search(r'<a[^>]*class="txt_title"[^>]*>(.*?)</a>', row, re.S)
            if not ma:
                continue
            inner = re.sub(r"<i[^>]*>.*?</i>", "", ma.group(1), flags=re.S)
            inner = re.sub(r'<span[^>]*class="sr_only"[^>]*>.*?</span>', "", inner, flags=re.S)
            title = html_to_text(inner)
        else:
            title = mt.group(1).strip()
        if not title or len(title) < 3:
            continue
        md = re.search(r'data-label="등록일"[^>]*>\s*(\d{4}-\d{2}-\d{2})', row)
        if not md:
            md = re.search(r"(\d{4}-\d{2}-\d{2})", row)
        published = md.group(1) if md else ""

        url = f"{BASE}?mid=a10503000000&bid=0027&act=view&list_no={no}"
        out.append({
            "id": f"mohw-{no}",
            "title": title,
            "url": url,
            "source": "보건복지부",
            "category": _category(title),
            "published": published,
            "summary": "",
            "content": "",
        })
        seen.add(no)
        if len(out) >= limit:
            break

    for a in out[: max(8, min(limit, 10))]:
        enrich(a)
    return out


def enrich(article: dict) -> None:
    r = get(article["url"])
    if r is None:
        return
    r.encoding = "utf-8"
    html = r.text
    if not article.get("published"):
        m = re.search(r"(20\d{2}-\d{2}-\d{2})", html)
        if m:
            article["published"] = m.group(1)

    content = ""
    m = re.search(
        r'<div class="viewArea">(.*?)(?:<div class="file"|class="board_btns"|첨부파일)',
        html, re.S | re.I,
    )
    if m:
        content = html_to_text(m.group(1))
    if len(content) < 80:
        m = re.search(
            r'<div[^>]*class="[^"]*board_view[^"]*"[^>]*>(.*?)(?:첨부파일|이전글)',
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
    if any(k in t for k in ["육아", "출산", "육아휴직", "부모", "자녀", "보육", "아동", "영유아"]):
        return "육아"
    if any(k in t for k in ["부동산", "전세", "월세", "주택", "임대"]):
        return "부동산"
    if any(k in t for k in ["세금", "세액", "과세", "연말정산"]):
        return "세금"
    if any(k in t for k in ["연금", "기초생활", "복지", "장애인", "노인", "의료"]):
        return "복지"
    return "일반정책"


if __name__ == "__main__":
    for a in fetch(5):
        print(f"[{a['published']}] {a['title']}")
        print(f"  {a['url']}")
        print(f"  content={len(a.get('content') or '')}자")

"""
보건복지부 보도자료
- 목록: https://www.mohw.go.kr/board.es?mid=a10503000000&bid=0027
- 본문: 같은 경로에 act=view&list_no=XXXX
"""
import re
from ._http import get

BASE = "https://www.mohw.go.kr/board.es"
LIST_PARAMS = {"mid": "a10503000000", "bid": "0027"}


def fetch(limit: int = 10) -> list[dict]:
    r = get(BASE + "?" + "&".join(f"{k}={v}" for k, v in LIST_PARAMS.items()))
    if r is None:
        return []
    r.encoding = "utf-8"
    html = r.text

    # tr 단위로 잘라서 list_no, 제목, 날짜 추출
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    out = []
    seen = set()
    for row in rows:
        # act=view&amp;list_no=숫자 (html entity) 또는 act=view&list_no=숫자
        m = re.search(r'act=view(?:&amp;|&)list_no=(\d+)', row)
        if not m:
            continue
        no = m.group(1)
        if no in seen:
            continue
        # 제목: <a ...class="txt_title" ...> 실제 텍스트 (i/span 자식 제외)
        # 우선 title 속성
        mt = re.search(r'<a[^>]*class="txt_title"[^>]*title="([^"]+)"', row)
        if not mt:
            # a 태그 안의 HTML을 잡아서 태그 제거 후 텍스트만
            ma = re.search(r'<a[^>]*class="txt_title"[^>]*>(.*?)</a>', row, re.S)
            if ma:
                inner = re.sub(r'<i[^>]*>.*?</i>', '', ma.group(1), flags=re.S)
                inner = re.sub(r'<span[^>]*class="sr_only"[^>]*>.*?</span>', '', inner, flags=re.S)
                inner = re.sub(r'<[^>]+>', '', inner)
                title = inner.replace('&nbsp;', ' ').strip()
            else:
                continue
        else:
            title = mt.group(1).strip()
        if not title or len(title) < 3:
            continue
        # 날짜: data-label="등록일">2026-08-07
        md = re.search(r'data-label="등록일"[^>]*>\s*(\d{4}-\d{2}-\d{2})', row)
        if not md:
            md = re.search(r'(\d{4}-\d{2}-\d{2})', row)
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

    # 본문은 상위 3건만 가져오기 (트래픽/속도 고려)
    for a in out[:3]:
        _enrich(a)
    return out


def _enrich(article: dict) -> None:
    r = get(article["url"])
    if r is None:
        return
    r.encoding = "utf-8"
    html = r.text
    if not article["published"]:
        m = re.search(r'(\d{4}-\d{2}-\d{2})', html)
        if m:
            article["published"] = m.group(1)

    # 본문: class에 cont/view-con/content 등
    for cls in ["view-con", "view_con", "viewCont", "bbs-con", "cont", "content"]:
        m = re.search(
            rf'<div[^>]*class="[^"]*{cls}[^"]*"[^>]*>(.*?)</div>',
            html, re.S,
        )
        if m:
            text = _strip_html(m.group(1))
            if len(text) > 50:
                article["content"] = text.strip()
                article["summary"] = text[:200].strip()
                return


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
        print(f"  {a['summary'][:100]}")
        print()

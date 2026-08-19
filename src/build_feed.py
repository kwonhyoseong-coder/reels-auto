"""
각 부처 크롤러를 돌려서 통합 RSS 1개 + JSON 캐시를 생성한다.

- output/policy-feed.xml  ← Make가 구독할 RSS
- output/policy-feed.json ← 디버그/중복 체크용

Make는 이 파일을 HTTP로 가져가야 하므로, 이 스크립트의 결과물을
GitHub Pages / Cloudflare R2 / Netlify / 자체 서버 어디에 올리든 공개 URL만
Make의 RSS Watch 모듈에 넣으면 된다.
(로컬 파일 경로는 Make에서 읽을 수 없음에 주의)
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from feedgen.feed import FeedGenerator

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sources import ALL_SOURCES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(exist_ok=True)

KST = timezone(timedelta(hours=9))

# 키워드 필터: "혜택/지원/신청" 류가 들어간 글만 통과
INCLUDE_KEYWORDS = [
    "지원", "지급", "신청", "혜택", "제도", "보조금", "장려금",
    "감면", "면제", "환급", "할인", "대상", "요건", "신규",
    "확대", "인상", "인하", "달라집니다",
    "모집", "공고", "선발", "육성", "지원금", "사업화",
]
# 투기/증권성 기사는 사전 차단 (LLM 프롬프트에서도 막지만 여기서 한 번 더)
EXCLUDE_KEYWORDS = ["주가", "코스피", "코스닥", "매수", "매도", "가상자산", "비트코인"]


def keyword_filter(title: str, summary: str) -> bool:
    text = title + " " + summary
    if any(x in text for x in EXCLUDE_KEYWORDS):
        return False
    return any(k in text for k in INCLUDE_KEYWORDS)


def parse_date(s: str) -> datetime:
    if not s:
        return datetime.now(KST)
    for fmt in ("%Y-%m-%d", "%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:len(fmt) + 2].strip(), fmt).replace(tzinfo=KST)
        except ValueError:
            continue
    return datetime.now(KST)


def build(per_source: int = 10) -> tuple[Path, list[dict]]:
    all_articles: list[dict] = []
    for fetch_fn in ALL_SOURCES:
        name = fetch_fn.__module__
        try:
            print(f"[{name}] 수집 중...")
            items = fetch_fn(limit=per_source)
            print(f"   → {len(items)}건")
            all_articles.extend(items)
        except Exception as e:
            print(f"   ⚠ {name} 실패: {e}")
        time.sleep(0.5)

    # 중복 제거 (id 기준) + 날짜 최신순 정렬
    uniq: dict[str, dict] = {}
    for a in all_articles:
        uniq[a["id"]] = a
    articles = sorted(uniq.values(), key=lambda x: x.get("published", ""), reverse=True)

    # 키워드 필터
    passed = [a for a in articles if keyword_filter(a["title"], a.get("summary", ""))]
    print(f"\n총 {len(articles)}건 → 키워드 필터 통과 {len(passed)}건")

    # XML 피드 생성
    fg = FeedGenerator()
    fg.title("정책 혜택 큐레이션 (정부 보도자료 통합)")
    fg.description("고용노동부·보건복지부·중소벤처기업부 공식 보도자료 중 혜택/지원 관련 글")
    fg.link(href="https://example.invalid/policy-feed.xml", rel="self")
    fg.language("ko")

    for a in passed[:50]:  # 피드는 최신 50개만
        entry = fg.add_entry()
        guid = a["id"] or hashlib.sha1(a["url"].encode()).hexdigest()[:12]
        entry.id(guid)
        entry.title(f"[{a['source']}] {a['title']}")
        entry.link(href=a["url"])
        desc = a.get("summary") or a.get("content") or ""
        entry.description(desc[:500])
        # LLM이 본문 전문을 요약에 쓸 수 있게 content:encoded 로 전문 포함
        if a.get("content"):
            entry.content(a["content"][:5000], type="text")
        entry.pubDate(parse_date(a.get("published", "")))
        # 카테고리/출처를 LLM이 읽을 수 있게
        entry.category(term=a.get("category", "일반정책"))
        entry.author(name=a["source"])

    xml_path = OUT_DIR / "policy-feed.xml"
    fg.rss_file(str(xml_path), pretty=True)

    json_path = OUT_DIR / "policy-feed.json"
    json_path.write_text(json.dumps(passed, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ {xml_path}  ({len(passed)} entries)")
    return xml_path, passed


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--per-source", type=int, default=10)
    args = p.parse_args()
    build(per_source=args.per_source)

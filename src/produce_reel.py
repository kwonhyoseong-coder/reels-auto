"""
전체 릴스 자동 생성 파이프라인 (GitHub Actions용, 완전 무료 스택).

순서:
  1. 부처 크롤링 → 통합 피드
  2. 이미 만든 기사(중복) 제외 → 1건 선택
  3. Gemini API로 대본 JSON 생성
  4. edge-tts + moviepy로 1080x1920 MP4 렌더
  5. MP4 + 메타데이터 JSON을 output/ 에 저장
     - GitHub Actions에서는 upload-artifact로 업로드
     - Make가 webhook 트리거로 영상 URL을 받아감
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from build_feed import build as build_feed, keyword_filter
from gemini_script import generate_script, full_narration
from render import render_reel

OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)
STATE_FILE = OUT / "state.json"
KST = timezone(timedelta(hours=9))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"published_ids": []}


def save_state(state: dict) -> None:
    # 발행 이력은 최근 500건만 유지
    state["published_ids"] = state["published_ids"][-500:]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_article(articles: list[dict], state: dict) -> dict | None:
    """키워드 필터 통과 + 아직 안 만든 것 중 최신 1건."""
    seen = set(state.get("published_ids", []))
    for a in articles:
        if a["id"] in seen:
            continue
        if not keyword_filter(a["title"], a.get("summary", "")):
            continue
        return a
    return None


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="영상만 만들고 state 업데이트는 안 함")
    parser.add_argument("--test", action="store_true",
                        help="더미 대본으로 샘플 영상만 생성")
    args = parser.parse_args()

    if args.test:
        sample = {
            "hook": "8월부터 육아휴직 급여가 최대 250만 원으로 오릅니다",
            "body": [
                "기존 월 최대 150만 원에서 250만 원으로 인상됩니다.",
                "첫 3개월간 적용되며 고용보험 가입자면 신청할 수 있습니다.",
                "관할 고용센터나 고용24에서 온라인 신청 가능합니다.",
            ],
            "cta": "자세한 내용은 고용노동부 공식 누리집에서 확인하세요",
            "hashtags": ["#육아휴직", "#출산혜택", "#고용노동부", "#정부지원"],
            "source_label": "고용노동부 보도자료",
        }
        out = OUT / f"sample_{datetime.now():%Y%m%d_%H%M}.mp4"
        render_reel(sample, out, OUT / "_work")
        print(f"✅ 샘플: {out}")
        return

    print("① 피드 빌드 중...")
    _, articles = build_feed(per_source=int(os.getenv("PER_SOURCE", "15")))

    state = load_state()
    article = pick_article(articles, state)
    if not article:
        print("🟡 새로 만들 기사가 없습니다. 종료.")
        return

    print(f"② 대상 선정: [{article['source']}] {article['title']}")

    print("③ Gemini 대본 생성 중...")
    script = generate_script(article)
    print("   hook:", script["hook"])
    for b in script["body"]:
        print("   -", b)
    print("   cta :", script["cta"])

    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    article_id_safe = hashlib.sha1(article["id"].encode()).hexdigest()[:10]
    mp4 = OUT / f"reel_{stamp}_{article_id_safe}.mp4"
    meta = OUT / mp4.name.replace(".mp4", ".json")

    print("④ 영상 렌더링 중...")
    render_reel(script, mp4, OUT / f"_work_{stamp}")
    print(f"   → {mp4} ({mp4.stat().st_size // 1024} KB)")

    # Make가 읽을 메타데이터
    caption = build_caption(script, article)
    payload = {
        "article_id": article["id"],
        "title": article["title"],
        "source": article["source"],
        "url": article["url"],
        "published": article.get("published", ""),
        "video_path": str(mp4.relative_to(ROOT)),
        "caption": caption,
        "narration": full_narration(script),
        "created_at": datetime.now(KST).isoformat(),
    }
    meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   → {meta}")

    if not args.dry_run:
        state.setdefault("published_ids", []).append(article["id"])
        save_state(state)
        print("⑤ state 업데이트 완료")
    else:
        print("⑤ --dry-run: state 업데이트 건너뜀")


def build_caption(script: dict, article: dict) -> str:
    tags = " ".join(script.get("hashtags", []))
    body = "\n".join(f"• {b}" for b in script["body"])
    return (
        f"{script['hook']}\n\n"
        f"{body}\n\n"
        f"{script['cta']}\n\n"
        f"🔗 원문: {article['url']}\n"
        f"📌 출처: {article['source']} ({article.get('published','')})\n\n"
        f"{tags}\n"
        f"#정부혜택 #꿀정보 #릴스"
    )


if __name__ == "__main__":
    run()

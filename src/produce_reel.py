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
import re
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


def score_article(a: dict) -> int:
    """릴스로 만들 가치가 높을수록 높은 점수.
    핵심: '시청자(국민)에게 직접 돈/서비스/권리로 돌아오는가'"""
    title = a.get("title", "")
    body = (a.get("summary", "") or "") + " " + (a.get("content", "") or "")
    head = title + " " + body[:600]
    score = 0

    # ✓ 시민이 직접 받는 혜택·서비스
    citizen_benefits = [
        "지원금", "보조금", "장려금", "수당", "급여", "연금", "환급",
        "감면", "면제", "할인", "무료", "지원대상", "신청하세요", "신청방법",
        "신청기간", "자격요건", "신청접수", "모집공고", "대상자",
        "확대 지원", "최대", "지급", "인상", "도입", "지원",
        "육아휴직", "부모급여", "아동수당", "기초생활", "청년도약",
    ]
    for k in citizen_benefits:
        if k in title:
            score += 25
        elif k in head:
            score += 8

    # ✓ 구체적 숫자/금액
    if re.search(r"\d{1,4}(?:,\d{3})*(?:\s*(?:만원|억원|천만원|원))", body):
        score += 20
    if re.search(r"\d+(?:\.\d+)?%", body):
        score += 10
    if re.search(r"\d{1,2}\.\d{1,2}", title):
        score += 5

    # ✓ 날짜/마감 정보
    if re.search(r"\d{1,2}월\s*\d{1,2}일", body) or "부터" in head or "시행" in head:
        score += 10
    if "마감" in body or "까지" in body[:300]:
        score += 10

    # ✗ PR성/내부 활동/간담회는 강하게 감점
    pr_keywords = [
        "업무보고", "간담회", "업무협약", "MOU", "현장방문", "현장점검",
        "첫 회의", "출범식", "워크숍", "세미나", "포럼", "축하", "격려",
        "브리핑", "논의", "점검 회의", "진단 실시", "특별진단",
        "개최", "주최", "기념식", "위원회 출범", "현장 간담",
        "현장 점검", "현장챙", "지도·점검", "점검·", "점검 결과", "합동점검",
        "현장 방문", "조직문화", "현장 행보", "현장간담", "현장방문",
        "위원장", "위원회", "실시", "점검",
    ]
    for k in pr_keywords:
        if k in title:
            score -= 60
        elif k in head[:300]:
            score -= 20

    # ✗ 사측/기업 대상(B2B) 뉴스는 일반 시청자 혜택 아님
    b2b = ["대·중소기업", "납품대금", "상생협약", "가맹점", "프랜차이즈",
           "수출기업", "중견기업", "대기업", "협력사", "대중소"]
    for k in b2b:
        if k in title:
            score -= 15

    # ✗ 추상적/관료적 표현
    for k in ["발표했습니다", "계획입니다", "논의했습니다", "모색", "살펴보"]:
        if k in body[:300]:
            score -= 5

    # 부처별 가중
    if a.get("source") == "고용노동부":
        score += 3
    if a.get("source") == "보건복지부":
        score += 3

    # 본문이 너무 짧으면 정보 부족
    if len(body) < 100:
        score -= 10
    return score


def pick_article(articles: list[dict], state: dict) -> tuple[dict | None, list[dict]]:
    """키워드 필터 통과 + 아직 안 만든 것 중 점수 높은 1건 반환.
    디버그를 위해 상위 5개 점수도 같이 반환."""
    seen = set(state.get("published_ids", []))
    candidates = []
    for a in articles:
        if a["id"] in seen:
            continue
        if not keyword_filter(a["title"], a.get("summary", "")):
            continue
        s = score_article(a)
        candidates.append((s, a))
    candidates.sort(key=lambda x: x[0], reverse=True)
    top5 = [{"score": s, "source": a["source"], "title": a["title"]} for s, a in candidates[:5]]
    return (candidates[0][1] if candidates else None), top5


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
    article, top5 = pick_article(articles, state)
    if not article:
        print("🟡 새로 만들 기사가 없습니다. 종료.")
        return

    print("② 대상 선정 후보 (점수순):")
    for t in top5:
        print(f"   {t['score']:+4d}  [{t['source']}] {t['title'][:60]}")
    print(f"   → 선택: [{article['source']}] {article['title']}")

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

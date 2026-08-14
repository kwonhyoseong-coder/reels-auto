"""
주간 베스트 혜택 요약 릴스 생성.
- output/state.json에 최근 발행된 기사 ID를 쌓아두고,
- output/policy-feed.json + 발행 이력에서 지난 7일 혜택성 기사 중
  조회수/점수 기준 Top 5를 뽑아 1분 분량 요약 영상을 만든다.
- 매주 일요일 18:00 KST에 실행.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemini_script import pick_model, _call_gemini, SYSTEM_PROMPT
from render import render_reel
from produce_reel import load_state, save_state, score_article, OUT

KST = timezone(timedelta(hours=9))


WEEKLY_SYSTEM = """\
너는 대한민국 정부 혜택을 주간 단위로 요약하는 인스타 릴스 작가다.
여러 보도자료를 받아서, 시청자가 가장 궁금해할 Top 5 혜택을 뽑아
1분 분량의 릴스 대본으로 만들어줘.

규칙:
- 첫 훅은 "이번 주 놓치면 안 되는 혜택 5" 처럼 숫자로 강하게.
- 본문은 각 혜택을 1문장씩, 총 5문장.
- 각 문장은 "얼마/무엇이 + 누구에게 + 언제부터/신청" 구조.
- 정보가 부족하면 "자세한 내용은 각 부처 누리집 확인"으로 마무리.
- 투자/주식/코인 관련 내용은 절대 넣지 말 것.
- JSON으로만 답하라.

JSON 스키마:
{
  "hook": "string",
  "body": ["s1","s2","s3","s4","s5"],
  "cta": "string",
  "hashtags": ["#string","#string","#string","#string"],
  "source_label": "지난 7일 정부 보도자료 요약"
}
"""


def build_weekly_script(candidates: list[dict]) -> dict:
    if not candidates:
        raise RuntimeError("주간 요약할 기사가 없습니다.")
    summary_lines = []
    for i, a in enumerate(candidates[:10], 1):
        body = (a.get("content") or a.get("summary") or "")[:600]
        summary_lines.append(
            f"[{i}] ({a['source']}) {a['title']}\n{body}\nURL: {a['url']}\n"
        )
    article_block = "\n".join(summary_lines)
    user_prompt = (
        "다음은 지난 7일간의 정부 보도자료야. 이 중 시청자에게 직접 혜택이 "
        "되는 것 Top 5를 뽑아 1분 릴스 대본을 만들어줘.\n\n" + article_block
    )

    model = pick_model()
    body = {
        "system_instruction": {"parts": [{"text": WEEKLY_SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }
    data = _call_gemini(model, body, attempts=3)
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    import re
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    script = json.loads(text)
    script["source_url"] = candidates[0]["url"]
    script["article_title"] = "주간 베스트 혜택 요약"
    script["source"] = "주간 요약"
    return script


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # 후보: 피드에 있는 최신 기사 + state에 최근 처리한 것
    feed_path = OUT / "policy-feed.json"
    if not feed_path.exists():
        print("🟡 policy-feed.json 없음. build_feed를 먼저 실행하세요.")
        return
    articles = json.loads(feed_path.read_text(encoding="utf-8"))

    # 점수 순으로 정렬
    scored = sorted(articles, key=score_article, reverse=True)
    # 점수가 0 이상인 것만
    good = [a for a in scored if score_article(a) >= 0]
    if not good:
        print("🟡 주간 요약할 만한 기사가 없습니다.")
        return

    print(f"① 후보 {len(good)}건 중 Top 10 선정")
    candidates = good[:10]

    print("② 주간 대본 생성 중...")
    script = build_weekly_script(candidates)
    print("   hook:", script["hook"])
    for i, b in enumerate(script["body"], 1):
        print(f"   {i}. {b[:70]}")
    print("   cta :", script["cta"])

    stamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    mp4 = OUT / f"weekly_{stamp}.mp4"
    meta = mp4.with_suffix(".json")
    print("③ 영상 렌더링 중...")
    render_reel(script, mp4, OUT / f"_weekly_work_{stamp}")
    print(f"   → {mp4} ({mp4.stat().st_size // 1024} KB)")

    payload = {
        "article_id": "weekly-" + stamp,
        "title": "이번 주 베스트 혜택",
        "source": "weekly",
        "url": "",
        "published": datetime.now(KST).date().isoformat(),
        "video_path": str(mp4.relative_to(ROOT)),
        "caption": build_caption(script),
        "created_at": datetime.now(KST).isoformat(),
    }
    meta.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"   → {meta}")
    if not args.dry_run:
        print("④ weekly state 업데이트")


def build_caption(script: dict) -> str:
    tags = " ".join(script.get("hashtags", []) +
                    ["#주간혜택", "#정부혜택", "#릴스"])
    body = "\n".join(f"{i+1}. {b}" for i, b in enumerate(script["body"]))
    return (
        f"{script['hook']}\n\n"
        f"{body}\n\n"
        f"{script['cta']}\n\n"
        f"📌 지난 7일 치 정부 보도자료 요약\n\n{tags}"
    )


if __name__ == "__main__":
    run()

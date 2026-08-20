"""
완성된 릴스를 텔레그램으로 보낸다. (반자동 게시용, 완전 무료)

필요 환경변수:
  TELEGRAM_BOT_TOKEN  — @BotFather 가 준 토큰
  TELEGRAM_CHAT_ID    — 본인 숫자 ID

사용:
  python src/notify_telegram.py --mp4 output/reel.mp4 --meta output/reel.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"


def _api(token: str, method: str, **kwargs):
    url = API.format(token=token, method=method)
    r = requests.post(url, timeout=120, **kwargs)
    if r.status_code != 200:
        raise RuntimeError(f"Telegram {method} {r.status_code}: {r.text[:400]}")
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} 실패: {data}")
    return data


def send_reel(mp4: Path, meta: dict, video_url: str = "") -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print("🟡 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 없음 — 알림 생략")
        return

    title = meta.get("title") or "오늘의 혜택"
    source = meta.get("source") or ""
    caption = (meta.get("caption") or "").strip()
    article_url = meta.get("url") or meta.get("article_url") or ""

    how_to = (
        "✅ 오늘의 혜택 릴스가 준비됐어요\n\n"
        f"제목: {title}\n"
        f"출처: {source}\n"
    )
    if article_url:
        how_to += f"원문: {article_url}\n"
    if video_url:
        how_to += f"백업: {video_url}\n"
    how_to += (
        "\n📱 올리는 법 (20초)\n"
        "1. 아래 영상을 눌러 저장(다운로드)\n"
        "2. 인스타 → ＋ → 릴스 → 이 영상 선택\n"
        "3. 다음 메시지를 길게 눌러 복사 → 캡션에 붙여넣기\n"
        "4. 공유\n"
    )

    print("↑ 텔레그램 안내 전송...")
    _api(token, "sendMessage", data={
        "chat_id": chat,
        "text": how_to[:4000],
        "disable_web_page_preview": True,
    })

    if mp4 and mp4.exists():
        print(f"↑ 영상 전송... ({mp4.stat().st_size // 1024} KB)")
        with mp4.open("rb") as f:
            _api(
                token, "sendVideo",
                data={"chat_id": chat, "supports_streaming": True},
                files={"video": (mp4.name, f, "video/mp4")},
            )
    elif video_url:
        _api(token, "sendMessage", data={
            "chat_id": chat,
            "text": f"영상 링크:\n{video_url}",
        })
    else:
        print("⚠ 영상 파일/URL 없음")

    if caption:
        print("↑ 캡션 전송...")
        # 길게 눌러 복사하기 쉽게 캡션만 따로
        text = caption
        if len(text) > 4000:
            text = text[:3990] + "…"
        _api(token, "sendMessage", data={
            "chat_id": chat,
            "text": text,
            "disable_web_page_preview": True,
        })

    print("✅ 텔레그램 전송 완료")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mp4", default="")
    p.add_argument("--meta", default="")
    p.add_argument("--video-url", default="")
    args = p.parse_args()

    meta = {}
    if args.meta and Path(args.meta).exists():
        meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))

    mp4 = Path(args.mp4) if args.mp4 else None
    try:
        send_reel(mp4, meta, video_url=args.video_url)
    except Exception as e:
        print(f"❌ 텔레그램 실패: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

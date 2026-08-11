"""
3단계: 대본 → 1080x1920 릴스 MP4
- edge-tts로 한국어 음성 생성
- 음성 타이밍에 맞춰 자막을 한 줄씩 표시
- 상단 후킹 타이틀, 하단 출처 표기
"""
import asyncio
import os
import re
from pathlib import Path

import edge_tts
from moviepy import (
    AudioFileClip, CompositeVideoClip, ImageClip, TextClip,
    concatenate_videoclips, ColorClip,
)
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"
FONT_REG = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"

# 릴스 세이프존: 위 15%, 아래 25%는 텍스트 비움
SAFE_TOP = int(H * 0.20)
SAFE_BOTTOM = int(H * 0.78)

BG_COLOR = (15, 23, 42)       # 슬레이트
ACCENT = (250, 204, 21)       # 옐로우
WHITE = (248, 250, 252)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH if bold else FONT_REG, size)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """한글 어절 단위 줄바꿈"""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_background(path: Path):
    """단색 배경 + 약한 그라데이션 느낌"""
    img = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        ratio = y / H
        r = int(BG_COLOR[0] * (1 - ratio * 0.3))
        g = int(BG_COLOR[1] * (1 - ratio * 0.3))
        b = int(BG_COLOR[2] + 10 * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    img.save(path)


async def _synth(text: str, out_mp3: Path):
    # ko-KR-SunHiNeural / ko-KR-InJoonNeural 등
    communicate = edge_tts.Communicate(text, voice="ko-KR-SunHiNeural", rate="+8%")
    await communicate.save(str(out_mp3))


def synthesize(text: str, out_mp3: Path) -> Path:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth(text, out_mp3))
    return out_mp3


def _caption_image(line: str, out_png: Path, accent: bool = False):
    """자막 한 줄 렌더 (검은 그림자 + 흰 글씨)"""
    img = Image.new("RGBA", (W, 320), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(64, bold=True)
    lines = _wrap(draw, line, font, int(W * 0.86))
    line_h = 90
    total_h = line_h * len(lines)
    y = (320 - total_h) // 2
    for ln in lines:
        tw = draw.textlength(ln, font=font)
        x = (W - tw) // 2
        # 그림자
        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3)]:
            draw.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0, 220))
        draw.text((x, y), ln, font=font, fill=ACCENT if accent else WHITE)
        y += line_h
    img.save(out_png)


def _title_image(hook: str, source: str, out_png: Path):
    img = Image.new("RGBA", (W, SAFE_TOP + 120), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 상단 노란 바
    draw.rectangle([(60, 80), (220, 92)], fill=ACCENT)
    draw.text((60, 110), "오늘의 혜택", font=_font(40), fill=ACCENT)
    hook_font = _font(72, bold=True)
    lines = _wrap(draw, hook, hook_font, int(W * 0.88))
    y = 200
    for ln in lines:
        draw.text((60, y), ln, font=hook_font, fill=WHITE)
        y += 96
    # 출처
    draw.text((60, SAFE_TOP + 40), source, font=_font(28, bold=False), fill=(180, 190, 210))
    img.save(out_png)


def _footer_image(cta: str, out_png: Path):
    img = Image.new("RGBA", (W, int(H * 0.22)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(60, 30), (W - 60, 180)], outline=ACCENT, width=4)
    draw.text((90, 70), cta, font=_font(40, bold=True), fill=WHITE)
    draw.text((90, 130), "공식 출처 기반 · 투자 정보 X", font=_font(26, bold=False), fill=(180, 190, 210))
    img.save(out_png)


def render_reel(script: dict, out_path: Path, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    narration = " ".join([script["hook"], *script["body"], script["cta"]])
    mp3 = work_dir / "voice.mp3"
    synthesize(narration, mp3)
    audio = AudioFileClip(str(mp3))
    duration = audio.duration + 0.8

    # 배경
    bg_png = work_dir / "bg.png"
    make_background(bg_png)

    # 본문 자막: 문장을 시간 균등 분할
    sentences = [script["hook"], *script["body"], script["cta"]]
    seg = duration / len(sentences)

    clips = [ImageClip(str(bg_png)).with_duration(duration)]

    # 타이틀 (처음 2초 후 사라지게)
    title_png = work_dir / "title.png"
    _title_image(script["hook"], script.get("source_label", ""), title_png)
    title_clip = (ImageClip(str(title_png))
                  .with_start(0)
                  .with_duration(min(3.0, duration))
                  .with_position(("center", 0)))
    clips.append(title_clip)

    # 자막
    for i, sent in enumerate(sentences):
        cap_png = work_dir / f"cap_{i}.png"
        _caption_image(sent, cap_png, accent=(i == 0))
        start = i * seg
        cap = (ImageClip(str(cap_png))
               .with_start(start)
               .with_duration(seg + 0.1)
               .with_position(("center", int(H * 0.42))))
        clips.append(cap)

    # 하단 CTA
    foot_png = work_dir / "footer.png"
    _footer_image(script["cta"], foot_png)
    foot = (ImageClip(str(foot_png))
            .with_start(0)
            .with_duration(duration)
            .with_position(("center", SAFE_BOTTOM)))
    clips.append(foot)

    video = CompositeVideoClip(clips, size=(W, H)).with_audio(audio)
    # Instagram Reels 스펙 맞춤:
    # - H.264 + yuv420p (progressive, 4:2:0)
    # - AAC 48kHz 128kbps stereo
    # - +faststart (moov atom을 파일 앞으로 — 스트리밍/API 처리에 필수)
    # - 3~5 Mbps VBR
    video.write_videofile(
        str(out_path),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        audio_fps=48000,
        audio_bitrate="128k",
        preset="medium",
        bitrate="3500k",
        threads=4,
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",
            "-profile:v", "high",
            "-level", "4.0",
            "-movflags", "+faststart",
        ],
        logger=None,
    )
    video.close()
    audio.close()
    return out_path


if __name__ == "__main__":
    import sys
    sample = {
        "hook": "8월부터 육아휴직 급여가 최대 250만 원으로 오릅니다",
        "body": [
            "기존 월 최대 150만 원에서 250만 원으로 인상됩니다.",
            "첫 3개월간 적용되며, 고용보험 가입자면 신청할 수 있습니다.",
            "관할 고용센터나 고용24에서 온라인 신청 가능합니다.",
        ],
        "cta": "자세한 내용은 고용노동부 공식 누리집에서 확인하세요",
        "source_label": "고용노동부 보도자료 2026.08.01",
    }
    out = Path("output/sample.mp4")
    render_reel(sample, out, Path("output/_work"))
    print("✅", out)

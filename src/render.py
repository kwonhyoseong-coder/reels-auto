"""
릴스 렌더러 v3
- 0.7초 브레이킹 뉴스 인트로
- 5개 슬라이드: 후킹 / 본문 3 / CTA
- 장면마다 카테고리 아이콘 삽입
- BGM: 자체 생성 앰비언트 비트 (bgm.py)
- TTS: edge-tts SunHi
"""
from __future__ import annotations
import asyncio
import os
from pathlib import Path

import edge_tts
import numpy as np
from moviepy import (
    AudioArrayClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bgm import make_bgm
from icons import icon_for

W, H = 1080, 1920
FPS = 30

# 세이프존: 위/아래 인스타 UI를 피해 22%
SAFE_TOP = int(H * 0.22)
SAFE_BOTTOM = int(H * 0.78)
CONTENT_W = int(W * 0.86)

FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_REG = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
FONT_EXTRA = "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf"

# 5+1 슬라이드 컬러 (인트로부터 콜투액션까지)
PALETTE = [
    {"bg": (15, 23, 42), "accent": (250, 204, 21)},    # 인트로 - 옐로
    {"bg": (15, 23, 42), "accent": (250, 204, 21)},    # 훅 - 옐로
    {"bg": (30, 41, 59), "accent": (56, 189, 248)},     # body1 - 스카이
    {"bg": (30, 41, 59), "accent": (52, 211, 153)},     # body2 - 에메랄드
    {"bg": (30, 41, 59), "accent": (244, 114, 182)},    # body3 - 핑크
    {"bg": (15, 23, 42), "accent": (250, 204, 21)},    # CTA - 옐로
]
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)


# ─────────────────────────── TTS ────────────────────────────
async def _synth(text, out):
    await edge_tts.Communicate(text, voice="ko-KR-SunHiNeural", rate="+5%").save(str(out))


def synthesize(text, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth(text, out))
    return out


# ─────────────────────────── 폰트/랩 ────────────────────────────
def font(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def wrap(draw, text, fnt, max_width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ─────────────────────────── 슬라이드 렌더 ────────────────────────────
def gradient_bg(top, bottom):
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        r = y / H
        c = tuple(int(top[i]*(1-r) + bottom[i]*r) for i in range(3))
        for x in range(W):
            px[x, y] = c
    return img.convert("RGBA")


def draw_intro(path, accent):
    """브레이킹 뉴스 인트로 - 0.7초."""
    img = gradient_bg((10, 15, 30), (2, 6, 18))
    d = ImageDraw.Draw(img)
    # 상하 레드 바
    d.rectangle([0, SAFE_TOP - 60, W, SAFE_TOP - 40], fill=(220, 38, 38))
    d.rectangle([0, SAFE_BOTTOM + 40, W, SAFE_BOTTOM + 60], fill=(220, 38, 38))
    # 큰 BREAKING
    f = font(150, bold=True)
    txt = "BREAKING"
    tw = d.textlength(txt, font=f)
    d.text(((W-tw)//2, H//2 - 200), txt, font=f, fill=(250, 204, 21))
    f2 = font(82, bold=True)
    txt2 = "정책 혜택 알림"
    tw2 = d.textlength(txt2, font=f2)
    d.text(((W-tw2)//2, H//2 - 10), txt2, font=f2, fill=WHITE)
    # 깜빡이는 점
    cx, cy, r = W//2, H//2 + 130, 22
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(220, 38, 38))
    img.convert("RGB").save(path, quality=95)


def draw_card(text, idx, total, sub, category, path):
    """본문 슬라이드 한 장."""
    pal = PALETTE[idx % len(PALETTE)]
    bg = gradient_bg(pal["bg"], (5, 10, 24))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # 장식 원
    for i, (cx, cy, r) in enumerate([
        (W - 130, SAFE_TOP + 80, 180),
        (100, SAFE_BOTTOM - 80, 120),
    ]):
        od.ellipse([cx-r, cy-r, cx+r, cy+r],
                  outline=(*pal["accent"], 60), width=4)
    bg = Image.alpha_composite(bg, overlay)
    d = ImageDraw.Draw(bg)

    # 상단 진행 바
    bar_x0, bar_y0, bar_x1, bar_y1 = 60, 110, W-60, 118
    d.rounded_rectangle([bar_x0, bar_y0, bar_x1, bar_y1], radius=4,
                        fill=(255, 255, 255, 50))
    p = int((bar_x1-bar_x0) * idx / (total - 1)) if total > 1 else bar_x1 - bar_x0
    d.rounded_rectangle([bar_x0, bar_y0, bar_x0+p, bar_y1],
                        radius=4, fill=pal["accent"])

    # 라벨
    d.text((60, 150), f"오늘의 혜택  ·  {idx}/{total-1}",
           font=font(32, bold=False), fill=MUTED)

    # 아이콘
    icon = icon_for(category, size=260, color=(*pal["accent"], 230))
    ix = W//2 - 130
    iy = SAFE_TOP + 40
    bg.alpha_composite(icon, (ix, iy))

    # 본문 텍스트
    fs = 78 if len(text) < 20 else (66 if len(text) < 40 else 58)
    f = font(fs, bold=True)
    lines = wrap(d, text, f, CONTENT_W)
    line_h = int(fs * 1.35)
    total_h = line_h * len(lines)
    # 텍스트를 아이콘 아래, 세이프존 안에 배치
    y0 = iy + 300
    y = y0
    # 강조 바
    d.rectangle([W//2 - 40, y - 40, W//2 + 40, y - 32], fill=pal["accent"])
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((W-tw)//2 + 3, y + 3), ln, font=f, fill=(0, 0, 0, 200))
        d.text(((W-tw)//2, y), ln, font=f, fill=WHITE)
        y += line_h

    # 서브 텍스트 (출처/안내)
    if sub:
        sf = font(30, bold=False)
        sub_lines = wrap(d, sub, sf, CONTENT_W)
        sy = SAFE_BOTTOM + 20
        for i, ln in enumerate(sub_lines[:2]):
            tw = d.textlength(ln, font=sf)
            d.text(((W-tw)//2, sy + i*42), ln, font=sf, fill=MUTED)

    bg.convert("RGB").save(path, quality=95)


# ─────────────────────────── 전체 렌더 ────────────────────────────
def render_reel(script, out_path, work_dir):
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    category = _guess_category(script)
    scenes = [
        {"text": script["hook"], "sub": script.get("source_label", ""), "kind": "hook"},
        *[{"text": b, "sub": "", "kind": "body"} for b in script["body"]],
        {"text": script["cta"],
         "sub": "🔗 출처는 프로필 링크 / 원문 확인", "kind": "cta"},
    ]
    total = len(scenes) + 1  # 인트로 포함

    # 인트로 음성/영상
    intro_png = work_dir / "intro.png"
    draw_intro(intro_png, PALETTE[0]["accent"])
    intro_dur = 0.75
    intro_clip = ImageClip(str(intro_png)).with_duration(intro_dur)

    # 장면별 음성/이미지
    scene_clips = []
    voice_clips = []
    cursor = intro_dur
    for i, sc in enumerate(scenes):
        mp3 = work_dir / f"voice_{i}.mp3"
        synthesize(sc["text"], mp3)
        vc = AudioFileClip(str(mp3))
        dur = vc.duration + 0.4
        voice_clips.append((cursor, vc))

        card_png = work_dir / f"card_{i}.png"
        # 슬라이드 인덱스: 훅=1, body=2,3,4, cta=5
        draw_card(sc["text"], i+1, total,
                  sc.get("sub", ""), category, card_png)
        clip = (ImageClip(str(card_png))
                .with_duration(dur)
                .with_start(cursor))
        scene_clips.append(clip)
        cursor += dur

    total_dur = cursor

    bg_black = ImageClip(str(_solid_bg(work_dir / "bg_black.png", (10, 15, 30)))).with_duration(total_dur)
    video = CompositeVideoClip([bg_black, intro_clip, *scene_clips],
                               size=(W, H))

    # 음성 합성
    from moviepy import concatenate_audioclips
    # 도입부 0.5초 정적
    silence = AudioArrayClip(
        np.zeros((int(0.5 * 44100), 2), dtype=np.float32), fps=44100,
    ).with_start(0)
    # 음성 클립 start 설정
    placed = []
    for start, vc in voice_clips:
        placed.append(vc.with_start(start))
    narration_track = CompositeAudioClip([silence, *placed])

    # BGM
    bgm_wav = work_dir / "bgm.wav"
    make_bgm(total_dur + 1.0, bgm_wav)
    bgm_audio = (AudioFileClip(str(bgm_wav))
                 .subclipped(0, total_dur)
                 .with_volume_scaled(0.45))

    mixed = CompositeAudioClip([narration_track, bgm_audio])
    video = video.with_audio(mixed)

    video.write_videofile(
        str(out_path), fps=FPS, codec="libx264", audio_codec="aac",
        audio_fps=48000, audio_bitrate="128k", preset="medium",
        bitrate="3500k", threads=4,
        ffmpeg_params=[
            "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0",
            "-movflags", "+faststart",
        ],
        logger=None,
    )
    video.close()
    for _, vc in voice_clips:
        vc.close()
    bgm_audio.close()
    return out_path


def _guess_category(script):
    text = " ".join([script.get("hook", "")] + script.get("body", []) +
                    [script.get("cta", "")] + script.get("hashtags", []))
    if any(k in text for k in ["육아", "출산", "부모", "자녀", "보육", "아동"]):
        return "육아"
    if any(k in text for k in ["부동산", "전세", "월세", "주택", "임대"]):
        return "부동산"
    if any(k in text for k in ["세금", "세액", "연말정산", "감면"]):
        return "세금"
    if any(k in text for k in ["소상공인", "자영업", "창업", "사업자"]):
        return "소상공인"
    if any(k in text for k in ["복지", "연금", "기초", "노인", "장애"]):
        return "복지"
    return "일반정책"


def _solid_bg(path, color):
    Image.new("RGB", (W, H), color).save(path)
    return path


if __name__ == "__main__":
    sample = {
        "hook": "8월부터 육아휴직 급여 최대 250만 원",
        "body": [
            "기존 월 최대 150만 원에서 250만 원으로 인상.",
            "첫 3개월간 적용되고 고용보험 가입자가 대상.",
            "관할 고용센터나 고용24에서 온라인 신청 가능.",
        ],
        "cta": "자세한 내용은 고용노동부 누리집에서 확인",
        "hashtags": ["#육아휴직", "#출산혜택", "#고용노동부", "#정부지원"],
        "source_label": "고용노동부 보도자료",
    }
    out = Path("output/sample_v3.mp4")
    render_reel(sample, out, Path("output/_work_v3"))
    print("✅", out)

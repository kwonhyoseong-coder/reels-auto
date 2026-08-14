"""
릴스 렌더러 v2 — 슬라이드/일러스트형
- 5개 장면: ① 후킹 ②③④ 본문(3문장) ⑤ CTA
- 장면마다 배경색 포인트가 살짝 다른 카드
- 상단 진행바 + 큰 자막 (세이프존 준수)
- 부드러운 페이드 전환
- TTS 위에 깔리는 로열티 프리 BGM (numpy로 합성)
"""
from __future__ import annotations

import asyncio
import math
import os
import re
import tempfile
import wave
from pathlib import Path

import edge_tts
import numpy as np
from moviepy import (
    AudioArrayClip,
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30

# 인스타 UI 대응 세이프존 (위/아래 22%)
SAFE_TOP = int(H * 0.22)
SAFE_BOTTOM = int(H * 0.78)
CONTENT_W = int(W * 0.86)

FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_REG = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
FONT_EXTRA = "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf"

# 5개 슬라이드 컬러 팔레트 (슬레이트 베이스에 포인트 컬러)
PALETTE = [
    {"bg": (15, 23, 42), "accent": (250, 204, 21)},    # 후킹 — 옐로
    {"bg": (30, 41, 59), "accent": (56, 189, 248)},     # 본문1 — 스카이
    {"bg": (30, 41, 59), "accent": (52, 211, 153)},     # 본문2 — 에메랄드
    {"bg": (30, 41, 59), "accent": (244, 114, 182)},    # 본문3 — 핑크
    {"bg": (15, 23, 42), "accent": (250, 204, 21)},    # CTA — 옐로
]
WHITE = (248, 250, 252)
MUTED = (148, 163, 184)


# ─────────────────────────── TTS ────────────────────────────

async def _synth(text: str, out_mp3: Path):
    # SunHi: 차분한 여성 / InJoon: 남성
    communicate = edge_tts.Communicate(text, voice="ko-KR-SunHiNeural", rate="+5%")
    await communicate.save(str(out_mp3))


def synthesize(text: str, out_mp3: Path) -> Path:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth(text, out_mp3))
    return out_mp3


# ─────────────────────────── BGM ────────────────────────────

def make_bgm(duration: float, out_wav: Path, sample_rate: int = 44100) -> Path:
    """
    부드러운 로열티 프리 배경음악(앰비언트 패드 + 약한 비트).
    어떤 외부 파일도 다운로드하지 않고 numpy로 합성한다.
    볼륨은 TTS를 해치지 않게 작게.
    """
    n = int(duration * sample_rate)
    t = np.linspace(0, duration, n, endpoint=False)

    # 다중 사인파 패드 (C major 7 코드: C-E-G-B)
    freqs = [130.81, 164.81, 196.00, 246.94]
    pad = np.zeros_like(t)
    for i, f in enumerate(freqs):
        # 느린 변조
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * (0.1 + 0.03 * i) * t)
        pad += 0.15 * lfo * np.sin(2 * np.pi * f * t + i * 0.7)
    pad /= len(freqs)

    # soft kick (4박자 — 90 BPM)
    beat_interval = 60 / 90
    kick = np.zeros_like(t)
    n_beats = int(duration / beat_interval) + 1
    for b in range(n_beats):
        start = int(b * beat_interval * sample_rate)
        length = int(0.18 * sample_rate)
        end = min(start + length, n)
        if start >= n:
            break
        x = np.linspace(0, 1, end - start, endpoint=False)
        # 피치가 빠르게 떨어지는 킥
        env = np.exp(-x * 18)
        wave_ = np.sin(2 * np.pi * (90 - 40 * x) * x) * env
        kick[start:end] += wave_ * 0.25

    # hi-hat-ish noise (every half beat)
    rng = np.random.default_rng(42)
    hat = np.zeros_like(t)
    for b in range(2 * n_beats):
        start = int(b * (beat_interval / 2) * sample_rate)
        length = int(0.04 * sample_rate)
        end = min(start + length, n)
        if start >= n:
            break
        x = np.linspace(0, 1, end - start, endpoint=False)
        env = np.exp(-x * 60)
        hat[start:end] += rng.standard_normal(end - start) * env * 0.04

    audio = pad + kick + hat
    # Fade in/out
    fade = int(0.8 * sample_rate)
    audio[:fade] *= np.linspace(0, 1, fade)
    audio[-fade:] *= np.linspace(1, 0, fade)
    audio = np.tanh(audio * 0.9) * 0.9  # soft clip
    audio = audio / max(1e-6, np.max(np.abs(audio))) * 0.28  # BGM을 낮게

    # 스테레오
    stereo = np.stack([audio, audio], axis=1)
    arr = (stereo * 32767).astype(np.int16)

    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(arr.tobytes())
    return out_wav


# ─────────────────────────── 카드/자막 렌더 ────────────────────────────

def _font(size: int, bold: bool = True, extra: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_EXTRA if extra else (FONT_BOLD if bold else FONT_REG)
    return ImageFont.truetype(path, size)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
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


def _vertical_gradient(w: int, h: int, top: tuple[int, int, int],
                      bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (w, h), top)
    px = img.load()
    for y in range(h):
        r = y / h
        col = tuple(int(top[i] * (1 - r) + bottom[i] * r) for i in range(3))
        for x in range(w):
            px[x, y] = col
    return img


def _decor_shapes(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int],
                  seed: int = 0):
    """심심하지 않게 반투명 원/라인 장식."""
    rng = np.random.default_rng(seed)
    for _ in range(6):
        r = int(rng.integers(60, 220))
        x = int(rng.integers(-50, W - 100))
        y = int(rng.integers(SAFE_TOP - 60, SAFE_BOTTOM + 60))
        alpha_fill = (accent[0], accent[1], accent[2], 28)
        # Pillow Draw는 RGBA 직접 안 되니 마스크 레이어 위에 그려야 하는데
        # 간단히 outline으로 처리
        draw.ellipse([x, y, x + r * 2, y + r * 2],
                     outline=(*accent, 80), width=3)
    # 사선 라인
    for _ in range(3):
        y = int(rng.integers(SAFE_TOP + 60, SAFE_BOTTOM - 60))
        draw.line([(60, y), (W - 60, y + int(rng.integers(-80, 80)))],
                  fill=(*accent, 70), width=2)


def render_card(text: str, idx: int, total: int, total_scene_label: str,
                sub: str, out_png: Path):
    pal = PALETTE[idx % len(PALETTE)]
    bg = _vertical_gradient(W, H, pal["bg"], (5, 10, 24))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    _decor_shapes(od, pal["accent"], seed=idx)
    bg = Image.alpha_composite(bg.convert("RGBA"), overlay)

    draw = ImageDraw.Draw(bg)

    # 상단 진행 바
    bar_x0, bar_y0 = 60, 110
    bar_x1, bar_y1 = W - 60, 118
    draw.rounded_rectangle([bar_x0, bar_y0, bar_x1, bar_y1],
                           radius=4, fill=(255, 255, 255, 50))
    progress_w = int((bar_x1 - bar_x0) * (idx + 1) / total)
    draw.rounded_rectangle([bar_x0, bar_y0, bar_x0 + progress_w, bar_y1],
                           radius=4, fill=pal["accent"])

    # 상단 라벨
    draw.text((60, 150), total_scene_label,
              font=_font(34, bold=False), fill=MUTED)

    # 본문 큰 자막
    font_size = 86 if len(text) < 35 else 74
    if len(text) >= 60:
        font_size = 64
    f = _font(font_size, bold=True)
    lines = _wrap(draw, text, f, CONTENT_W)
    line_h = int(font_size * 1.35)
    total_h = line_h * len(lines)
    y = (SAFE_TOP + SAFE_BOTTOM) // 2 - total_h // 2
    for i, ln in enumerate(lines):
        # 그림자
        draw.text((W // 2 - draw.textlength(ln, font=f) // 2 + 3, y + i * line_h + 3),
                  ln, font=f, fill=(0, 0, 0, 220))
        # 본문
        draw.text((W // 2 - draw.textlength(ln, font=f) // 2, y + i * line_h),
                  ln, font=f, fill=WHITE)

    # 포인트 바
    bar_w = 80
    draw.rectangle([(W // 2 - bar_w // 2, y - 40),
                    (W // 2 + bar_w // 2, y - 32)], fill=pal["accent"])

    # 하단 서브 텍스트 (출처 or 안내)
    if sub:
        sf = _font(30, bold=False)
        lines2 = _wrap(draw, sub, sf, CONTENT_W)
        sy = SAFE_BOTTOM + 20
        for i, ln in enumerate(lines2[:2]):
            draw.text((W // 2 - draw.textlength(ln, font=sf) // 2, sy + i * 40),
                      ln, font=sf, fill=MUTED)

    bg.convert("RGB").save(out_png, quality=95)


# ─────────────────────────── 전체 합성 ────────────────────────────

def render_reel(script: dict, out_path: Path, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    scenes = [
        {"text": script["hook"], "sub": script.get("source_label", "정부 공식 발표")},
        *[{"text": b, "sub": ""} for b in script["body"]],
        {"text": script["cta"], "sub": "🔗 출처는 프로필 링크 / 원문 확인"},
    ]
    total = len(scenes)

    # 음성 (장면별로 나눠 녹음 → 각 장면 길이를 그 음성에 맞춤)
    audio_clips = []
    scene_clips = []
    cursor = 0.0
    for i, sc in enumerate(scenes):
        mp3 = work_dir / f"voice_{i}.mp3"
        synthesize(sc["text"], mp3)
        ac = AudioFileClip(str(mp3))
        audio_clips.append(ac)
        dur = ac.duration + 0.5  # 장면 끝에 약간 여유

        card_png = work_dir / f"card_{i}.png"
        render_card(
            sc["text"], i, total,
            total_scene_label=f"오늘의 혜택  ·  {i + 1}/{total}",
            sub=sc.get("sub", ""),
            out_png=card_png,
        )
        clip = ImageClip(str(card_png)).with_duration(dur).with_start(cursor)
        # 장면 전환 페이드인
        clip = clip.with_effects([])  # simple
        scene_clips.append(clip)
        cursor += dur

    total_duration = cursor

    # 전체 화면
    bg_black = ImageClip(
        str(_solid_bg(work_dir / "bg_black.png", PALETTE[0]["bg"]))
    ).with_duration(total_duration)
    video = CompositeVideoClip([bg_black, *scene_clips], size=(W, H))

    # TTS를 시간 순서대로 이어붙이기
    from moviepy import concatenate_audioclips
    narration = concatenate_audioclips(audio_clips)

    # BGM
    bgm_wav = work_dir / "bgm.wav"
    make_bgm(total_duration + 1.0, bgm_wav)
    bgm_audio = AudioFileClip(str(bgm_wav)).subclipped(0, total_duration).with_volume_scaled(0.55)

    mixed = CompositeAudioClip([narration, bgm_audio])
    video = video.with_audio(mixed)

    # Instagram Reels 스펙
    video.write_videofile(
        str(out_path),
        fps=FPS,
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

    # 리소스 정리
    video.close()
    for c in audio_clips:
        c.close()
    bgm_audio.close()
    return out_path


def _solid_bg(path: Path, color: tuple[int, int, int]) -> Path:
    Image.new("RGB", (W, H), color).save(path)
    return path


if __name__ == "__main__":
    sample = {
        "hook": "8월부터 육아휴직 급여 최대 250만 원",
        "body": [
            "기존 150만 원에서 250만 원으로 인상됩니다.",
            "첫 3개월간 적용되고 고용보험 가입자가 대상.",
            "관할 고용센터나 고용24에서 온라인 신청 가능.",
        ],
        "cta": "자세한 내용은 고용노동부 누리집에서 확인하세요",
        "source_label": "고용노동부 보도자료",
    }
    out = Path("output/sample_v2.mp4")
    render_reel(sample, out, Path("output/_work_v2"))
    print("✅", out)

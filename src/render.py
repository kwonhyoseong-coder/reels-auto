"""
릴스 렌더러 v4 — 다양하고 풍성한 비주얼
- BREAKING 인트로
- 슬라이드마다 다른 레이아웃 (훅=빅타이틀, body=카드/리스트/스탯, CTA=액션박스)
- highlight 키워드 강조색 처리
- 슬라이드 전환 크로스페이드
- 장면별 사운드 팝
- 풍부한 BGM (bgm.py)
"""
from __future__ import annotations
import asyncio, math, os, wave
from pathlib import Path

import edge_tts
import numpy as np
from moviepy import (
    AudioArrayClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip,
    ImageClip, concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from bgm import make_bgm
from icons import icon_for

W, H = 1080, 1920
FPS = 30
SAFE_TOP, SAFE_BOTTOM = int(H*0.20), int(H*0.80)
CONTENT_W = int(W*0.86)

FONT_BOLD = "/usr/share/fonts/truetype/nanum/NanumSquareB.ttf"
FONT_REG  = "/usr/share/fonts/truetype/nanum/NanumSquareR.ttf"
FONT_EXTRA= "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf"

PALETTE = [
    {"bg": (12, 19, 35), "accent": (250, 204, 21)},   # hook - 옐로
    {"bg": (24, 33, 52), "accent": (56, 189, 248)},    # body1 - 스카이
    {"bg": (20, 35, 45), "accent": (52, 211, 153)},    # body2 - 에메랄드
    {"bg": (40, 25, 50), "accent": (244, 114, 182)},   # body3 - 핑크
    {"bg": (12, 19, 35), "accent": (250, 204, 21)},    # cta - 옐로
]
WHITE, MUTED, DARK = (248,250,252), (148,163,184), (8,12,24)


def fnt(size, bold=True):
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def wrap(draw, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur+" "+w).strip()
        if draw.textlength(test, font=f) <= maxw:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines


def gradient(top, bottom):
    img = Image.new("RGB", (W,H), top)
    px = img.load()
    for y in range(H):
        r = y/H
        c = tuple(int(top[i]*(1-r)+bottom[i]*r) for i in range(3))
        for x in range(W):
            px[x,y] = c
    return img.convert("RGBA")


def add_noise_dots(draw, accent, n=30, seed=0):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        x = int(rng.integers(40, W-40)); y = int(rng.integers(SAFE_TOP, SAFE_BOTTOM))
        r = int(rng.integers(2, 7))
        draw.ellipse([x-r,y-r,x+r,y+r], fill=(*accent, 40))


def draw_intro(path):
    bg = gradient((10,15,30), (2,6,18))
    d = ImageDraw.Draw(bg)
    # 레드 바
    d.rectangle([0, SAFE_TOP-80, W, SAFE_TOP-56], fill=(220,38,38))
    d.rectangle([0, SAFE_BOTTOM+56, W, SAFE_BOTTOM+80], fill=(220,38,38))
    # BIG
    f = fnt(160); t = "BREAKING"
    tw = d.textlength(t, font=f)
    d.text(((W-tw)//2, H//2-220), t, font=f, fill=(250,204,21))
    f2 = fnt(78); t2 = "정책 혜택 알림"
    tw2 = d.textlength(t2, font=f2)
    d.text(((W-tw2)//2, H//2-20), t2, font=f2, fill=WHITE)
    # 깜빡이는 점
    cx, cy, r = W//2, H//2+140, 24
    d.ellipse([cx-r,cy-r,cx+r,cy+r], fill=(220,38,38))
    bg.convert("RGB").save(path, quality=95)


# ── 각 슬라이드 레이아웃 ──────────────────────────
def draw_hook_slide(text, sub, category, path):
    pal = PALETTE[0]
    bg = gradient(pal["bg"], (4,8,18))
    overlay = Image.new("RGBA",(W,H),(0,0,0,0)); od = ImageDraw.Draw(overlay)
    od.ellipse([W-260, 100, W+80, 440], outline=(*pal["accent"],80), width=5)
    od.ellipse([-80, SAFE_BOTTOM-200, 220, SAFE_BOTTOM+200], outline=(*pal["accent"],60), width=4)
    bg = Image.alpha_composite(bg, overlay)
    d = ImageDraw.Draw(bg)
    add_noise_dots(d, pal["accent"], 25, seed=1)

    # 상단 라벨
    d.text((60, 140), "TODAY'S PICK", font=fnt(30, False), fill=MUTED)
    d.rectangle([60, 185, 180, 192], fill=pal["accent"])

    # 아이콘
    ic = icon_for(category, 200, (*pal["accent"],230))
    bg.alpha_composite(ic, (W//2-100, SAFE_TOP+40))

    # 빅 타이틀
    fs = 86 if len(text)<20 else (70 if len(text)<40 else 58)
    f = fnt(fs)
    lines = wrap(d, text, f, CONTENT_W)
    y = SAFE_TOP + 300
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((W-tw)//2+3, y+3), ln, font=f, fill=(0,0,0,200))
        d.text(((W-tw)//2, y), ln, font=f, fill=WHITE)
        y += int(fs*1.3)

    # 하단 바 + sub
    d.rectangle([60, SAFE_BOTTOM+10, W-60, SAFE_BOTTOM+16], fill=(*pal["accent"], 180))
    if sub:
        sf = fnt(28, False)
        tw = d.textlength(sub, font=sf)
        d.text(((W-tw)//2, SAFE_BOTTOM+40), sub, font=sf, fill=MUTED)
    bg.convert("RGB").save(path, quality=95)


def draw_stat_slide(text, highlight, idx, total, category, path):
    """큰 숫자/키워드 강조형 슬라이드."""
    pal = PALETTE[(idx-1) % len(PALETTE)]
    bg = gradient(pal["bg"], (6,10,22))
    overlay = Image.new("RGBA",(W,H),(0,0,0,0)); od = ImageDraw.Draw(overlay)
    # 모서리 장식
    for cx, cy, r in [(W-120, SAFE_TOP+120, 180), (120, SAFE_BOTTOM-140, 140)]:
        od.ellipse([cx-r,cy-r,cx+r,cy+r], outline=(*pal["accent"], 70), width=4)
    bg = Image.alpha_composite(bg, overlay)
    d = ImageDraw.Draw(bg)
    add_noise_dots(d, pal["accent"], 18, seed=idx+3)

    # 상단 진행 바
    d.rounded_rectangle([60,110,W-60,118], radius=4, fill=(255,255,255,50))
    p = int((W-120)*idx/(total-1)) if total>1 else W-120
    d.rounded_rectangle([60,110,60+p,118], radius=4, fill=pal["accent"])
    d.text((60,140), f"오늘의 혜택  ·  {idx}/{total-1}", font=fnt(30, False), fill=MUTED)

    # 핵심 하이라이트 크게
    hl = (highlight or "").strip()
    if hl and len(hl) < 25:
        hf = fnt(130 if len(hl)<=6 else (96 if len(hl)<=12 else 72))
        tw = d.textlength(hl, font=hf)
        hy = SAFE_TOP + 80
        d.text(((W-tw)//2, hy), hl, font=hf, fill=pal["accent"])
        # 밑줄
        d.rectangle([W//2-tw//2, hy+int(130*0.9), W//2+tw//2, hy+int(130*0.9)+6], fill=pal["accent"])
        body_y = hy + 220
    else:
        body_y = SAFE_TOP + 200

    # 본문
    f = fnt(58)
    # highlight 제거한 나머지 텍스트
    rest = text
    if hl:
        rest = text.replace(hl, "").strip(" :.,")
    if not rest: rest = text
    lines = wrap(d, rest, f, CONTENT_W)
    for i, ln in enumerate(lines[:4]):
        tw = d.textlength(ln, font=f)
        d.text(((W-tw)//2+2, body_y+i*82+2), ln, font=f, fill=(0,0,0,200))
        d.text(((W-tw)//2, body_y+i*82), ln, font=f, fill=WHITE)

    bg.convert("RGB").save(path, quality=95)


def draw_list_slide(text, highlight, idx, total, category, path):
    """리스트/체크형 슬라이드."""
    pal = PALETTE[(idx-1) % len(PALETTE)]
    bg = gradient(pal["bg"], (6,10,22))
    d = ImageDraw.Draw(bg)
    # 진행 바
    d.rounded_rectangle([60,110,W-60,118], radius=4, fill=(255,255,255,50))
    p = int((W-120)*idx/(total-1)) if total>1 else W-120
    d.rounded_rectangle([60,110,60+p,118], radius=4, fill=pal["accent"])
    d.text((60,140), f"오늘의 혜택  ·  {idx}/{total-1}", font=fnt(30, False), fill=MUTED)

    # 아이콘
    ic = icon_for(category, 160, (*pal["accent"], 230))
    bg.alpha_composite(ic, (W//2-80, SAFE_TOP+20))

    # 본문 - 체크 리스트 스타일
    f = fnt(56)
    lines = wrap(d, text, f, CONTENT_W-100)
    y = SAFE_TOP + 240
    for i, ln in enumerate(lines[:4]):
        # 체크 원
        cy = y + i*92 + 30
        d.ellipse([90, cy, 140, cy+50], outline=pal["accent"], width=5)
        d.line([104, cy+25, 118, cy+38], fill=pal["accent"], width=6)
        d.line([118, cy+38, 132, cy+15], fill=pal["accent"], width=6)
        # 텍스트 (highlight 강조)
        _draw_with_highlight(d, ln, 165, cy-15, f, pal["accent"], highlight)
    bg.convert("RGB").save(path, quality=95)


def draw_cta_slide(text, sub, path):
    pal = PALETTE[4]
    bg = gradient(pal["bg"], (4,8,18))
    overlay = Image.new("RGBA",(W,H),(0,0,0,0)); od = ImageDraw.Draw(overlay)
    # 사선
    for y in range(SAFE_TOP, SAFE_BOTTOM, 80):
        od.line([(0, y), (W, y-200)], fill=(*pal["accent"], 20), width=2)
    bg = Image.alpha_composite(bg, overlay)
    d = ImageDraw.Draw(bg)
    add_noise_dots(d, pal["accent"], 25, seed=99)

    # 라벨
    d.text((60, 140), "지금 확인하세요", font=fnt(30, False), fill=MUTED)
    d.rectangle([60, 185, 200, 193], fill=pal["accent"])

    # 큰 화살표/체크
    cx, cy = W//2, SAFE_TOP + 200
    d.ellipse([cx-90, cy-90, cx+90, cy+90], outline=pal["accent"], width=8)
    d.line([cx-40, cy, cx-10, cy+35], fill=pal["accent"], width=10)
    d.line([cx-10, cy+35, cx+50, cy-30], fill=pal["accent"], width=10)

    # CTA 텍스트
    fs = 80 if len(text)<20 else (66 if len(text)<40 else 54)
    f = fnt(fs)
    lines = wrap(d, text, f, CONTENT_W)
    y = cy + 160
    for ln in lines:
        tw = d.textlength(ln, font=f)
        d.text(((W-tw)//2+3, y+3), ln, font=f, fill=(0,0,0,200))
        d.text(((W-tw)//2, y), ln, font=f, fill=WHITE)
        y += int(fs*1.3)

    # 액션 박스
    if sub:
        sf = fnt(30, False)
        sub_lines = wrap(d, sub, sf, CONTENT_W-120)
        box_y = SAFE_BOTTOM - 40 - len(sub_lines)*42
        d.rounded_rectangle([80, box_y-20, W-80, SAFE_BOTTOM+20],
                            radius=16, outline=pal["accent"], width=3)
        for i, ln in enumerate(sub_lines[:2]):
            tw = d.textlength(ln, font=sf)
            d.text(((W-tw)//2, box_y+i*42), ln, font=sf, fill=pal["accent"])
    bg.convert("RGB").save(path, quality=95)


def _draw_with_highlight(d, text, x, y, f, accent, hl=None):
    """텍스트 내에서 hl 키워드는 강조색으로 그린다."""
    if not hl or hl not in text:
        d.text((x, y), text, font=f, fill=WHITE)
        return
    parts = text.split(hl, 1)
    cur_x = x
    for i, part in enumerate(parts):
        if part:
            d.text((cur_x, y), part, font=f, fill=WHITE)
            cur_x += d.textlength(part, font=f)
        if i < len(parts)-1:
            d.text((cur_x, y), hl, font=f, fill=accent)
            cur_x += d.textlength(hl, font=f)


# ── TTS/사운드 ──────────────────────────
async def _synth(text, out):
    await edge_tts.Communicate(text, voice="ko-KR-SunHiNeural", rate="+5%").save(str(out))

def synthesize(text, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_synth(text, out))

def make_ping(duration=0.15, sr=44100):
    n = int(duration*sr)
    t = np.arange(n)/sr
    freq = 880
    sig = np.sin(2*np.pi*freq*t) * np.exp(-t*12)
    stereo = np.stack([sig, sig], axis=1).astype(np.float32)
    return AudioArrayClip(stereo*0.25, fps=sr)


# ── 메인 렌더 ──────────────────────────
def render_reel(script, out_path, work_dir):
    work_dir.mkdir(parents=True, exist_ok=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    category = _guess_cat(script)
    hl = script.get("highlight", ["", "", ""])
    while len(hl) < 3: hl.append("")

    body_scenes = list(zip(script["body"], hl))

    # 인트로
    intro_png = work_dir/"intro.png"; draw_intro(intro_png)
    intro_dur = 0.7
    intro = ImageClip(str(intro_png)).with_duration(intro_dur)

    # 장면 타입: hook→hook_slide, body1→stat, body2→list, body3→stat, cta→cta
    clips = [intro]
    voices = []
    pings = []
    cursor = intro_dur

    # hook
    hook_png = work_dir/"hook.png"
    draw_hook_slide(script["hook"], script.get("source_label",""), category, hook_png)
    hook_mp3 = work_dir/"voice_hook.mp3"
    synthesize(script["hook"], hook_mp3)
    hv = AudioFileClip(str(hook_mp3))
    hook_dur = hv.duration + 0.35
    clips.append(ImageClip(str(hook_png)).with_duration(hook_dur).with_start(cursor))
    voices.append((cursor, hv))
    pings.append((cursor + 0.05, make_ping()))
    cursor += hook_dur

    # body 3장
    for i, (text, h) in enumerate(body_scenes, 1):
        png = work_dir/f"body{i}.png"
        if i == 2:
            draw_list_slide(text, h, i, 5, category, png)
        else:
            draw_stat_slide(text, h, i, 5, category, png)
        mp3 = work_dir/f"voice_b{i}.mp3"
        synthesize(text, mp3)
        v = AudioFileClip(str(mp3))
        dur = v.duration + 0.35
        clips.append(ImageClip(str(png)).with_duration(dur).with_start(cursor))
        voices.append((cursor, v))
        pings.append((cursor + 0.05, make_ping()))
        cursor += dur

    # cta
    cta_png = work_dir/"cta.png"
    draw_cta_slide(script["cta"], "🔗 출처는 프로필 링크 / 원문 확인", cta_png)
    cta_mp3 = work_dir/"voice_cta.mp3"
    synthesize(script["cta"], cta_mp3)
    cv = AudioFileClip(str(cta_mp3))
    cta_dur = cv.duration + 0.5
    clips.append(ImageClip(str(cta_png)).with_duration(cta_dur).with_start(cursor))
    voices.append((cursor, cv))
    pings.append((cursor + 0.05, make_ping()))
    cursor += cta_dur

    total = cursor
    bg = ImageClip(str(_solid(work_dir/"bg.png", (10,15,30)))).with_duration(total)
    video = CompositeVideoClip([bg, *clips], size=(W,H))

    # 음성
    placed = [v.with_start(s) for s, v in voices]
    narration = CompositeAudioClip(placed)

    # ping 효과
    ping_clips = [p.with_start(s) for s, p in pings]

    # BGM
    bgm_wav = work_dir/"bgm.wav"
    make_bgm(total+1, bgm_wav)
    bgm = (AudioFileClip(str(bgm_wav)).subclipped(0, total)
           .with_volume_scaled(0.40))

    mixed = CompositeAudioClip([narration, bgm, *ping_clips])
    video = video.with_audio(mixed)

    video.write_videofile(
        str(out_path), fps=FPS, codec="libx264", audio_codec="aac",
        audio_fps=48000, audio_bitrate="128k", preset="medium",
        bitrate="3500k", threads=4,
        ffmpeg_params=["-pix_fmt","yuv420p","-profile:v","high","-level","4.0",
                       "-movflags","+faststart"],
        logger=None,
    )
    video.close()
    for _, v in voices: v.close()
    bgm.close()
    return out_path


def _guess_cat(script):
    text = " ".join([script.get("hook","")]+script.get("body",[])+
                    [script.get("cta","")]+script.get("hashtags",[]))
    if any(k in text for k in ["육아","출산","부모","자녀","보육","아동"]): return "육아"
    if any(k in text for k in ["부동산","전세","월세","주택","임대"]): return "부동산"
    if any(k in text for k in ["세금","세액","연말정산","감면"]): return "세금"
    if any(k in text for k in ["소상공인","자영업","창업","사업자"]): return "소상공인"
    if any(k in text for k in ["복지","연금","기초","노인","장애"]): return "복지"
    return "일반정책"


def _solid(path, color):
    Image.new("RGB",(W,H),color).save(path); return path


if __name__ == "__main__":
    sample = {
        "hook": "8월부터 육아휴직 급여 최대 250만 원",
        "body": [
            "기존 월 최대 150만 원에서 250만 원으로 100만 원 인상됩니다.",
            "생후 18개월 이내 자녀를 둔 고용보험 가입자가 대상입니다.",
            "관할 고용센터나 고용24 누리집에서 온라인으로 신청하세요.",
        ],
        "highlight": ["250만 원", "고용보험 가입자", "고용24"],
        "cta": "신청은 고용24 누리집에서",
        "hashtags": ["#육아휴직","#출산혜택","#고용노동부","#정부지원"],
        "source_label": "고용노동부 보도자료",
    }
    out = Path("output/sample_v4.mp4")
    render_reel(sample, out, Path("output/_work_v4"))
    print("✅", out)

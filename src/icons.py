"""
릴스 슬라이드에 넣을 벡터 아이콘 (Pillow에 그리기).
각 아이콘 함수는 RGBA Image를 반환한다.
색은 인자로 받아 슬라이드 팔레트와 맞춘다.
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw


def _new(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def icon_wallet(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """지폐/지갑 — 지원금."""
    img, d = _new(size)
    w = h = size
    # 지폐
    d.rounded_rectangle([w*0.1, h*0.25, w*0.9, h*0.8], radius=20,
                        outline=color, width=8)
    d.rounded_rectangle([w*0.2, h*0.4, w*0.8, h*0.65], radius=12,
                        outline=color, width=6)
    # 원(코인)
    cx, cy, r = int(w*0.5), int(h*0.5), int(min(w,h)*0.09)
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=color, width=6)
    return img


def icon_house(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """집 — 부동산."""
    img, d = _new(size)
    w = h = size
    # 지붕
    d.polygon([(w*0.15, h*0.5), (w*0.5, h*0.18), (w*0.85, h*0.5)],
              outline=color, width=8)
    # 집 벽
    d.rounded_rectangle([w*0.25, h*0.48, w*0.75, h*0.82], radius=10,
                        outline=color, width=8)
    # 문
    d.rounded_rectangle([w*0.43, h*0.6, w*0.57, h*0.82], radius=6,
                        outline=color, width=6)
    return img


def icon_family(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """가족 — 육아/가족."""
    img, d = _new(size)
    w = h = size
    # 어른
    d.ellipse([w*0.25, h*0.22, w*0.45, h*0.42], outline=color, width=7)
    d.arc([w*0.22, h*0.42, w*0.48, h*0.85], 200, 340, fill=color, width=7)
    # 아이
    d.ellipse([w*0.5, h*0.35, w*0.68, h*0.53], outline=color, width=7)
    d.arc([w*0.48, h*0.53, w*0.72, h*0.85], 200, 340, fill=color, width=7)
    # 하트
    cx, cy = int(w*0.75), int(h*0.28)
    r = int(min(w,h)*0.04)
    d.ellipse([cx-r*2, cy-r, cx, cy+r], outline=color, width=6)
    d.ellipse([cx, cy-r, cx+r*2, cy+r], outline=color, width=6)
    d.polygon([(cx-r*2, cy+r//2), (cx+r*2, cy+r//2), (cx, cy+r*2)],
              outline=color, width=6)
    return img


def icon_document(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """문서 — 일반 정책."""
    img, d = _new(size)
    w = h = size
    d.rounded_rectangle([w*0.25, h*0.15, w*0.75, h*0.85], radius=10,
                        outline=color, width=8)
    # 접힌 모서리
    d.polygon([(w*0.6, h*0.15), (w*0.75, h*0.15), (w*0.75, h*0.3)],
              outline=color, width=6)
    # 줄
    for i, y in enumerate([0.42, 0.54, 0.66]):
        x_end = 0.68 if i < 2 else 0.55
        d.line([(w*0.33, h*y), (w*x_end, h*y)], fill=color, width=6)
    return img


def icon_percent(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """% — 세금/할인."""
    img, d = _new(size)
    w = h = size
    # 두 원
    d.ellipse([w*0.2, h*0.2, w*0.4, h*0.4], outline=color, width=8)
    d.ellipse([w*0.6, h*0.6, w*0.8, h*0.8], outline=color, width=8)
    # 대각선
    d.line([(w*0.78, h*0.22), (w*0.22, h*0.78)], fill=color, width=10)
    return img


def icon_bell(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """벨 — 알림/뉴스."""
    img, d = _new(size)
    w = h = size
    # 종 모양
    d.arc([w*0.22, h*0.2, w*0.78, h*0.78], 200, 340, fill=color, width=8)
    d.line([(w*0.22, h*0.7), (w*0.78, h*0.7)], fill=color, width=8)
    d.rounded_rectangle([w*0.3, h*0.75, w*0.7, h*0.82], radius=4,
                        outline=color, width=6)
    # 클래퍼
    d.ellipse([w*0.43, h*0.82, w*0.57, h*0.88], outline=color, width=6)
    return img


def icon_heart(size: int = 320, color=(255, 255, 255, 220)) -> Image.Image:
    """하트 — 복지."""
    img, d = _new(size)
    w = h = size
    cx, cy = w//2, int(h*0.42)
    r = int(min(w,h)*0.13)
    d.ellipse([cx-r*2, cy-r, cx, cy+r], outline=color, width=8)
    d.ellipse([cx, cy-r, cx+r*2, cy+r], outline=color, width=8)
    d.polygon([(cx-r*2, cy+r//2), (cx+r*2, cy+r//2), (cx, cy+r*2)],
              outline=color, width=8)
    return img


def icon_for(category: str, size: int = 320,
             color=(255, 255, 255, 220)) -> Image.Image:
    mapping = {
        "육아": icon_family,
        "부동산": icon_house,
        "세금": icon_percent,
        "소상공인": icon_wallet,
        "복지": icon_heart,
        "일반정책": icon_document,
    }
    fn = mapping.get(category, icon_bell)
    return fn(size=size, color=color)

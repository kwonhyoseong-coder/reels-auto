"""
전체 파이프라인 실행기
사용법:
  python src/main.py --test      # 샘플 대본으로 영상만 렌더 (업로드X)
  python src/main.py              # 수집 → 생성 → 렌더 → 발행
  python src/main.py --dry-run    # 수집+대본 생성 후 영상 로컬 저장 (발행X)
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

from collect import fetch_candidates
from script import generate_script
from render import render_reel
from publish import publish_reel, build_caption

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output"


def run(dry_run: bool, test: bool):
    if test:
        sample = {
            "hook": "8월부터 육아휴직 급여가 최대 250만 원으로 오릅니다",
            "body": [
                "기존 월 최대 150만 원에서 250만 원으로 인상됩니다.",
                "첫 3개월간 적용되며, 고용보험 가입자면 신청할 수 있습니다.",
                "관할 고용센터나 고용24에서 온라인 신청 가능합니다.",
            ],
            "cta": "자세한 내용은 고용노동부 공식 누리집에서 확인하세요",
            "hashtags": ["#육아휴직", "#출산혜택", "#고용노동부", "#정부지원"],
            "source_label": "고용노동부 보도자료 2026.08.01",
            "source_url": "https://www.moel.go.kr",
        }
        out = OUT / f"test_{datetime.now():%Y%m%d_%H%M}.mp4"
        render_reel(sample, out, OUT / "_work")
        print("✅ 샘플 영상:", out)
        return

    print("① RSS 수집 중...")
    candidates = fetch_candidates()
    if not candidates:
        print("후보가 없습니다. RSS_FEEDS를 확인하세요.")
        sys.exit(1)
    print(f"  {len(candidates)}개 후보 발견. 첫 번째 기사 선택:")
    art = candidates[0]
    print("  -", art["title"])

    print("② 대본 생성 중...")
    script = generate_script(art)
    for k, v in script.items():
        print(f"   {k}: {v}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUT / f"reel_{stamp}.mp4"

    print("③ 영상 렌더링 중...")
    render_reel(script, out, OUT / f"_work_{stamp}")
    print("  ✅", out)

    if dry_run:
        print("--dry-run: 발행 건너뜀")
        return

    print("④ 인스타 발행 중...")
    caption = build_caption(script)
    publish_reel(out, caption=caption, key=out.name)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--test", action="store_true")
    args = p.parse_args()
    run(dry_run=args.dry_run, test=args.test)

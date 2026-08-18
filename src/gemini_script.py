"""
Gemini API로 릴스 대본 생성 (무료 티어).

Google은 모델 이름을 자주 바꾸고 신규 계정은 구 모델을 막기 때문에,
사용 가능한 모델 목록을 조회해서 가장 최신 Flash 계열 모델을 자동 선택한다.
- API 키: https://aistudio.google.com/apikey
- 반환: script dict (hook, body[], cta, hashtags[], source_label, source_url)
"""
import json
import os
import re
import sys
from pathlib import Path

import requests

API_KEY = os.getenv("GEMINI_API_KEY", "")
# 강제로 특정 모델을 쓰고 싶으면 환경변수로 지정. 없으면 자동 탐색.
FORCED_MODEL = os.getenv("GEMINI_MODEL", "")
API_BASE = "https://generativelanguage.googleapis.com/v1beta"

from prompt import SYSTEM_PROMPT


def _call_gemini(model: str, body: dict, *, attempts: int = 3) -> dict:
    """Gemini API 호출. 500/503/429는 지수 백오프로 재시도."""
    import time as _time
    url = f"{API_BASE}/models/{model}:generateContent"
    last_err = None
    for i in range(attempts):
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": API_KEY,
                         "Content-Type": "application/json"},
                json=body,
                timeout=90,
            )
        except requests.RequestException as e:
            last_err = f"network: {e}"
            _time.sleep(2 ** i)
            continue
        if r.status_code == 200:
            return r.json()
        # 500/503/429는 재시도
        if r.status_code in (429, 500, 503, 504):
            print(f"   ⚠ {model}: HTTP {r.status_code}, {2**(i+1)}초 후 재시도...",
                  file=sys.stderr)
            _time.sleep(2 ** (i + 1))
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            continue
        # 400/404 등은 바로 예외
        raise RuntimeError(f"Gemini API {r.status_code}: {r.text[:500]}")
    raise RuntimeError(f"Gemini 재시도 초과 ({model}): {last_err}")


def pick_model() -> str:
    """
    안정적인 최신 Flash 모델을 확정적으로 사용.
    - GEMINI_MODEL 환경변수가 있으면 그걸 첫 후보로
    - 실제 호출 테스트 후 살아있는 모델 반환
    """
    candidates = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    if FORCED_MODEL and FORCED_MODEL not in candidates:
        candidates.insert(0, FORCED_MODEL)

    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    probe = {
        "contents": [{"role": "user", "parts": [{"text": "OK"}]}],
        "generationConfig": {"maxOutputTokens": 1},
    }
    for m in candidates:
        try:
            data = _call_gemini(m, probe, attempts=1)
            if data.get("candidates"):
                print(f"   → Gemini 모델: {m}", file=sys.stderr)
                return m
        except Exception as e:
            print(f"   ⚠ {m}: {str(e)[:120]}", file=sys.stderr)

    raise RuntimeError(
        f"사용 가능한 Gemini 모델을 찾지 못했습니다. 시도: {candidates}."
    )


def generate_script(article: dict) -> dict:
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    # 모델 후보 순서대로 시도 (503이면 다음 모델로)
    model_order = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    if FORCED_MODEL:
        model_order.insert(0, FORCED_MODEL)

    user_prompt = _build_prompt(article)
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }

    last_err = None
    for model in model_order:
        try:
            data = _call_gemini(model, body, attempts=3)
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
            script = json.loads(text)
            script["source_url"] = article["url"]
            script["article_title"] = article["title"]
            script["source"] = article.get("source", "")
            print(f"   → 사용 모델: {model}", file=sys.stderr)
            return script
        except Exception as e:
            msg = str(e)
            # 404 (no longer available)는 다음 모델로
            if "404" in msg or "no longer" in msg.lower():
                print(f"   ⚠ {model} 사용 불가, 다음 모델로", file=sys.stderr)
                last_err = e
                continue
            # 503은 재시도했는데도 실패면 다음 모델
            if "503" in msg or "재시도 초과" in msg:
                print(f"   ⚠ {model} 과부하, 다음 모델로", file=sys.stderr)
                last_err = e
                continue
            # 그 외 에러는 그대로 던지기
            raise
    raise RuntimeError(f"모든 Gemini 모델 실패. 마지막 에러: {last_err}")


def _build_prompt(article: dict) -> str:
    return f"""\
아래 정부 보도자료를 25~35초 인스타 릴스 대본으로 만들어줘.

[원칙]
- body 3문장은 각각 40자 이내.
- 각 문장에 구체적 정보(숫자/금액/날짜/대상/방법) 중 하나 이상이 들어가야 함.
- "알아보세요/확인하세요/자세한 내용은" 같은 모호한 표현은 body에 넣지 말 것.
- highlight 배열은 각 body의 핵심 숫자/키워드(예: "250만원", "고용보험 가입자", "고용24").
- 원문에 없는 정보는 억지로 만들지 말 것.
- 해시태그는 핵심 단어 3~4개.

[출력]
JSON으로만. 필드: hook, body[3], highlight[3], cta, hashtags[4], source_label.

[제목] {article['title']}
[출처] {article['source']}
[발행일] {article.get('published','')}
[URL] {article['url']}
[원문]
{article.get('content') or article.get('summary','')[:2000]}
"""


def full_narration(script: dict) -> str:
    return " ".join([script["hook"], *script["body"], script["cta"]])


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_feed import build
    _, articles = build(per_source=5)
    if not articles:
        print("기사 없음")
        sys.exit(1)
    s = generate_script(articles[0])
    print(json.dumps(s, ensure_ascii=False, indent=2))

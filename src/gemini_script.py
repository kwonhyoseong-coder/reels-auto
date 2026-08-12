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

SYSTEM_PROMPT = """\
너는 대한민국 정부 정책·혜택 정보를 쉽게 설명하는 인스타 릴스 작가다.
규칙을 절대적으로 지켜라:
1. 오직 제공된 원문에 있는 사실만 사용. 추측·일반화 금지.
2. 투자·주식·코인·부동산 투자 수익 관련 조언은 일절 넣지 말 것.
3. 친절하고 담담한 톤. 과장 문장 금지.
4. 첫 문장은 혜택을 한 줄로 요약하는 후킹 문장(20자 내외).
5. 마지막에 신청 방법/공식 누리집 안내를 넣을 것.
6. JSON으로만 답하라. 다른 설명 절대 넣지 말 것.

JSON 스키마:
{
  "hook": "string",
  "body": ["string","string","string"],
  "cta": "string",
  "hashtags": ["#string","#string","#string","#string"],
  "source_label": "출처 표기 문구"
}
"""


def pick_model() -> str:
    """
    안정적인 최신 Flash 모델을 확정적으로 사용.
    - GEMINI_MODEL 환경변수가 있고 실제 호출이 되면 그걸 쓰고
    - 실패하면(404 등) 자동으로 3.6-flash → 3.5-flash → 3-flash로 폴백
    """
    # 2026년 8월 현재 GA된 안정 Flash 모델들 (신규 키 허용)
    candidates = [
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash",
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
            tr = requests.post(
                f"{API_BASE}/models/{m}:generateContent",
                headers={"x-goog-api-key": API_KEY,
                         "Content-Type": "application/json"},
                json=probe,
                timeout=15,
            )
            if tr.status_code == 200:
                print(f"   → Gemini 모델: {m}", file=sys.stderr)
                return m
            print(f"   ⚠ {m}: {tr.status_code} {tr.text[:150]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"   ⚠ {m}: {str(e)[:100]}", file=sys.stderr)

    raise RuntimeError(
        f"사용 가능한 Gemini 모델을 찾지 못했습니다. 시도: {candidates}. "
        f"API 키와 https://aistudio.google.com/apikey 에서 모델 가용성을 확인하세요."
    )


def generate_script(article: dict) -> dict:
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    model = pick_model()
    url = f"{API_BASE}/models/{model}:generateContent"

    user_prompt = f"""\
아래 정부 보도자료를 25~35초 인스타 릴스 대본으로 만들어줘.
- 본문은 3개 문장. 각 문장은 40자 이내로 짧게.
- 숫자·일자·금액은 원문 그대로 사용.
- 반드시 JSON으로만 답할 것.

[제목] {article['title']}
[출처] {article['source']}
[발행일] {article.get('published','')}
[URL] {article['url']}
[원문]
{article.get('content') or article.get('summary','')[:2000]}
"""

    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "responseMimeType": "application/json",
        },
    }
    r = requests.post(
        url,
        headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini API {r.status_code}: {r.text[:500]}")
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M)
    script = json.loads(text)
    script["source_url"] = article["url"]
    script["article_title"] = article["title"]
    script["source"] = article.get("source", "")
    return script


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

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
    사용 가능한 가장 좋은 Flash 모델 자동 선택.
    모델 목록을 받아온 뒤, 실제로 generateContent를 호출해보고
    404/400이 아닌 첫 모델을 쓴다. (신규 키는 2.5-flash를 막아서)
    """
    if FORCED_MODEL:
        return FORCED_MODEL

    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")

    r = requests.get(
        f"{API_BASE}/models",
        headers={"x-goog-api-key": API_KEY},
        timeout=15,
    )
    r.raise_for_status()
    data = r.json()

    candidates = []
    for m in data.get("models", []):
        name = m["name"].replace("models/", "")
        methods = m.get("supportedGenerationMethods", [])
        if "generateContent" not in methods:
            continue
        if "flash" not in name.lower():
            continue
        # 이미지/라이브/오디오 전용 모델 제외
        if any(x in name.lower() for x in ["image", "live", "tts", "audio", "embedding"]):
            continue
        candidates.append(name)

    # 선호도 순으로 정렬:
    # 1) 3.x flash (preview) — 신규 키에 가장 확실하게 열려있음
    # 2) 2.5-flash-lite
    # 3) 2.5-flash (신규 키는 막혀있을 수 있음)
    # 4) 2.0-flash
    def sort_key(n: str) -> tuple:
        score = 0
        low = n.lower()
        if low.startswith("gemini-3"):
            score += 100
        elif "2.5" in low:
            score += 50
        elif "2.0" in low:
            score += 30
        if "lite" in low:
            score -= 5  # 일단 flash 우선
        if "preview" in low:
            score += 2
        return (score, n)

    candidates.sort(key=sort_key, reverse=True)
    if not candidates:
        raise RuntimeError("사용 가능한 Flash 모델이 없습니다.")

    # 실제 호출 테스트: 1토큰만 요청해서 404/400이면 다음 모델로
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
                print(f"   → 자동 선택된 Gemini 모델: {m}", file=sys.stderr)
                return m
            else:
                print(f"   ⚠ {m}: {tr.status_code} {tr.text[:120]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"   ⚠ {m}: {str(e)[:100]}", file=sys.stderr)

    raise RuntimeError(
        f"사용 가능한 Gemini Flash 모델을 찾지 못했습니다. 후보: {candidates}"
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

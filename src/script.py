"""
2단계: 수집된 뉴스를 릴스 대본으로 변환
- 투자 정보는 절대 넣지 않음
- 공식 출처 기반만 사용
- 30~50초 분량 (약 100~150자)
"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """\
너는 대한민국 정부 정책·혜택 정보를 쉽게 설명하는 인스타 릴스 작가다.
규칙을 절대적으로 지켜라:

1. 오직 제공된 원문에 있는 사실만 사용. 추측·일반화 금지.
2. 투자·주식·코인·부동산 투자 수익 관련 조언은 일절 넣지 말 것.
3. "~카더라", "알려드립니다"류 과장 없이 담담하고 친절한 톤.
4. 첫 문장은 혜택을 한 줄로 요약하는 후킹 문장.
5. 마지막에 신청 방법/링크를 꼭 안내.

JSON으로만 답하라:
{
  "hook": "첫 문장 (20자 내외)",
  "body": ["문장1", "문장2", "문장3"],
  "cta": "마무리/신청 안내 문장",
  "hashtags": ["#태그1","#태그2","#태그3","#태그4"],
  "source_label": "출처 표기 문구 (예: 정부24 보도자료 2026.08.06)"
}
"""

def generate_script(article: dict) -> dict:
    client = OpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    user_content = f"""
제목: {article['title']}
출처: {article['source']}
요약: {article['summary']}
원문 URL: {article['url']}
발행일: {article.get('published','')}

이 내용으로 30초 내외 릴스 대본을 JSON으로 작성해줘.
"""
    resp = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )
    data = json.loads(resp.choices[0].message.content)
    data["source_url"] = article["url"]
    data["article_title"] = article["title"]
    return data

def full_narration(script: dict) -> str:
    parts = [script["hook"], *script["body"], script["cta"]]
    return " ".join(parts)

if __name__ == "__main__":
    from collect import fetch_candidates
    cands = fetch_candidates()
    if not cands:
        print("후보 없음")
    else:
        s = generate_script(cands[0])
        print(json.dumps(s, ensure_ascii=False, indent=2))
        print("\n내레이션:", full_narration(s))

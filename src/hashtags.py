"""카테고리별 해시태그 매핑."""

CATEGORY_HASHTAGS = {
    "육아": ["#육아혜택", "#출산혜택", "#부모급여", "#육아휴직", "#아동수당"],
    "부동산": ["#부동산정책", "#전세지원", "#주택청약", "#월세지원", "#임대주택"],
    "세금": ["#세금혜택", "#연말정산", "#세금환급", "#절세팁", "#세금감면"],
    "소상공인": ["#소상공인지원", "#자영업자혜택", "#창업지원", "#소상공인", "#전통시장"],
    "복지": ["#복지혜택", "#기초생활", "#장애인혜택", "#노인복지", "#복지로"],
    "일반정책": ["#정부혜택", "#정부지원", "#정책정보", "#꿀정보", "#혜택정보"],
}


def hashtags_for(category: str, base_tags: list[str] | None = None) -> list[str]:
    """카테고리에 맞는 해시태그 4~6개 반환.
    base_tags(LLM이 만든 것)와 합치되 중복 제거."""
    tags = list(base_tags or [])
    for t in CATEGORY_HASHTAGS.get(category, CATEGORY_HASHTAGS["일반정책"]):
        if t not in tags:
            tags.append(t)
    # 필수 브랜드 태그
    for brand in ["#정부혜택", "#꿀정보", "#릴스"]:
        if brand not in tags:
            tags.append(brand)
    # 최대 8개로 제한
    return tags[:8]


def guess_category(text: str) -> str:
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

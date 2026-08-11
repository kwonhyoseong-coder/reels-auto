"""
정부 부처 보도자료 크롤러 모음.
각 모듈은 fetch() -> list[Article] 을 구현합니다.

Article = {
    "id":       str,  # 고유 ID (URL 또는 글번호)
    "title":    str,
    "url":      str,
    "summary":  str,  # 목록에 노출되는 요약 또는 본문 앞부분
    "content":  str,  # 가능하면 본문 전문 (없으면 summary와 같게)
    "published": str, # ISO8601 또는 YYYY-MM-DD
    "source":   str,  # 기관명
    "category": str,  # 세금/부동산/육아/일반정책
}
"""
from .moel import fetch as fetch_moel
from .mohw import fetch as fetch_mohw
from .mss import fetch as fetch_mss

ALL_SOURCES = [fetch_moel, fetch_mohw, fetch_mss]

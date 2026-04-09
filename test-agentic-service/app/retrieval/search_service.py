"""오늘 뭐해? 검색/추천용 DuckDuckGo retrieval helpers."""
from __future__ import annotations

import logging
import os
import re
import time
from typing import Dict, Iterable, List, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from duckduckgo_search import DDGS
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

_AD_KEYWORDS = (
    "광고",
    "협찬",
    "스폰서",
    "sponsored",
    "promotion",
    "promo",
    "coupon",
    "쿠폰",
    "특가",
    "할인",
    "쇼핑",
    "배송",
    "대출",
    "보험",
    "주식",
    "코인",
)

_BOOKING_HINTS = (
    "예약",
    "예매",
    "booking",
    "reserve",
    "ticket",
    "interpark",
    "catchtable",
    "yanolja",
    "visit",
    "naver",
    "place",
)

_CATEGORY_KEYWORDS = {
    "전시": ("전시", "미술관", "아트", "갤러리", "museum", "exhibition"),
    "카페": ("카페", "브런치", "디저트", "커피", "베이커리"),
    "체험": ("체험", "공방", "클래스", "원데이", "워크숍", "만들기"),
    "산책": ("산책", "공원", "호수", "강변", "둘레길", "코스"),
    "공연": ("공연", "연극", "뮤지컬", "콘서트", "라이브"),
    "맛집": ("맛집", "식당", "레스토랑", "다이닝", "이자카야", "술집"),
    "복합": ("복합", "몰", "플라자", "복합문화", "문화공간", "팝업"),
}

_DEFAULT_CATEGORY_ORDER = ["전시", "카페", "체험", "산책", "공연", "맛집", "복합"]


def _get_env_int(name: str, default: int) -> int:
    """환경 변수 정수 파싱 (유효하지 않으면 기본값)."""
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        logger.warning(f"[오늘 뭐해?] {name}={value} 파싱 실패. 기본값 {default} 사용")
        return default


def _get_rag_mode() -> str:
    """RAG 모드 조회 (web | hybrid | vector). 기본값은 web."""
    mode = os.getenv("RAG_MODE", "web").strip().lower()
    if mode not in {"web", "hybrid", "vector"}:
        logger.warning(f"[오늘 뭐해?] RAG_MODE={mode}는 지원되지 않아 web으로 대체합니다.")
        return "web"
    return mode


def _normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_for_match(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _canonicalize_url(href: str) -> str:
    if not href:
        return ""
    href = href.strip()
    if not href.startswith(("http://", "https://")):
        return _normalize_for_match(href)

    parts = urlsplit(href)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source", "spm"}
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    netloc = parts.netloc.lower()
    if netloc.startswith("m."):
        netloc = netloc[2:]
    path = re.sub(r"/+$", "", parts.path or "")
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def _has_any(text: str, keywords: Iterable[str]) -> bool:
    normalized = _normalize_for_match(text)
    return any(keyword.lower() in normalized for keyword in keywords)


def _keyword_hits(text: str, keywords: Iterable[str]) -> int:
    normalized = _normalize_for_match(text)
    return sum(1 for keyword in keywords if keyword.lower() in normalized)


def _is_ad_like(title: str, body: str, href: str) -> bool:
    haystack = " ".join([title or "", body or "", href or ""])
    normalized = _normalize_for_match(haystack)
    ad_hits = _keyword_hits(normalized, _AD_KEYWORDS)
    if ad_hits == 0:
        return False

    positive_hits = _keyword_hits(normalized, _BOOKING_HINTS)
    if positive_hits >= 2:
        return False

    return ad_hits >= 1


def _infer_category(title: str, body: str, href: str = "") -> str:
    haystack = " ".join([title or "", body or "", href or ""])
    normalized = _normalize_for_match(haystack)
    best_category = "복합"
    best_hits = 0
    for category in _DEFAULT_CATEGORY_ORDER:
        keywords = _CATEGORY_KEYWORDS.get(category, ())
        hits = _keyword_hits(normalized, keywords)
        if hits > best_hits:
            best_category = category
            best_hits = hits
    return best_category


def _infer_area(text: str, default: str = "국내") -> str:
    normalized = _normalize_for_match(text)
    region_keywords = (
        "서울",
        "부산",
        "인천",
        "대구",
        "대전",
        "광주",
        "울산",
        "수원",
        "성수",
        "홍대",
        "연남",
        "종로",
        "강남",
        "잠실",
        "이태원",
        "한남",
        "여의도",
        "잠원",
        "제주",
        "해운대",
    )
    for keyword in region_keywords:
        if keyword.lower() in normalized:
            return keyword
    return default


def _score_result(
    result: Dict[str, str],
    context_terms: Sequence[str] | None = None,
    query_terms: Sequence[str] | None = None,
) -> float:
    title = result.get("title", "")
    body = result.get("body", "")
    href = result.get("href", "")
    haystack = " ".join([title, body, href])
    normalized = _normalize_for_match(haystack)

    score = 0.0
    score += 3.0 * _keyword_hits(title, _CATEGORY_KEYWORDS.get(_infer_category(title, body, href), ()))
    score += 1.5 * _keyword_hits(body, _CATEGORY_KEYWORDS.get(_infer_category(title, body, href), ()))
    score += 1.2 * _keyword_hits(normalized, _BOOKING_HINTS)
    score += 0.8 * _keyword_hits(normalized, ("오늘", "추천", "갈만한", "데이트", "혼자", "비", "실내", "체험", "전시"))

    for term in context_terms or []:
        normalized_term = _normalize_for_match(term)
        if normalized_term and normalized_term in normalized:
            score += 1.4

    for term in query_terms or []:
        normalized_term = _normalize_for_match(term)
        if normalized_term and normalized_term in normalized:
            score += 1.1

    if _is_ad_like(title, body, href):
        score -= 3.0

    if href.startswith("http") and any(domain in href.lower() for domain in ("naver.com", "kakao.com", "visit", "interpark", "catchtable")):
        score += 0.8

    if len(body.strip()) > 120:
        score += 0.3

    return score


def _extract_booking_url(result: Dict[str, str]) -> str:
    href = (result.get("href") or "").strip()
    haystack = " ".join([result.get("title", ""), result.get("body", ""), href]).lower()
    if href and _has_any(href, _BOOKING_HINTS):
        return href
    if href and _has_any(haystack, ("예약", "예매", "booking", "reserve", "ticket")):
        return href
    return ""


def _attach_metadata(
    results: Sequence[Dict[str, str]],
    query: str,
    context_terms: Sequence[str] | None = None,
) -> List[Dict[str, str]]:
    enriched: List[Dict[str, str]] = []
    for rank, result in enumerate(results, start=1):
        title = _normalize_whitespace(result.get("title", ""))
        body = _normalize_whitespace(result.get("body", "") or result.get("snippet", ""))
        href = _normalize_whitespace(result.get("href", "") or result.get("url", ""))
        if not title and not body and not href:
            continue

        enriched.append(
            {
                "query": query,
                "title": title,
                "body": body,
                "href": href,
                "rank": rank,
                "score": _score_result(
                    {"title": title, "body": body, "href": href},
                    context_terms=context_terms,
                    query_terms=query.split(),
                ),
                "category": _infer_category(title, body, href),
                "area": _infer_area(" ".join([title, body, href])),
                "reservation_url": _extract_booking_url({"title": title, "body": body, "href": href}),
            }
        )
    return enriched


def dedupe_results(results: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    """검색 결과를 URL/제목 기준으로 중복 제거하고 점수 순으로 정렬한다."""
    best_by_key: Dict[str, Dict[str, str]] = {}
    for result in results:
        title = _normalize_whitespace(result.get("title", ""))
        body = _normalize_whitespace(result.get("body", ""))
        href = _normalize_whitespace(result.get("href", ""))
        key = _canonicalize_url(href) if href else ""
        if not key:
            key = f"{_normalize_for_match(title)}|{_normalize_for_match(body)[:120]}"
        candidate = dict(result)
        candidate["title"] = title
        candidate["body"] = body
        candidate["href"] = href
        candidate["score"] = float(candidate.get("score", 0.0) or 0.0)
        candidate["rank"] = int(candidate.get("rank", 999) or 999)

        if key in best_by_key:
            current = best_by_key[key]
            current_score = float(current.get("score", 0.0) or 0.0)
            candidate_score = float(candidate.get("score", 0.0) or 0.0)
            if candidate_score > current_score:
                best_by_key[key] = candidate
            continue

        best_by_key[key] = candidate

    return sorted(
        best_by_key.values(),
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            int(item.get("rank", 999) or 999),
            item.get("title", ""),
        ),
    )


def search_web(query: str, max_results: int = 5, retry: int = 2) -> List[Dict[str, str]]:
    """
    DuckDuckGo를 사용하여 웹 검색한다.

    Returns:
        [{"title": "...", "body": "...", "href": "..."}]
    """
    query = _normalize_whitespace(query)
    if not query:
        return []

    logger.info(f"[오늘 뭐해? 검색 시작] query={query}, max_results={max_results}")

    for attempt in range(retry + 1):
        try:
            if attempt > 0:
                delay = 2**attempt
                logger.info(f"[오늘 뭐해? 검색 재시도] attempt={attempt}/{retry}, delay={delay}s")
                time.sleep(delay)

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            formatted_results: List[Dict[str, str]] = []
            for result in results:
                formatted_results.append(
                    {
                        "title": _normalize_whitespace(str(result.get("title", ""))),
                        "body": _normalize_whitespace(str(result.get("body", "") or result.get("snippet", ""))),
                        "href": _normalize_whitespace(str(result.get("href", "") or result.get("url", ""))),
                    }
                )

            logger.info(f"[오늘 뭐해? 검색 완료] query={query}, results={len(formatted_results)}")
            return formatted_results
        except Exception as exc:  # pragma: no cover - network failure path
            error_msg = str(exc)
            if "Ratelimit" in error_msg and attempt < retry:
                logger.warning(f"[오늘 뭐해? 검색 RateLimit] retrying query={query}")
                continue
            logger.error(f"[오늘 뭐해? 검색 오류] query={query}, error={error_msg}")
            return []

    logger.error(f"[오늘 뭐해? 검색 실패] query={query}")
    return []


def format_search_results(results: Sequence[Dict[str, str]], heading: str = "검색 결과") -> str:
    """검색 결과를 사람이 읽을 수 있는 컨텍스트 문자열로 포맷팅한다."""
    if not results:
        return ""

    lines = [f"\n\n=== {heading} ===\n"]
    for index, result in enumerate(results, start=1):
        title = _normalize_whitespace(str(result.get("title", "")))
        body = _normalize_whitespace(str(result.get("body", "")))
        href = _normalize_whitespace(str(result.get("href", "")))
        category = _normalize_whitespace(str(result.get("category", "")))
        area = _normalize_whitespace(str(result.get("area", "")))
        score = result.get("score")

        lines.append(f"[{index}] {title}".rstrip())
        if category or area or score is not None:
            extras = []
            if category:
                extras.append(f"카테고리: {category}")
            if area:
                extras.append(f"지역: {area}")
            if score is not None:
                extras.append(f"점수: {float(score):.2f}")
            lines.append(" / ".join(extras))
        if body:
            lines.append(body)
        if href:
            lines.append(f"출처: {href}")
        lines.append("")

    return "\n".join(lines).strip()


def merge_contexts(
    vector_results: Sequence[Dict[str, str]],
    web_results: Sequence[Dict[str, str]],
) -> str:
    """벡터/웹 검색 결과를 하나의 컨텍스트 문자열로 병합한다."""
    sections: List[str] = []
    vector_context = format_search_results(vector_results, heading="로컬 지식 검색 결과")
    if vector_context:
        sections.append(vector_context)

    web_context = format_search_results(web_results, heading="웹 검색 결과")
    if web_context:
        sections.append(web_context)

    return "\n\n".join(sections).strip()


def retrieve_with_vector(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """벡터 검색을 시도한다. 인덱스가 없으면 빈 리스트를 반환한다."""
    query = _normalize_whitespace(query)
    if not query:
        return []

    try:
        try:
            from retrieval.vector_store import retrieve
        except ModuleNotFoundError:  # pragma: no cover - import path fallback
            from app.retrieval.vector_store import retrieve
        return retrieve(query=query, k=max_results)
    except Exception as exc:
        logger.warning(f"[오늘 뭐해?] 벡터 검색 사용 불가: {exc}")
        return []


def search_with_context(query: str, max_results: int = 5) -> str:
    """DuckDuckGo 웹 검색 후 컨텍스트 문자열을 반환한다."""
    query = _normalize_whitespace(query)
    if not query:
        return ""

    logger.info(f"[오늘 뭐해? 컨텍스트 검색] query={query}")
    rag_mode = _get_rag_mode()
    vector_results: List[Dict[str, str]] = []
    web_results: List[Dict[str, str]] = []

    if rag_mode == "web":
        web_results = search_web(query, max_results=max_results)
        return merge_contexts(vector_results=[], web_results=web_results)

    vector_results = retrieve_with_vector(query=query, max_results=max_results)
    if vector_results:
        return merge_contexts(vector_results=vector_results, web_results=[])

    web_results = search_web(query, max_results=max_results)
    return merge_contexts(vector_results=[], web_results=web_results)


@tool("search_web")
def search_web_tool(query: str, max_results: int = 5) -> str:
    """DuckDuckGo 웹 검색을 실행하고 결과를 컨텍스트 문자열로 반환한다."""
    query = _normalize_whitespace(query)
    if not query:
        return "검색어가 비어 있습니다."

    results = search_web(query=query, max_results=max_results)
    if not results:
        return "검색 결과가 없습니다."
    return format_search_results(results, heading="웹 검색 결과").strip()


@tool("search_outing_context")
def search_outing_context_tool(query: str, max_results: int = 5) -> str:
    """오늘 뭐해? 상황 검색용 컨텍스트를 반환한다."""
    query = _normalize_whitespace(query)
    if not query:
        return "검색어가 비어 있습니다."

    context = search_with_context(query=query, max_results=max_results)
    return context if context else "검색 결과가 없습니다."


def search_outing_candidates(
    queries: Sequence[str],
    max_results_per_query: int = 4,
    context_terms: Sequence[str] | None = None,
) -> List[Dict[str, str]]:
    """멀티쿼리 검색을 실행하고 정렬된 후보를 반환한다."""
    enriched_results: List[Dict[str, str]] = []
    seen_queries = []
    for query in queries:
        cleaned_query = _normalize_whitespace(query)
        if not cleaned_query or cleaned_query in seen_queries:
            continue
        seen_queries.append(cleaned_query)

        raw_results = search_web(cleaned_query, max_results=max_results_per_query)
        enriched_results.extend(
            _attach_metadata(raw_results, query=cleaned_query, context_terms=context_terms)
        )

    return dedupe_results(enriched_results)


__all__ = [
    "dedupe_results",
    "format_search_results",
    "merge_contexts",
    "retrieve_with_vector",
    "search_outing_candidates",
    "search_outing_context_tool",
    "search_web",
    "search_web_tool",
    "search_with_context",
]

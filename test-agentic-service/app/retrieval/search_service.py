"""Hybrid retrieval utilities for dining recommendations."""
import logging
import os
import time
from typing import Dict, List

from duckduckgo_search import DDGS
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        logger.warning(f"[RAG 설정] {name}={value} 파싱 실패. 기본값 {default} 사용")
        return default


def _get_rag_mode() -> str:
    mode = os.getenv("RAG_MODE", "hybrid").strip().lower()
    if mode not in {"hybrid", "vector", "web"}:
        logger.warning(f"[RAG 설정] RAG_MODE={mode}는 지원되지 않아 hybrid로 대체합니다.")
        return "hybrid"
    return mode


def search_web(query: str, max_results: int = 5, retry: int = 2) -> List[Dict[str, str]]:
    logger.info(f"[RAG 검색 시작] 쿼리: {query}, 최대 결과: {max_results}")

    for attempt in range(retry + 1):
        try:
            if attempt > 0:
                delay = 2 ** attempt
                logger.info(f"[재시도 {attempt}/{retry}] {delay}초 대기 중...")
                time.sleep(delay)

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "title": result.get("title", ""),
                        "body": result.get("body", ""),
                        "href": result.get("href", ""),
                    }
                )
            logger.info(f"[RAG 검색 완료] {len(formatted_results)}개 결과 반환")
            return formatted_results
        except Exception as exc:
            error_msg = str(exc)
            if "Ratelimit" in error_msg and attempt < retry:
                logger.warning(f"[RAG 검색 Rate Limit] 재시도 예정... ({attempt + 1}/{retry})")
                continue
            logger.error(f"[RAG 검색 오류] {error_msg}")
            return []

    logger.error("[RAG 검색 실패] 모든 재시도 실패")
    return []


def format_search_results(
    results: List[Dict[str, str]], heading: str = "검색 결과"
) -> str:
    if not results:
        return ""

    context = [f"=== {heading} ===", ""]
    for index, result in enumerate(results, start=1):
        context.append(f"[{index}] {result['title']}")
        context.append(result["body"])
        if result["href"]:
            context.append(f"출처: {result['href']}")
        context.append("")
    return "\n".join(context).strip()


def retrieve_with_vector(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    try:
        try:
            from retrieval.vector_store import retrieve
        except ModuleNotFoundError:
            from app.retrieval.vector_store import retrieve
        return retrieve(query=query, k=max_results)
    except Exception as exc:
        logger.warning(f"[Vector RAG] 벡터 검색 사용 불가: {exc}")
        return []


def merge_contexts(
    vector_results: List[Dict[str, str]],
    web_results: List[Dict[str, str]],
) -> str:
    sections = []
    vector_context = format_search_results(vector_results, heading="로컬 다이닝 지식")
    if vector_context:
        sections.append(vector_context)

    web_context = format_search_results(web_results, heading="웹 검색 결과")
    if web_context:
        sections.append(web_context)

    return "\n\n".join(sections).strip()


def search_with_context(query: str, max_results: int = 5) -> str:
    logger.info(f"[컨텍스트 검색] 쿼리: {query}")

    rag_mode = _get_rag_mode()
    vector_top_k = min(max_results, _get_env_int("VECTOR_TOP_K", 4))
    min_vector_results = _get_env_int("WEB_FALLBACK_MIN_RESULTS", 2)

    vector_results: List[Dict[str, str]] = []
    web_results: List[Dict[str, str]] = []

    if rag_mode == "web":
        web_results = search_web(query, max_results=max_results)
        return merge_contexts(vector_results=[], web_results=web_results)

    try:
        vector_results = retrieve_with_vector(query=query, max_results=vector_top_k)
    except Exception as exc:
        logger.warning(f"[Vector RAG] 예외 발생으로 벡터 검색을 건너뜁니다: {exc}")
        vector_results = []

    if len(vector_results) >= min_vector_results:
        return merge_contexts(vector_results=vector_results, web_results=[])

    logger.warning(
        "[Vector RAG] 결과가 부족하여 웹 검색 보조를 수행합니다. "
        f"(mode={rag_mode}, vector={len(vector_results)}, min={min_vector_results})"
    )
    web_results = search_web(query, max_results=max_results)
    return merge_contexts(vector_results=vector_results, web_results=web_results)


@tool("search_web")
def search_web_tool(query: str, max_results: int = 5) -> str:
    """DuckDuckGo 웹 검색을 실행하고 결과를 문자열 컨텍스트로 반환합니다."""
    if not query or not query.strip():
        return "검색어가 비어 있습니다."

    results = search_web(query=query.strip(), max_results=max_results)
    if not results:
        return "검색 결과가 없습니다."

    return format_search_results(results, heading="웹 검색 결과").strip()


@tool("search_place_context")
def search_place_context_tool(query: str, max_results: int = 5) -> str:
    """맛집/카페 추천 단계용 하이브리드 RAG 컨텍스트 검색을 수행합니다."""
    if not query or not query.strip():
        return "검색어가 비어 있습니다."

    context = search_with_context(query=query.strip(), max_results=max_results)
    return context if context else "검색 결과가 없습니다."

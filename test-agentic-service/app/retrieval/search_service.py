"""하이브리드 RAG 검색 서비스 (벡터DB + DuckDuckGo 웹 검색)."""
import logging
import os
import time
from typing import List, Dict
from duckduckgo_search import DDGS
from langchain_core.tools import tool

# 로거 설정
logger = logging.getLogger(__name__)


def _get_env_int(name: str, default: int) -> int:
    """환경 변수 정수 파싱 (유효하지 않으면 기본값)."""
    value = os.getenv(name, str(default)).strip()
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except ValueError:
        logger.warning(f"[RAG 설정] {name}={value} 파싱 실패. 기본값 {default} 사용")
        return default


def _get_rag_mode() -> str:
    """RAG 모드 조회 (hybrid | vector | web)."""
    mode = os.getenv("RAG_MODE", "hybrid").strip().lower()
    if mode not in {"hybrid", "vector", "web"}:
        logger.warning(f"[RAG 설정] RAG_MODE={mode}는 지원되지 않아 hybrid로 대체합니다.")
        return "hybrid"
    return mode


def search_web(query: str, max_results: int = 5, retry: int = 2) -> List[Dict[str, str]]:
    """
    DuckDuckGo를 사용하여 웹 검색 (재시도 로직 포함)
    
    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수
        retry: 재시도 횟수
        
    Returns:
        검색 결과 리스트 [{"title": "제목", "body": "내용", "href": "URL"}]
    """
    logger.info(f"[RAG 검색 시작] 쿼리: {query}, 최대 결과: {max_results}")
    
    for attempt in range(retry + 1):
        try:
            # Rate limit 방지를 위한 딜레이
            if attempt > 0:
                delay = 2 ** attempt  # 지수 백오프: 2초, 4초
                logger.info(f"[재시도 {attempt}/{retry}] {delay}초 대기 중...")
                time.sleep(delay)
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                
            logger.info(f"[RAG 검색 완료] {len(results)}개 결과 반환")
            
            # 결과 포맷팅
            formatted_results = []
            for i, result in enumerate(results, 1):
                formatted = {
                    "title": result.get("title", ""),
                    "body": result.get("body", ""),
                    "href": result.get("href", "")
                }
                formatted_results.append(formatted)
                logger.debug(f"  [{i}] {formatted['title'][:50]}...")
            
            return formatted_results
            
        except Exception as e:
            error_msg = str(e)
            if "Ratelimit" in error_msg and attempt < retry:
                logger.warning(f"[RAG 검색 Rate Limit] 재시도 예정... ({attempt + 1}/{retry})")
                continue
            else:
                logger.error(f"[RAG 검색 오류] {error_msg}")
                return []
    
    logger.error("[RAG 검색 실패] 모든 재시도 실패")
    return []


def format_search_results(results: List[Dict[str, str]], heading: str = "검색 결과") -> str:
    """
    검색 결과를 컨텍스트 문자열로 포맷팅
    
    Args:
        results: 검색 결과 리스트
        
    Returns:
        포맷팅된 컨텍스트 문자열
    """
    if not results:
        return ""

    context = f"\n\n=== {heading} ===\n\n"
    
    for i, result in enumerate(results, 1):
        context += f"[{i}] {result['title']}\n"
        context += f"{result['body']}\n"
        if result['href']:
            context += f"출처: {result['href']}\n"
        context += "\n"
    
    return context


def retrieve_with_vector(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    벡터DB에서 관련 문서를 검색한다.

    Note:
        인덱스가 없거나 깨져있는 경우 예외 대신 빈 리스트를 반환한다.
    """
    try:
        # Lazy import로 앱 기동 시 의존성 영향 최소화
        try:
            from retrieval.vector_store import retrieve
        except ModuleNotFoundError:
            from app.retrieval.vector_store import retrieve
        return retrieve(query=query, k=max_results)
    except Exception as e:
        logger.warning(f"[Vector RAG] 벡터 검색 사용 불가: {e}")
        return []


def merge_contexts(vector_results: List[Dict[str, str]], web_results: List[Dict[str, str]]) -> str:
    """벡터/웹 검색 결과를 하나의 컨텍스트 문자열로 병합한다."""
    sections = []
    vector_context = format_search_results(vector_results, heading="벡터 검색 결과")
    if vector_context:
        sections.append(vector_context)

    web_context = format_search_results(web_results, heading="웹 검색 결과")
    if web_context:
        sections.append(web_context)

    return "".join(sections).strip()


def search_with_context(query: str, max_results: int = 5) -> str:
    """
    웹 검색 후 컨텍스트 문자열 반환
    
    Args:
        query: 검색 쿼리
        max_results: 최대 결과 수
        
    Returns:
        포맷팅된 검색 결과 컨텍스트
    """
    logger.info(f"[컨텍스트 검색] 쿼리: {query}")

    rag_mode = _get_rag_mode()
    vector_top_k = min(max_results, _get_env_int("VECTOR_TOP_K", 4))
    min_vector_results = _get_env_int("WEB_FALLBACK_MIN_RESULTS", 2)

    vector_results: List[Dict[str, str]] = []
    web_results: List[Dict[str, str]] = []

    # 웹 전용 모드면 기존 동작 유지
    if rag_mode == "web":
        web_results = search_web(query, max_results=max_results)
        context = merge_contexts(vector_results=[], web_results=web_results)
        logger.info(f"[컨텍스트 생성 완료] 모드: {rag_mode}, 길이: {len(context)} 문자")
        return context

    # vector/hybrid 공통: 벡터 검색 우선
    try:
        vector_results = retrieve_with_vector(query=query, max_results=vector_top_k)
    except Exception as e:
        logger.warning(f"[Vector RAG] 예외 발생으로 벡터 검색을 건너뜁니다: {e}")
        vector_results = []
    vector_count = len(vector_results)
    logger.info(f"[Vector RAG] 결과 수: {vector_count}개 (요구 최소: {min_vector_results}개)")

    # 충분한 벡터 결과가 있으면 웹 검색 생략 (hybrid/vector 공통)
    if vector_count >= min_vector_results:
        context = merge_contexts(vector_results=vector_results, web_results=[])
        logger.info(f"[컨텍스트 생성 완료] 모드: {rag_mode}, 길이: {len(context)} 문자")
        return context

    # 결과 부족 시 웹 검색 보조 (vector 모드에서도 graceful fallback)
    logger.warning(
        f"[Vector RAG] 결과가 부족하여 웹 검색 보조를 수행합니다. "
        f"(mode={rag_mode}, vector={vector_count}, min={min_vector_results})"
    )
    web_results = search_web(query, max_results=max_results)
    context = merge_contexts(vector_results=vector_results, web_results=web_results)

    logger.info(
        f"[컨텍스트 생성 완료] 모드: {rag_mode}, "
        f"vector={len(vector_results)}개, web={len(web_results)}개, 길이: {len(context)} 문자"
    )

    return context


@tool("search_web")
def search_web_tool(query: str, max_results: int = 5) -> str:
    """DuckDuckGo 웹 검색을 실행하고 결과를 컨텍스트 문자열로 반환합니다."""
    if not query or not query.strip():
        return "검색어가 비어 있습니다."

    results = search_web(query=query.strip(), max_results=max_results)
    if not results:
        return "검색 결과가 없습니다."

    return format_search_results(results, heading="웹 검색 결과").strip()


@tool("search_city_context")
def search_city_context_tool(query: str, max_results: int = 5) -> str:
    """도시 추천 단계용 하이브리드 RAG 컨텍스트 검색을 수행합니다."""
    if not query or not query.strip():
        return "검색어가 비어 있습니다."

    context = search_with_context(query=query.strip(), max_results=max_results)
    return context if context else "검색 결과가 없습니다."


@tool("search_flight_context")
def search_flight_context_tool(query: str, max_results: int = 5) -> str:
    """항공권 검색 단계용 하이브리드 RAG 컨텍스트 검색을 수행합니다."""
    if not query or not query.strip():
        return "검색어가 비어 있습니다."

    context = search_with_context(query=query.strip(), max_results=max_results)
    return context if context else "검색 결과가 없습니다."

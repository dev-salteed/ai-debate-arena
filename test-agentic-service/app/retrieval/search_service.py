"""DuckDuckGo 웹 검색 서비스"""
import logging
import time
from typing import List, Dict
from duckduckgo_search import DDGS

# 로거 설정
logger = logging.getLogger(__name__)


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


def format_search_results(results: List[Dict[str, str]]) -> str:
    """
    검색 결과를 컨텍스트 문자열로 포맷팅
    
    Args:
        results: 검색 결과 리스트
        
    Returns:
        포맷팅된 컨텍스트 문자열
    """
    if not results:
        return ""
    
    context = "\n\n=== 검색 결과 ===\n\n"
    
    for i, result in enumerate(results, 1):
        context += f"[{i}] {result['title']}\n"
        context += f"{result['body']}\n"
        if result['href']:
            context += f"출처: {result['href']}\n"
        context += "\n"
    
    return context


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
    
    results = search_web(query, max_results)
    context = format_search_results(results)
    
    logger.info(f"[컨텍스트 생성 완료] 길이: {len(context)} 문자")
    
    return context

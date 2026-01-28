"""로깅 시스템 설정"""
import logging
import sys
from datetime import datetime


def setup_logger(name: str = "travel_agent", level: int = logging.INFO) -> logging.Logger:
    """
    로거 설정
    
    Args:
        name: 로거 이름
        level: 로깅 레벨
        
    Returns:
        설정된 로거
    """
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 있으면 반환 (중복 방지)
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 포맷터 설정
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


def log_agent_input(logger: logging.Logger, agent_name: str, state: dict):
    """에이전트 입력 로깅"""
    logger.info(f"{'='*60}")
    logger.info(f"[{agent_name}] 실행 시작")
    logger.info(f"{'='*60}")
    logger.info(f"입력 상태:")
    logger.info(f"  - 여행 주제: {state.get('travel_theme', 'N/A')}")
    logger.info(f"  - 여행 일수: {state.get('travel_days', 'N/A')}일")
    logger.info(f"  - 예산: {state.get('budget', 'N/A'):,}원" if state.get('budget') else "  - 예산: 미정")
    logger.info(f"  - 현재 단계: {state.get('current_step', 'N/A')}")


def log_agent_output(logger: logging.Logger, agent_name: str, result: any):
    """에이전트 출력 로깅"""
    logger.info(f"\n[{agent_name}] 결과:")
    logger.info(f"  출력 타입: {type(result).__name__}")
    if isinstance(result, str):
        logger.info(f"  내용 (앞 100자): {result[:100]}...")
    elif isinstance(result, (list, dict)):
        logger.info(f"  내용: {result}")
    logger.info(f"{'='*60}\n")


def log_search_context(logger: logging.Logger, query: str, context: str):
    """검색 컨텍스트 로깅"""
    logger.info(f"\n[RAG 검색 컨텍스트]")
    logger.info(f"  쿼리: {query}")
    logger.info(f"  컨텍스트 길이: {len(context)} 문자")
    logger.debug(f"  컨텍스트 내용:\n{context[:500]}...")

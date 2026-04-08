"""Logging helpers for the dining recommendation service."""
import logging
import sys


def setup_logger(name: str = "dining_agent", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


def log_agent_input(logger: logging.Logger, agent_name: str, state: dict):
    logger.info("=" * 60)
    logger.info(f"[{agent_name}] 실행 시작")
    logger.info("=" * 60)
    logger.info(f"입력 쿼리: {state.get('user_query', 'N/A')}")
    logger.info(f"현재 단계: {state.get('current_step', 'N/A')}")
    parsed_query = state.get("parsed_query") or {}
    if parsed_query:
        logger.info(
            "해석 요약: "
            f"region={parsed_query.get('region', '')}, "
            f"venue_type={parsed_query.get('venue_type', '')}, "
            f"purpose={parsed_query.get('purpose', '')}"
        )


def log_agent_output(logger: logging.Logger, agent_name: str, result):
    logger.info(f"\n[{agent_name}] 결과:")
    logger.info(f"  출력 타입: {type(result).__name__}")
    if isinstance(result, str):
        logger.info(f"  내용 (앞 120자): {result[:120]}...")
    elif isinstance(result, (list, dict)):
        logger.info(f"  내용: {result}")
    logger.info("=" * 60 + "\n")

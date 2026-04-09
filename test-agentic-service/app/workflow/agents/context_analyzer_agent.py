"""Context analyzer for 오늘 뭐해?"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Dict, List

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState

_REGION_KEYWORDS = (
    "서울",
    "부산",
    "인천",
    "대구",
    "대전",
    "광주",
    "울산",
    "수원",
    "제주",
    "성수",
    "홍대",
    "연남",
    "합정",
    "종로",
    "강남",
    "잠실",
    "이태원",
    "한남",
    "여의도",
    "해운대",
    "서면",
)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _pick_region(query: str, fallback: str) -> str:
    normalized = _normalize_text(query)
    for keyword in _REGION_KEYWORDS:
        if keyword in normalized:
            return keyword
    return fallback or "서울"


def _pick_companion(query: str, fallback: str) -> str:
    normalized = _normalize_text(query)
    if any(token in normalized for token in ("썸", "연애", "연인", "커플", "데이트")):
        return "썸"
    if any(token in normalized for token in ("친구", "동행", "약속", "모임")):
        return "친구"
    if any(token in normalized for token in ("혼자", "솔로", "나혼자", "나 혼자")):
        return "혼자"
    if any(token in normalized for token in ("가족", "부모", "아이", "아이랑")):
        return "가족"
    return fallback or "상관없음"


def _pick_weather(query: str, fallback: str) -> str:
    normalized = _normalize_text(query)
    if any(token in normalized for token in ("비", "우천", "장마", "rain")):
        return "비"
    if any(token in normalized for token in ("눈", "snow", "폭설")):
        return "눈"
    if any(token in normalized for token in ("흐림", "구름", "쌀쌀")):
        return "흐림"
    if any(token in normalized for token in ("맑", "화창", "쾌청")):
        return "맑음"
    return fallback or "상관없음"


def _pick_time_slot(query: str, fallback: str) -> str:
    normalized = _normalize_text(query)
    if any(token in normalized for token in ("아침", "오전", "브런치", "아점")):
        return "오전"
    if any(token in normalized for token in ("점심", "오후", "낮", "점심쯤")):
        return "오후"
    if any(token in normalized for token in ("저녁", "밤", "야간", "퇴근")):
        return "저녁"
    if any(token in normalized for token in ("하루", "종일", "풀코스", "오픈런")):
        return "하루 종일"
    return fallback or "상관없음"


def _pick_budget_level(query: str, fallback: str) -> str:
    normalized = _normalize_text(query)
    if any(token in normalized for token in ("가성비", "저렴", "가볍게", "무료", "부담없", "싼")):
        return "가볍게"
    if any(token in normalized for token in ("프리미엄", "고급", "특별", "비싸", "여유")):
        return "여유"
    return fallback or "상관없음"


def _pick_mobility(query: str, fallback: str) -> str:
    normalized = _normalize_text(query)
    if any(token in normalized for token in ("도보", "걷", "산책", "가까운")):
        return "도보 위주"
    if any(token in normalized for token in ("택시", "차로", "편하게")):
        return "택시 가능"
    if any(token in normalized for token in ("지하철", "버스", "대중교통")):
        return "대중교통"
    return fallback or "상관없음"


def _extract_keywords(query: str) -> List[str]:
    normalized = _normalize_text(query)
    candidates = [
        "데이트",
        "썸",
        "혼자",
        "친구",
        "가족",
        "전시",
        "카페",
        "체험",
        "원데이",
        "산책",
        "공연",
        "맛집",
        "실내",
        "예약",
    ]
    return [keyword for keyword in candidates if keyword in normalized]


class ContextAnalyzerAgent:
    """자연어 입력을 상황 중심 추천 컨텍스트로 정리한다."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.CONTEXT_ANALYZER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)

        new_state = deepcopy(state)
        messages = list(new_state.get("messages", []))
        decision_memory = list(new_state.get("decision_memory", []))

        user_query = _normalize_text(new_state.get("user_query", ""))
        region = _pick_region(user_query, new_state.get("region", "서울"))
        companion = _pick_companion(user_query, new_state.get("companion", "상관없음"))
        weather = _pick_weather(user_query, new_state.get("weather", "상관없음"))
        time_slot = _pick_time_slot(user_query, new_state.get("time_slot", "상관없음"))
        budget_level = _pick_budget_level(user_query, new_state.get("budget_level", "상관없음"))
        mobility = _pick_mobility(user_query, new_state.get("mobility", "상관없음"))
        keywords = _extract_keywords(user_query)

        parsed = dict(new_state.get("parsed_context", {}))
        parsed.update(
            {
                "intent": user_query,
                "region": region,
                "companion": companion,
                "weather": weather,
                "time_slot": time_slot,
                "budget_level": budget_level,
                "mobility": mobility,
                "keywords": keywords,
                "category_hints": keywords[:5],
                "search_focus": " / ".join(
                    [value for value in [region, companion, weather, time_slot, budget_level] if value and value != "상관없음"]
                ),
                "must_have": ["3~5개 추천", "timeline", "route_summary", "booking_links"],
                "prefer_indoor": weather in {"비", "눈", "흐림"},
            }
        )

        new_state["region"] = region
        new_state["companion"] = companion
        new_state["weather"] = weather
        new_state["time_slot"] = time_slot
        new_state["budget_level"] = budget_level
        new_state["mobility"] = mobility
        new_state["parsed_context"] = parsed
        new_state["current_step"] = self.role
        new_state["completed"] = False

        messages.append(
            {
                "role": self.role,
                "content": (
                    f"상황 분석 완료: 지역={region}, 동행={companion}, 날씨={weather}, "
                    f"시간대={time_slot}, 예산={budget_level}, 이동={mobility}"
                ),
            }
        )
        new_state["messages"] = messages[-20:]

        decision_memory.append(
            "CONTEXT_ANALYZER: "
            f"region={region}, companion={companion}, weather={weather}, time_slot={time_slot}"
        )
        new_state["decision_memory"] = decision_memory[-12:]

        log_agent_output(self.logger, self.role, parsed)
        return new_state

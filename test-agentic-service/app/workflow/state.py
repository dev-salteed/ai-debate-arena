"""State definitions for the 오늘 뭐해? service."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, TypedDict

CompanionType = Literal["혼자", "썸", "연인", "친구", "가족", "상관없음"]
WeatherType = Literal["맑음", "비", "흐림", "눈", "상관없음"]
TimeSlotType = Literal["오전", "오후", "저녁", "하루 종일", "상관없음"]
BudgetLevelType = Literal["여유", "보통", "가볍게", "상관없음"]
MobilityType = Literal["도보 위주", "대중교통", "택시 가능", "상관없음"]


class AgentType:
    SUPERVISOR = "SUPERVISOR"
    CONTEXT_ANALYZER = "CONTEXT_ANALYZER"
    RETRIEVER = "RETRIEVER"
    CURATOR = "CURATOR"
    PLANNER = "PLANNER"
    RESPONSE_COMPOSER = "RESPONSE_COMPOSER"

    @classmethod
    def to_korean(cls, role: str) -> str:
        mapping = {
            cls.SUPERVISOR: "총괄",
            cls.CONTEXT_ANALYZER: "상황 분석",
            cls.RETRIEVER: "검색 수집",
            cls.CURATOR: "후보 큐레이션",
            cls.PLANNER: "일정 설계",
            cls.RESPONSE_COMPOSER: "응답 정리",
        }
        return mapping.get(role, role)


class TodayWhatState(TypedDict):
    user_query: str
    region: str
    companion: CompanionType
    weather: WeatherType
    time_slot: TimeSlotType
    budget_level: BudgetLevelType
    mobility: MobilityType
    parsed_context: Dict[str, object]
    search_queries: List[str]
    raw_search_results: List[Dict[str, object]]
    curated_candidates: List[Dict[str, object]]
    final_plan: Dict[str, object]
    decision_memory: List[str]
    constraints_memory: Dict[str, str]
    messages: List[Dict[str, str]]
    current_step: str
    completed: bool

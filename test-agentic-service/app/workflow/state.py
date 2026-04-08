"""LangGraph state for the dining recommendation service."""
from typing import Any, Dict, List, Optional, TypedDict


class AgentType:
    SUPERVISOR = "SUPERVISOR"
    QUERY_PARSER = "QUERY_PARSER"
    PLACE_SEARCH = "PLACE_SEARCH"
    RAG_PROCESSOR = "RAG_PROCESSOR"
    RECOMMENDATION = "RECOMMENDATION"

    @classmethod
    def to_korean(cls, role: str) -> str:
        mapping = {
            cls.SUPERVISOR: "총괄",
            cls.QUERY_PARSER: "요청 해석",
            cls.PLACE_SEARCH: "검색",
            cls.RAG_PROCESSOR: "근거 정리",
            cls.RECOMMENDATION: "최종 추천",
        }
        return mapping.get(role, role)


class DiningState(TypedDict):
    user_query: str
    parsed_query: Dict[str, Any]
    search_brief: Dict[str, Any]
    candidate_places: List[Dict[str, Any]]
    recommendations: Optional[Dict[str, Any]]
    search_iterations: int
    max_search_iterations: int
    decision_memory: List[str]
    constraints_memory: Dict[str, str]
    current_step: str
    messages: List[Dict[str, str]]
    completed: bool

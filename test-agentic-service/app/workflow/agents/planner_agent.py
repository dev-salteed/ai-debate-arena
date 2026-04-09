"""Planner for 오늘 뭐해?"""
from __future__ import annotations

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState


class PlannerAgent:
    """Placeholder planner interface stabilized in refactor step."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.PLANNER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)
        new_state = state.copy()
        new_state["final_plan"] = {
            "summary": "아직 추천 후보를 정리하는 중입니다.",
            "situation_tags": [],
            "recommendations": [],
            "timeline": [],
            "route_summary": "",
            "booking_links": [],
            "notes": [],
            "follow_up_prompt": "원하는 분위기나 지역을 더 알려주면 다시 추천할게요.",
            "fallback_option": "검색 범위를 넓혀 다시 추천할 수 있습니다.",
            "quick_tips": [],
        }
        new_state["current_step"] = self.role
        new_state["messages"].append(
            {"role": self.role, "content": "추천 흐름을 일정 형태로 정리"}
        )
        log_agent_output(self.logger, self.role, new_state["final_plan"])
        return new_state

"""Curator for 오늘 뭐해?"""
from __future__ import annotations

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState


class CuratorAgent:
    """Placeholder curator interface stabilized in refactor step."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.CURATOR
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)
        new_state = state.copy()
        new_state["curated_candidates"] = []
        new_state["current_step"] = self.role
        new_state["messages"].append(
            {"role": self.role, "content": "검색 결과를 활동 후보로 정리"}
        )
        log_agent_output(self.logger, self.role, new_state["curated_candidates"])
        return new_state

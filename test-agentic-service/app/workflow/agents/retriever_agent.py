"""Retriever for 오늘 뭐해?"""
from __future__ import annotations

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState


class RetrieverAgent:
    """Placeholder retriever interface stabilized in refactor step."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.RETRIEVER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)
        parsed_context = state.get("parsed_context", {})
        queries = [
            f"{parsed_context.get('region', state.get('region', '서울'))} {state.get('user_query', '')}".strip(),
        ]

        new_state = state.copy()
        constraints_memory = dict(new_state.get("constraints_memory", {}))
        constraints_memory["broaden_search"] = "false"
        new_state["search_queries"] = queries
        new_state["raw_search_results"] = []
        new_state["constraints_memory"] = constraints_memory
        new_state["current_step"] = self.role
        new_state["messages"].append(
            {"role": self.role, "content": f"검색 쿼리 초안 {len(queries)}개 생성"}
        )
        log_agent_output(self.logger, self.role, {"queries": queries})
        return new_state

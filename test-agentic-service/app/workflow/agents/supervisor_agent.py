"""Supervisor agent for the 오늘 뭐해? graph."""
from __future__ import annotations

from workflow.state import AgentType, TodayWhatState


class SupervisorAgent:
    """Controls graph progression and a single broad-search retry."""

    def __init__(self):
        self.role = AgentType.SUPERVISOR

    def run(self, state: TodayWhatState) -> TodayWhatState:
        new_state = state.copy()
        current_step = state.get("current_step", "")
        if current_step not in {AgentType.RETRIEVER, AgentType.CURATOR}:
            return new_state

        constraints_memory = dict(new_state.get("constraints_memory", {}))
        decision_memory = list(new_state.get("decision_memory", []))
        retry_attempts = int(constraints_memory.get("retry_attempts", "0"))
        curated_candidates = new_state.get("curated_candidates", [])
        has_booking_link = any(
            bool(candidate.get("reservation_url"))
            for candidate in curated_candidates
        )
        needs_retry = len(curated_candidates) < 3 or not has_booking_link

        if current_step == AgentType.CURATOR and needs_retry and retry_attempts < 1:
            constraints_memory["retry_attempts"] = str(retry_attempts + 1)
            constraints_memory["broaden_search"] = "true"
            decision_memory.append(
                "SUPERVISOR: 큐레이션 후보 부족으로 검색 범위를 넓혀 한 번 더 수집"
            )
            new_state["messages"].append(
                {
                    "role": self.role,
                    "content": "후보가 부족해 검색 범위를 넓혀 한 번 더 찾아볼게요.",
                }
            )
        else:
            constraints_memory.setdefault("broaden_search", "false")

        new_state["constraints_memory"] = constraints_memory
        new_state["decision_memory"] = decision_memory[-12:]
        return new_state

    def route_next(self, state: TodayWhatState) -> str:
        current_step = state.get("current_step", "")
        constraints_memory = state.get("constraints_memory", {})
        broaden_search = constraints_memory.get("broaden_search", "false") == "true"

        if not current_step:
            return AgentType.CONTEXT_ANALYZER
        if current_step == AgentType.CONTEXT_ANALYZER:
            return AgentType.RETRIEVER
        if current_step == AgentType.RETRIEVER:
            return AgentType.CURATOR
        if current_step == AgentType.CURATOR:
            if broaden_search:
                return AgentType.RETRIEVER
            return AgentType.PLANNER
        if current_step == AgentType.PLANNER:
            return AgentType.RESPONSE_COMPOSER
        if current_step == AgentType.RESPONSE_COMPOSER:
            return "END"
        return "END"

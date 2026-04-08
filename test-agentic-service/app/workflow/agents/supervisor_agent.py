"""Supervisor agent for the dining workflow."""
from workflow.state import AgentType, DiningState


class SupervisorAgent:
    """Routes the dining workflow and decides whether to broaden search."""

    def __init__(self):
        self.role = AgentType.SUPERVISOR

    def run(self, state: DiningState) -> DiningState:
        new_state = state.copy()
        current_step = state.get("current_step", "")

        if current_step != AgentType.RAG_PROCESSOR:
            return new_state

        candidate_places = state.get("candidate_places", [])
        if candidate_places:
            return new_state

        search_iterations = state.get("search_iterations", 0)
        max_search_iterations = state.get("max_search_iterations", 2)
        if search_iterations >= max_search_iterations:
            return new_state

        decision_memory = list(new_state.get("decision_memory", []))
        constraints_memory = dict(new_state.get("constraints_memory", {}))
        decision_memory.append(
            "SUPERVISOR: 후보 부족으로 검색 범위를 완화해 재검색"
        )
        constraints_memory["broaden_search"] = "true"
        new_state["decision_memory"] = decision_memory[-10:]
        new_state["constraints_memory"] = constraints_memory
        new_state["messages"].append(
            {
                "role": self.role,
                "content": "후보가 부족해 검색 범위를 완화하고 다시 찾습니다.",
            }
        )
        return new_state

    def route_next(self, state: DiningState) -> str:
        current_step = state.get("current_step", "")

        if not current_step:
            return AgentType.QUERY_PARSER

        if current_step == AgentType.QUERY_PARSER:
            return AgentType.PLACE_SEARCH

        if current_step == AgentType.PLACE_SEARCH:
            return AgentType.RAG_PROCESSOR

        if current_step == AgentType.RAG_PROCESSOR:
            if state.get("candidate_places"):
                return AgentType.RECOMMENDATION

            if state.get("search_iterations", 0) < state.get("max_search_iterations", 2):
                return AgentType.PLACE_SEARCH

            return AgentType.RECOMMENDATION

        if current_step == AgentType.RECOMMENDATION:
            return "END"

        return "END"

    def should_continue(self, state: DiningState) -> bool:
        return not state.get("completed", False)

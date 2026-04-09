"""Context analyzer for 오늘 뭐해?"""
from __future__ import annotations

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState


class ContextAnalyzerAgent:
    """Parses user input into structured outing context."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.CONTEXT_ANALYZER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)
        parsed = dict(state.get("parsed_context", {}))
        parsed.setdefault("intent", state.get("user_query", ""))
        parsed.setdefault("region", state.get("region", "서울"))
        parsed.setdefault("companion", state.get("companion", "상관없음"))
        parsed.setdefault("weather", state.get("weather", "상관없음"))
        parsed.setdefault("time_slot", state.get("time_slot", "상관없음"))
        parsed.setdefault("budget_level", state.get("budget_level", "상관없음"))
        parsed.setdefault("mobility", state.get("mobility", "상관없음"))

        new_state = state.copy()
        new_state["parsed_context"] = parsed
        new_state["current_step"] = self.role
        new_state["messages"].append(
            {"role": self.role, "content": f"상황 분석 완료: {parsed.get('region', '서울')} 중심으로 추천"}
        )
        decision_memory = list(new_state.get("decision_memory", []))
        decision_memory.append(
            f"CONTEXT_ANALYZER: region={parsed.get('region')}, companion={parsed.get('companion')}, weather={parsed.get('weather')}"
        )
        new_state["decision_memory"] = decision_memory[-12:]
        log_agent_output(self.logger, self.role, parsed)
        return new_state

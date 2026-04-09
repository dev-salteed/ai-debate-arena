"""Response composer for 오늘 뭐해?"""
from __future__ import annotations

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState


class ResponseComposerAgent:
    """Finalizes the response payload for UI and API."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.RESPONSE_COMPOSER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)
        new_state = state.copy()
        plan = dict(new_state.get("final_plan", {}))
        if "follow_up_prompt" not in plan:
            plan["follow_up_prompt"] = "지역이나 분위기를 바꿔서 다시 추천받아보세요."
        new_state["final_plan"] = plan
        new_state["current_step"] = self.role
        new_state["completed"] = True
        new_state["messages"].append(
            {"role": self.role, "content": "최종 응답 포맷 정리 완료"}
        )
        log_agent_output(self.logger, self.role, plan)
        return new_state

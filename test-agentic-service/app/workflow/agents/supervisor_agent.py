"""Supervisor Agent - 전체 워크플로우 제어"""
from workflow.state import TravelState, AgentType


class SupervisorAgent:
    """전체 여행 계획 프로세스를 관리하는 Supervisor"""

    def __init__(self):
        self.role = AgentType.SUPERVISOR

    def run(self, state: TravelState) -> TravelState:
        """
        분기 전 상태 정리.

        항공권 미가용 시 다음 추천 도시로 자동 전환하여
        다음 라우팅에서 재검색 브랜치가 동작하도록 만든다.
        """
        new_state = state.copy()
        current_step = state.get("current_step", "")

        if current_step != AgentType.FLIGHT_SEARCH:
            return new_state

        if state.get("flight_available", False):
            return new_state

        attempts = state.get("flight_search_attempts", 0)
        max_attempts = state.get("max_flight_search_attempts", 3)
        selected_index = state.get("selected_city_index", 0)
        recommended_cities = state.get("recommended_cities", [])

        has_next_city = selected_index + 1 < len(recommended_cities)
        can_retry = attempts < max_attempts
        decision_memory = list(new_state.get("decision_memory", []))
        constraints_memory = dict(new_state.get("constraints_memory", {}))
        reason = state.get("flight_unavailability_reason") or "미가용 사유 없음"

        if has_next_city and can_retry:
            next_index = selected_index + 1
            next_city = recommended_cities[next_index]
            new_state["selected_city_index"] = next_index
            new_state["selected_city"] = next_city
            new_state["messages"].append({
                "role": self.role,
                "content": (
                    "항공권 미가용으로 분기: "
                    f"{next_city.get('city', '다음 도시')}로 재검색합니다."
                ),
            })
            decision_memory.append(
                "SUPERVISOR: 항공권 미가용 분기 -> "
                f"{next_city.get('city', '다음 도시')} 재검색 (reason={reason})"
            )
            constraints_memory["last_flight_unavailability_reason"] = reason
        else:
            decision_memory.append(
                "SUPERVISOR: 재시도 조건 없음 -> 일정 단계 fallback "
                f"(reason={reason})"
            )

        new_state["decision_memory"] = decision_memory[-10:]
        new_state["constraints_memory"] = constraints_memory

        return new_state

    def route_next(self, state: TravelState) -> str:
        """다음 실행할 에이전트 결정"""

        current_step = state.get("current_step", "")

        # 초기 상태: 도시 추천부터 시작
        if not current_step:
            return AgentType.CITY_RECOMMENDER

        # 도시 추천 완료 → 항공권 검색
        if current_step == AgentType.CITY_RECOMMENDER:
            return AgentType.FLIGHT_SEARCH

        # 항공권 검색 완료:
        # - 가용이면 일정 계획
        # - 미가용이면 조건에 따라 재검색 또는 일정 계획(보수적 fallback)
        if current_step == AgentType.FLIGHT_SEARCH:
            if state.get("flight_available", False):
                return AgentType.ITINERARY_PLANNER

            attempts = state.get("flight_search_attempts", 0)
            max_attempts = state.get("max_flight_search_attempts", 3)
            if attempts < max_attempts:
                return AgentType.FLIGHT_SEARCH

            # 더 이상 재시도 조건이 없으면 일정 단계로 진행
            return AgentType.ITINERARY_PLANNER

        # 모든 단계 완료 → 종료
        if current_step == AgentType.ITINERARY_PLANNER:
            return "END"

        return "END"

    def should_continue(self, state: TravelState) -> bool:
        """계속 진행할지 여부 판단"""
        return not state.get("completed", False)

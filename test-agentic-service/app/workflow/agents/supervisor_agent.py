"""Supervisor Agent - 전체 워크플로우 제어"""
from workflow.state import TravelState, AgentType


class SupervisorAgent:
    """전체 여행 계획 프로세스를 관리하는 Supervisor"""

    def __init__(self):
        self.role = AgentType.SUPERVISOR

    def route_next(self, state: TravelState) -> str:
        """다음 실행할 에이전트 결정"""
        
        current_step = state.get("current_step", "")
        
        # 초기 상태: 도시 추천부터 시작
        if not current_step:
            return AgentType.CITY_RECOMMENDER
        
        # 도시 추천 완료 → 항공권 검색
        if current_step == AgentType.CITY_RECOMMENDER:
            return AgentType.FLIGHT_SEARCH
        
        # 항공권 검색 완료 → 일정 계획
        if current_step == AgentType.FLIGHT_SEARCH:
            return AgentType.ITINERARY_PLANNER
        
        # 모든 단계 완료 → 종료
        if current_step == AgentType.ITINERARY_PLANNER:
            return "END"
        
        return "END"

    def should_continue(self, state: TravelState) -> bool:
        """계속 진행할지 여부 판단"""
        return not state.get("completed", False)

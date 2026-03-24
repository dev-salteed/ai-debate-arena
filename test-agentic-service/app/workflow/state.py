# LangGraph 상태 정의 - 여행 계획 에이전틱 서비스
from typing import Dict, List, TypedDict, Optional


class AgentType:
    SUPERVISOR = "SUPERVISOR"
    CITY_RECOMMENDER = "CITY_RECOMMENDER"
    FLIGHT_SEARCH = "FLIGHT_SEARCH"
    ITINERARY_PLANNER = "ITINERARY_PLANNER"

    @classmethod
    def to_korean(cls, role: str) -> str:
        mapping = {
            cls.SUPERVISOR: "총괄",
            cls.CITY_RECOMMENDER: "도시 추천",
            cls.FLIGHT_SEARCH: "항공권 검색",
            cls.ITINERARY_PLANNER: "일정 계획",
        }
        return mapping.get(role, role)


class TravelState(TypedDict):
    # 입력 정보
    travel_theme: str  # 여행 주제
    travel_days: Optional[int]  # 여행 일수
    budget: Optional[int]  # 예산 (KRW)
    departure_city: str  # 출발 도시 (기본: 서울)
    
    # 각 에이전트 결과
    recommended_cities: List[Dict]  # 추천 도시 목록
    selected_city: Optional[Dict]  # 선택된 도시
    flight_info: Optional[Dict]  # 항공권 정보
    flight_available: bool  # 항공권 가용 여부
    flight_unavailability_reason: Optional[str]  # 미가용 사유
    selected_city_index: int  # 현재 선택된 도시 인덱스
    flight_search_attempts: int  # 항공권 검색 시도 횟수
    max_flight_search_attempts: int  # 최대 재시도 횟수
    itinerary: Optional[Dict]  # 여행 일정 + 예산
    
    # 진행 상태
    current_step: str  # 현재 진행 단계
    messages: List[Dict]  # 각 에이전트의 메시지 로그
    completed: bool  # 완료 여부

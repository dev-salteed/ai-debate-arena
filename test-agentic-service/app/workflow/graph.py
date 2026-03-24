"""여행 계획 에이전틱 서비스 - LangGraph 워크플로우"""
from workflow.agents.city_recommender_agent import CityRecommenderAgent
from workflow.agents.flight_search_agent import FlightSearchAgent
from workflow.agents.itinerary_agent import ItineraryAgent
from workflow.agents.supervisor_agent import SupervisorAgent
from workflow.state import TravelState, AgentType
from langgraph.graph import StateGraph, END


def create_travel_graph(enable_rag: bool = True):
    """
    여행 계획 그래프 생성
    
    Args:
        enable_rag: RAG 활성화 여부
    """
    
    # 그래프 생성
    workflow = StateGraph(TravelState)
    
    # 에이전트 인스턴스 생성 (RAG 옵션 전달)
    city_recommender = CityRecommenderAgent(enable_rag=enable_rag)
    flight_search = FlightSearchAgent(enable_rag=enable_rag)
    itinerary_planner = ItineraryAgent(enable_rag=enable_rag)
    supervisor = SupervisorAgent()
    
    # 노드 추가
    workflow.add_node(AgentType.SUPERVISOR, supervisor.run)
    workflow.add_node(AgentType.CITY_RECOMMENDER, city_recommender.run)
    workflow.add_node(AgentType.FLIGHT_SEARCH, flight_search.run)
    workflow.add_node(AgentType.ITINERARY_PLANNER, itinerary_planner.run)

    # 각 작업 노드 실행 후 항상 Supervisor로 돌아가서 다음 분기를 결정한다.
    workflow.add_edge(AgentType.CITY_RECOMMENDER, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.FLIGHT_SEARCH, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.ITINERARY_PLANNER, AgentType.SUPERVISOR)

    # Supervisor 조건 분기
    workflow.add_conditional_edges(
        AgentType.SUPERVISOR,
        supervisor.route_next,
        {
            AgentType.CITY_RECOMMENDER: AgentType.CITY_RECOMMENDER,
            AgentType.FLIGHT_SEARCH: AgentType.FLIGHT_SEARCH,
            AgentType.ITINERARY_PLANNER: AgentType.ITINERARY_PLANNER,
            "END": END,
        },
    )

    # 시작 지점 설정
    workflow.set_entry_point(AgentType.SUPERVISOR)
    
    # 그래프 컴파일
    return workflow.compile()


if __name__ == "__main__":
    """그래프 시각화"""
    import logging
    
    # 로깅 설정
    logging.basicConfig(level=logging.INFO)
    
    graph = create_travel_graph(enable_rag=True)
    
    try:
        graph_image = graph.get_graph().draw_mermaid_png()
        output_path = "travel_graph.png"
        with open(output_path, "wb") as f:
            f.write(graph_image)
        print(f"그래프 이미지 저장 완료: {output_path}")
    except Exception as e:
        print(f"그래프 시각화 실패: {e}")

"""저기어때 - 여행 계획 에이전틱 서비스"""
import streamlit as st
import logging
import uuid
from workflow.graph import create_travel_graph
from workflow.state import TravelState, AgentType


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def initialize_state():
    """세션 상태 초기화"""
    if "travel_plan" not in st.session_state:
        st.session_state.travel_plan = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "logs" not in st.session_state:
        st.session_state.logs = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "continued_last_run" not in st.session_state:
        st.session_state.continued_last_run = False
    if "workflow_graph" not in st.session_state:
        st.session_state.workflow_graph = None
    if "workflow_graph_rag" not in st.session_state:
        st.session_state.workflow_graph_rag = None


def build_initial_state(
    travel_theme: str,
    travel_days: int,
    budget: int,
    departure_city: str,
) -> TravelState:
    """새 계획 생성용 초기 상태."""
    return TravelState(
        travel_theme=travel_theme,
        travel_days=travel_days if travel_days > 0 else None,
        budget=budget if budget > 0 else None,
        departure_city=departure_city,
        recommended_cities=[],
        selected_city=None,
        selected_city_index=0,
        flight_info=None,
        flight_available=False,
        flight_unavailability_reason=None,
        flight_search_attempts=0,
        max_flight_search_attempts=3,
        itinerary=None,
        decision_memory=[],
        constraints_memory={},
        current_step="",
        messages=[],
        completed=False,
    )


def build_continued_state(
    previous_state: TravelState,
    travel_theme: str,
    travel_days: int,
    budget: int,
    departure_city: str,
) -> TravelState:
    """이전 상태를 기반으로 입력 조건을 반영해 재실행 상태를 만든다."""
    continued = dict(previous_state)
    continued["travel_theme"] = travel_theme
    continued["travel_days"] = travel_days if travel_days > 0 else None
    continued["budget"] = budget if budget > 0 else None
    continued["departure_city"] = departure_city
    continued["current_step"] = ""
    continued["completed"] = False
    return continued


def get_or_create_workflow_graph(enable_rag: bool):
    """RAG 모드별 그래프를 세션에 캐시한다."""
    if (
        st.session_state.workflow_graph is None
        or st.session_state.workflow_graph_rag != enable_rag
    ):
        st.session_state.workflow_graph = create_travel_graph(enable_rag=enable_rag)
        st.session_state.workflow_graph_rag = enable_rag
    return st.session_state.workflow_graph


def main():
    """메인 애플리케이션"""
    
    # 초기 상태 설정
    initialize_state()
    
    # 페이지 설정
    st.set_page_config(
        page_title="저기어때 - 여행 계획 서비스",
        page_icon="✈️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # 제목
    st.title("✈️ 저기어때")
    st.markdown("#### 당신의 여행 주제만 알려주세요. 나머지는 저희가 계획해드립니다!")
    
    # 사이드바: 입력 폼
    with st.sidebar:
        st.markdown("### 여행 정보 입력")
        
        with st.form("travel_form"):
            travel_theme = st.text_input(
                "여행 주제 *",
                placeholder="예: 해변에서 휴양",
                help="어떤 테마의 여행을 원하시나요?"
            )
            
            travel_days = st.number_input(
                "여행 일수",
                min_value=1,
                max_value=30,
                value=5,
                help="며칠간 여행하실 계획인가요?"
            )
            
            budget = st.number_input(
                "예산 (선택, 원 단위)",
                min_value=0,
                value=0,
                step=100000,
                help="총 여행 예산을 입력하세요 (0이면 자동 계산)"
            )
            
            departure_city = st.text_input(
                "출발 도시",
                value="서울",
                help="어디서 출발하시나요?"
            )
            
            enable_rag = st.checkbox(
                "🔍 RAG 활성화",
                value=True,
                help="외부 지식을 검색하여 여행 계획에 활용합니다."
            )

            continue_mode = st.checkbox(
                "이어서 계획 수정/재실행",
                value=False,
                disabled=st.session_state.travel_plan is None,
                help="동일 thread_id로 이전 실행 맥락을 이어서 다시 계획합니다.",
            )
            
            submitted = st.form_submit_button("여행 계획 시작", use_container_width=True)
        
        # 정보 안내
        st.markdown("---")
        st.markdown("### 🎯 서비스 특징")
        st.markdown("""
        - 🌍 여행 도시 자동 추천
        - ✈️ 항공권 검색
        - 📅 일정 계획
        - 💰 예산 분배
        - 🔍 RAG 기반 실시간 정보
        """)
        
        # 로그 표시
        if st.session_state.get("logs"):
            with st.expander("📋 실행 로그 보기", expanded=False):
                for log in st.session_state.logs[-50:]:  # 최근 50개만
                    st.text(log)
    
    # 메인 화면
    if submitted:
        if not travel_theme:
            st.warning("여행 주제를 입력해주세요!")
        else:
            # 여행 계획 실행
            rag_status = "활성화" if enable_rag else "비활성화"
            with st.spinner(f"여행 계획을 생성하고 있습니다... (RAG: {rag_status})"):
                try:
                    # 로그 수집을 위한 핸들러
                    class StreamlitLogHandler(logging.Handler):
                        def emit(self, record):
                            log_entry = self.format(record)
                            if "logs" in st.session_state:
                                st.session_state.logs.append(log_entry)
                    
                    # 로그 핸들러 추가
                    handler = StreamlitLogHandler()
                    handler.setFormatter(logging.Formatter(
                        '[%(asctime)s] [%(levelname)s] %(message)s',
                        datefmt='%H:%M:%S'
                    ))
                    logging.getLogger().addHandler(handler)
                    
                    # 로그 초기화
                    st.session_state.logs = []
                    
                    logging.info(f"{'='*60}")
                    logging.info(f"여행 계획 생성 시작")
                    logging.info(f"주제: {travel_theme}, 일수: {travel_days}일, RAG: {rag_status}")
                    logging.info(f"{'='*60}")

                    # 초기/연속 실행 상태 구성
                    if continue_mode and st.session_state.travel_plan:
                        thread_id = st.session_state.thread_id or str(uuid.uuid4())
                        initial_state = build_continued_state(
                            previous_state=st.session_state.travel_plan,
                            travel_theme=travel_theme,
                            travel_days=travel_days,
                            budget=budget,
                            departure_city=departure_city,
                        )
                        st.session_state.continued_last_run = True
                    else:
                        thread_id = str(uuid.uuid4())
                        initial_state = build_initial_state(
                            travel_theme=travel_theme,
                            travel_days=travel_days,
                            budget=budget,
                            departure_city=departure_city,
                        )
                        st.session_state.continued_last_run = False
                    st.session_state.thread_id = thread_id

                    # 그래프 생성 및 실행
                    graph = get_or_create_workflow_graph(enable_rag=enable_rag)
                    final_state = graph.invoke(
                        initial_state,
                        config={"configurable": {"thread_id": thread_id}},
                    )
                    
                    logging.info(f"{'='*60}")
                    logging.info(f"여행 계획 생성 완료!")
                    logging.info(f"{'='*60}")
                    
                    # 결과 저장
                    st.session_state.travel_plan = final_state
                    st.session_state.messages = final_state["messages"]
                    
                    # 로그 핸들러 제거
                    logging.getLogger().removeHandler(handler)
                    
                    st.success("여행 계획이 완성되었습니다! 🎉")
                    st.rerun()
                    
                except Exception as e:
                    logging.error(f"오류 발생: {str(e)}", exc_info=True)
                    st.error(f"여행 계획 생성 중 오류가 발생했습니다: {str(e)}")
    
    # 결과 표시
    if st.session_state.travel_plan:
        plan = st.session_state.travel_plan
        
        st.markdown("---")
        st.markdown("## 📋 여행 계획 결과")
        if st.session_state.thread_id:
            continued_text = "예" if st.session_state.continued_last_run else "아니오"
            st.caption(
                f"Thread ID: `{st.session_state.thread_id}` | 연속 실행: {continued_text}"
            )
        
        # 1. 추천 도시
        st.markdown("### 🌍 추천 여행 도시")
        cities = plan.get("recommended_cities", [])
        if cities:
            for i, city in enumerate(cities, 1):
                with st.expander(f"{i}. {city['city']}, {city['country']}", expanded=(i==1)):
                    st.markdown(f"**추천 이유:** {city['reason']}")
            
            # 선택된 도시 강조
            selected = plan.get("selected_city")
            if selected:
                st.info(f"✅ **선택된 도시**: {selected['city']}, {selected['country']}")
        else:
            st.warning("추천 도시 정보가 없습니다.")
        
        st.markdown("---")
        
        # 2. 항공권
        st.markdown("### ✈️ 항공권 정보")
        flight = plan.get("flight_info")
        flight_available = plan.get("flight_available", True)
        unavailable_reason = plan.get("flight_unavailability_reason")
        if not flight_available and unavailable_reason:
            st.warning(f"항공권 가용성 이슈로 분기됨: {unavailable_reason}")
        if flight:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("항공사", flight.get("airline", "N/A"))
                st.metric("출발 공항", flight.get("departure_airport", "N/A"))
                st.metric("출발일", flight.get("departure_date", "N/A"))
            with col2:
                price = flight.get("price", 0)
                st.metric("항공권 가격", f"{price:,}원")
                st.metric("도착 공항", flight.get("arrival_airport", "N/A"))
                st.metric("귀국일", flight.get("return_date", "N/A"))
        else:
            st.warning("항공권 정보가 없습니다.")
        
        st.markdown("---")
        
        # 3. 일정
        st.markdown("### 📅 여행 일정")
        itinerary_data = plan.get("itinerary", {})
        itinerary = itinerary_data.get("itinerary", [])
        if itinerary:
            for day_plan in itinerary:
                day = day_plan.get("day", 0)
                plan_text = day_plan.get("plan", "")
                with st.expander(f"Day {day}", expanded=True):
                    st.markdown(plan_text)
        else:
            st.warning("일정 정보가 없습니다.")
        
        st.markdown("---")
        
        # 4. 예산
        st.markdown("### 💰 예산 분배")
        itinerary_data = plan.get("itinerary", {})
        budget_breakdown = itinerary_data.get("budget_breakdown", {})
        if budget_breakdown:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.metric("✈️ 항공권", f"{budget_breakdown.get('flight', 0):,}원")
                st.metric("🏨 숙소", f"{budget_breakdown.get('accommodation', 0):,}원")
                st.metric("🍽️ 식비", f"{budget_breakdown.get('food', 0):,}원")
                st.metric("🎫 기타", f"{budget_breakdown.get('others', 0):,}원")
            with col2:
                total = budget_breakdown.get('total', 0)
                st.metric("💰 총 예산", f"{total:,}원", delta=None)
        else:
            st.warning("예산 정보가 없습니다.")
        
        # 초기화 버튼
        st.markdown("---")
        if st.button("새로운 여행 계획하기", use_container_width=True):
            st.session_state.travel_plan = None
            st.session_state.messages = []
            st.session_state.thread_id = None
            st.session_state.continued_last_run = False
            st.rerun()
    
    else:
        # 안내 메시지
        st.markdown("---")
        st.markdown("### 👈 왼쪽 사이드바에서 여행 정보를 입력하고 시작하세요!")
        st.markdown("""
        **저기어때**는 여러분의 여행 주제를 기반으로:
        1. 🌍 최적의 여행 도시를 추천하고
        2. ✈️ 항공권 정보를 찾아드리며
        3. 📅 상세한 여행 일정을 계획하고
        4. 💰 예산을 합리적으로 분배해드립니다
        
        간단한 입력만으로 완벽한 여행 계획을 받아보세요!
        """)


if __name__ == "__main__":
    main()

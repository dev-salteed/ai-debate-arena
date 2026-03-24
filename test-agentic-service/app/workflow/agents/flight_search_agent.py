"""항공권 검색 에이전트 - Agent B"""
import json
from datetime import datetime, timedelta
from typing import Dict
from langchain_core.messages import HumanMessage, SystemMessage
from utils.config import get_llm
from utils.logger import setup_logger, log_agent_input, log_agent_output
from retrieval.search_service import search_web_tool
from workflow.state import TravelState, AgentType
from workflow.agents.tool_runner import invoke_with_tool_calls


class FlightSearchAgent:
    """항공권을 검색하는 에이전트 (RAG 지원)"""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.FLIGHT_SEARCH
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        
        self.system_prompt = """당신은 항공권 검색 전문가입니다.
주어진 정보를 바탕으로 적절한 왕복 항공권 1개를 추천해주세요.

{rag_instruction}

응답은 반드시 다음 JSON 형식으로 작성하세요:
{{
  "flight": {{
    "departure_airport": "ICN",
    "arrival_airport": "공항코드",
    "departure_date": "YYYY-MM-DD",
    "return_date": "YYYY-MM-DD",
    "airline": "항공사명",
    "price": 1000000
  }}
}}

주의사항:
- 정확한 JSON 형식을 유지하세요
- price는 숫자로 입력하세요 (KRW 단위)
- 실제 항공사명을 사용하세요 (대한항공, 아시아나항공, 진에어 등)
- 공항 코드는 IATA 3자리 코드를 사용하세요
"""
        self.unavailability_keywords = [
            "항공편 없음",
            "운항 없음",
            "예약 불가",
            "매진",
            "no flights",
            "not available",
            "sold out",
            "unavailable",
            "운휴",
        ]
        self.availability_signal_keywords = [
            "예약 가능 여부",
            "운항 현황",
            "출도착",
            "항공편",
            "스케줄",
            "availability",
        ]

    def run(self, state: TravelState) -> TravelState:
        """항공권 검색 실행"""
        
        # 입력 로깅
        log_agent_input(self.logger, self.role, state)
        
        # 날짜 계산
        departure_date, return_date = self._calculate_dates(state)
        self.logger.info(f"[날짜 계산] 출발: {departure_date}, 귀국: {return_date}")
        
        search_context = ""
        
        # 프롬프트 생성
        prompt = self._create_prompt(state, departure_date, return_date, search_context)
        
        # 시스템 프롬프트에 RAG 안내 추가
        rag_instruction = ""
        if self.enable_rag:
            rag_instruction = (
                "최신 운항/가격 정보가 필요하면 search_web 도구를 1회 이상 호출해 확인하세요."
            )
        else:
            rag_instruction = "도구를 사용하지 말고 일반적인 항공권 가격을 고려해 추천해주세요."

        system_prompt = self.system_prompt.format(rag_instruction=rag_instruction)

        # LLM + Tool 호출
        self.logger.info(f"[LLM] 호출 시작 (프롬프트 길이: {len(prompt)} 문자)")
        if self.enable_rag:
            response_text = invoke_with_tool_calls(
                system_prompt=system_prompt,
                user_prompt=prompt,
                tools=[search_web_tool],
                logger=self.logger,
            )
        else:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt),
            ]
            response = get_llm().invoke(messages)
            response_text = response.content.strip()

        self.logger.info(f"[LLM] 응답 받음 (길이: {len(response_text)} 문자)")
        
        # JSON 파싱
        try:
            # JSON 블록 추출
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            self.logger.info("[파싱] JSON 추출 완료")
            result = json.loads(response_text)
            flight_info = result.get("flight", {})
            self.logger.info(f"[파싱] 항공권 정보 추출 성공: {flight_info.get('airline', 'N/A')}")
        except json.JSONDecodeError as e:
            self.logger.error(f"[파싱 오류] {e}")
            self.logger.error(f"응답: {response_text[:200]}...")
            flight_info = {}
        
        # 상태 업데이트
        new_state = state.copy()
        flight_available, unavailability_reason = self._evaluate_availability(
            flight_info=flight_info,
            search_context=search_context,
        )

        new_state["flight_info"] = flight_info if flight_available else None
        new_state["flight_available"] = flight_available
        new_state["flight_unavailability_reason"] = (
            unavailability_reason if not flight_available else None
        )
        new_state["flight_search_attempts"] = state.get("flight_search_attempts", 0) + 1
        new_state["current_step"] = AgentType.FLIGHT_SEARCH
        
        if flight_available and flight_info:
            price_text = f"{flight_info.get('price', 0):,}원"
            new_state["messages"].append({
                "role": self.role,
                "content": f"항공권 검색 완료: {flight_info.get('airline')} ({price_text})"
            })
            self.logger.info(f"[완료] 항공권: {flight_info.get('airline')}, 가격: {price_text}")
        else:
            reason = unavailability_reason or "가용 항공권을 확인하지 못했습니다."
            new_state["messages"].append({
                "role": self.role,
                "content": f"항공권 미가용 판단: {reason}"
            })
            self.logger.warning(f"[미가용] {reason}")
        
        # 출력 로깅
        log_agent_output(self.logger, self.role, flight_info)
        
        return new_state

    def _evaluate_availability(self, flight_info: Dict, search_context: str) -> tuple[bool, str]:
        """
        항공권 가용성 평가.

        Returns:
            (가용 여부, 미가용 사유)
        """
        if not flight_info:
            return False, "항공권 결과가 비어 있습니다."

        required_fields = [
            "departure_airport",
            "arrival_airport",
            "departure_date",
            "return_date",
            "airline",
            "price",
        ]
        missing = [
            field
            for field in required_fields
            if field not in flight_info or flight_info.get(field) in (None, "")
        ]
        if missing:
            return False, f"필수 항공권 필드 누락: {', '.join(missing)}"

        price = flight_info.get("price", 0)
        if not isinstance(price, (int, float)) or price <= 0:
            return False, "항공권 가격이 유효하지 않습니다."

        # 검색 컨텍스트에 강한 미가용 신호가 있으면 우선 미가용으로 판단.
        if search_context:
            context_lower = search_context.lower()
            matched = [kw for kw in self.unavailability_keywords if kw.lower() in context_lower]
            if matched:
                return False, f"검색 결과에서 미가용 신호 감지: {matched[0]}"

        return True, ""

    def _collect_availability_signals(self, search_context: str) -> list[str]:
        """검색 컨텍스트의 가용성 관련 키워드 추출."""
        if not search_context:
            return []
        lowered = search_context.lower()
        return [kw for kw in self.availability_signal_keywords if kw.lower() in lowered]

    def _calculate_dates(self, state: TravelState) -> tuple:
        """여행 날짜 계산"""
        # 출발일 = 오늘 + 30일
        departure_date = datetime.now() + timedelta(days=30)
        
        # 귀국일 = 출발일 + 여행 일수
        travel_days = state.get("travel_days", 5)  # 기본 5일
        return_date = departure_date + timedelta(days=travel_days)
        
        return departure_date.strftime("%Y-%m-%d"), return_date.strftime("%Y-%m-%d")

    def _create_prompt(self, state: TravelState, departure_date: str, return_date: str, search_context: str = "") -> str:
        """프롬프트 생성"""
        selected_city = state.get("selected_city", {})
        
        prompt = f"""출발 도시: {state.get('departure_city', '서울')}
도착 도시: {selected_city.get('city', '알 수 없음')}
국가: {selected_city.get('country', '알 수 없음')}
출발일: {departure_date}
귀국일: {return_date}
여행 일수: {state.get('travel_days', 5)}일

"""
        
        if self.enable_rag:
            tool_query = (
                f"서울 {selected_city.get('city', '')} 항공권 운항 여부 예약 가능 여부 평균 가격 항공사"
            )
            prompt += (
                "웹 검색이 필요하면 search_web 도구를 사용하세요.\n"
                f"권장 검색어: {tool_query}\n"
            )
        elif search_context:
            prompt += f"{search_context}\n"
        
        prompt += """위 정보를 바탕으로 적절한 왕복 항공권을 추천해주세요.
항공권 가격은 현실적인 가격을 제시하세요.
"""
        
        return prompt

"""일정 + 예산 계획 에이전트 - Agent C"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from utils.config import get_llm
from utils.logger import setup_logger, log_agent_input, log_agent_output
from retrieval.search_service import search_web_tool
from workflow.state import TravelState, AgentType
from workflow.agents.tool_runner import invoke_with_tool_calls


class ItineraryAgent:
    """여행 일정과 예산을 계획하는 에이전트 (RAG 지원)"""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.ITINERARY_PLANNER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        
        self.system_prompt = """당신은 여행 일정 계획 전문가입니다.
주어진 정보를 바탕으로 Day별 여행 일정과 예산 분배를 계획해주세요.

{rag_instruction}

응답은 반드시 다음 JSON 형식으로 작성하세요:
{{
  "itinerary": [
    {{"day": 1, "plan": "첫날 일정 설명"}},
    {{"day": 2, "plan": "둘째날 일정 설명"}}
  ],
  "budget_breakdown": {{
    "flight": 1000000,
    "accommodation": 500000,
    "food": 300000,
    "others": 200000,
    "total": 2000000
  }}
}}

주의사항:
- 정확한 JSON 형식을 유지하세요
- 모든 금액은 숫자로 입력하세요 (KRW 단위)
- total은 flight + accommodation + food + others의 합계여야 합니다
- 각 day의 plan은 구체적이고 실현 가능한 일정으로 작성하세요
"""

    def run(self, state: TravelState) -> TravelState:
        """일정 + 예산 계획 실행"""
        
        # 입력 로깅
        log_agent_input(self.logger, self.role, state)

        # 프롬프트 생성
        prompt = self._create_prompt(state)

        # 시스템 프롬프트에 RAG 안내 추가
        rag_instruction = ""
        if self.enable_rag:
            rag_instruction = (
                "최신 명소/식당 정보가 필요하면 search_web 도구를 1회 이상 호출해 반영하세요."
            )
        else:
            rag_instruction = "도구를 사용하지 말고 일반적인 여행 정보를 바탕으로 일정을 계획해주세요."

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
            itinerary_data = result
            
            itinerary = itinerary_data.get("itinerary", [])
            budget = itinerary_data.get("budget_breakdown", {})
            self.logger.info(f"[파싱] 일정 {len(itinerary)}일, 총 예산 {budget.get('total', 0):,}원 추출 성공")
        except json.JSONDecodeError as e:
            self.logger.error(f"[파싱 오류] {e}")
            self.logger.error(f"응답: {response_text[:200]}...")
            itinerary_data = {}
        
        # 상태 업데이트
        new_state = state.copy()
        new_state["itinerary"] = itinerary_data
        new_state["current_step"] = AgentType.ITINERARY_PLANNER
        new_state["completed"] = True
        
        if itinerary_data:
            budget = itinerary_data.get("budget_breakdown", {})
            total = budget.get("total", 0)
            new_state["messages"].append({
                "role": self.role,
                "content": f"여행 일정 및 예산 계획 완료 (총 예산: {total:,}원)"
            })
            self.logger.info(f"[완료] 총 예산: {total:,}원")
        
        # 출력 로깅
        log_agent_output(self.logger, self.role, itinerary_data)
        
        return new_state

    def _create_prompt(self, state: TravelState) -> str:
        """프롬프트 생성"""
        selected_city = state.get("selected_city", {})
        flight_info = state.get("flight_info", {})
        travel_days = state.get("travel_days", 5)
        budget = state.get("budget")
        
        prompt = f"""여행지: {selected_city.get('city', '알 수 없음')}, {selected_city.get('country', '알 수 없음')}
여행 주제: {state.get('travel_theme', '알 수 없음')}
여행 일수: {travel_days}일

항공권 정보:
- 항공사: {flight_info.get('airline', '알 수 없음')}
- 출발일: {flight_info.get('departure_date', '알 수 없음')}
- 귀국일: {flight_info.get('return_date', '알 수 없음')}
- 항공권 가격: {flight_info.get('price', 0):,}원

"""
        
        if self.enable_rag:
            tool_query = (
                f"{selected_city.get('city', '')} {state.get('travel_theme', '')} 여행 일정 추천 명소 맛집"
            )
            prompt += (
                "웹 검색이 필요하면 search_web 도구를 사용하세요.\n"
                f"권장 검색어: {tool_query}\n"
            )
        
        if budget:
            prompt += f"\n전체 예산: {budget:,}원 (항공권 포함)"
        else:
            prompt += f"\n전체 예산: 항공권 가격을 기준으로 적절하게 계산해주세요"
        
        prompt += f"""

위 정보를 바탕으로:
1. Day 1부터 Day {travel_days}까지의 구체적인 일정을 작성해주세요
2. 예산을 항공권, 숙소, 식비, 기타로 분배해주세요
3. 항공권 가격은 {flight_info.get('price', 0):,}원으로 이미 정해져 있습니다
"""
        
        return prompt

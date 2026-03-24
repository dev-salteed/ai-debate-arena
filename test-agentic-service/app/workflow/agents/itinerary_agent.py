"""일정 + 예산 계획 에이전트 - Agent C"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from utils.config import get_llm
from utils.logger import setup_logger, log_agent_input, log_agent_output
from retrieval.search_service import search_web_tool
from workflow.state import TravelState, AgentType
from workflow.agents.tool_runner import invoke_with_tool_calls
from workflow.agents.response_guard import parse_json, missing_required_keys


class ItineraryAgent:
    """여행 일정과 예산을 계획하는 에이전트 (RAG 지원)"""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.ITINERARY_PLANNER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        
        self.system_prompt = """당신은 여행 일정 계획 전문가입니다.
주어진 정보를 바탕으로 Day별 여행 일정과 예산 분배를 계획해주세요.

{rag_instruction}

Few-shot 예시:
입력: 여행지=도쿄, 여행일수=3일, 항공권=420000
출력:
{{
  "rationale": "동선 밀집도와 식사 피크 시간 회피를 기준으로 일정과 예산을 구성했습니다.",
  "itinerary": [
    {{"day": 1, "plan": "도착 후 체크인 및 근거리 산책"}},
    {{"day": 2, "plan": "핵심 명소 2곳 + 저녁 미식 코스"}},
    {{"day": 3, "plan": "체크아웃 전 가벼운 일정 후 공항 이동"}}
  ],
  "budget_breakdown": {{
    "flight": 420000,
    "accommodation": 480000,
    "food": 240000,
    "others": 160000,
    "total": 1300000
  }}
}}

응답은 반드시 다음 JSON 형식으로 작성하세요:
{{
  "rationale": "일정/예산 구성 근거 한 문장",
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
- 입력이 모호하거나 부족하면 합리적 가정을 `rationale`에 명시하세요
- 필수 키 누락 시 JSON을 1회 자가 보정해 완전한 형태로 출력하세요
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
        
        # JSON 파싱 + 누락 키 보정 1회
        try:
            result, cleaned_text = parse_json(response_text)
            missing = missing_required_keys(result, ["itinerary", "budget_breakdown", "rationale"])
            if missing:
                self.logger.warning(f"[파싱] 필수 키 누락 감지: {missing}, 보정 1회 시도")
                repaired_text = self._repair_json_once(cleaned_text, missing)
                result, _ = parse_json(repaired_text)

            self.logger.info("[파싱] JSON 추출 완료")
            itinerary_data = result
            itinerary = itinerary_data.get("itinerary", [])
            budget = itinerary_data.get("budget_breakdown", {})
            self.logger.info(f"[파싱] 일정 {len(itinerary)}일, 총 예산 {budget.get('total', 0):,}원 추출 성공")
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"[파싱 오류] {e}")
            self.logger.error(f"응답: {response_text[:200]}...")
            itinerary_data = {}
        
        # 상태 업데이트
        new_state = state.copy()
        new_state["itinerary"] = itinerary_data
        new_state["current_step"] = AgentType.ITINERARY_PLANNER
        new_state["completed"] = True
        decision_memory = list(new_state.get("decision_memory", []))
        
        if itinerary_data:
            budget = itinerary_data.get("budget_breakdown", {})
            total = budget.get("total", 0)
            new_state["messages"].append({
                "role": self.role,
                "content": f"여행 일정 및 예산 계획 완료 (총 예산: {total:,}원)"
            })
            self.logger.info(f"[완료] 총 예산: {total:,}원")
            decision_memory.append(
                f"ITINERARY_PLANNER: 일정/예산 완료 (total={total:,}원)"
            )
        new_state["decision_memory"] = decision_memory[-10:]
        
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

        constraints_memory = state.get("constraints_memory", {})
        decision_memory = state.get("decision_memory", [])
        if constraints_memory:
            prompt += "\n[제약조건 메모리]\n"
            for key, value in constraints_memory.items():
                prompt += f"- {key}: {value}\n"
        if decision_memory:
            prompt += "\n[최근 의사결정 메모리]\n"
            for item in decision_memory[-3:]:
                prompt += f"- {item}\n"
        
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

    def _repair_json_once(self, broken_json: str, missing_keys: list[str]) -> str:
        """누락된 필수 키를 보정하기 위해 LLM에 JSON 리페어를 1회 요청한다."""
        repair_system = (
            "당신은 JSON 리페어 도우미입니다. "
            "반드시 유효한 JSON만 출력하고 설명문은 금지합니다."
        )
        repair_prompt = f"""다음 JSON 응답에서 필수 키를 보정하세요.
필수 키: {", ".join(missing_keys)}

원본:
{broken_json}
"""
        response = get_llm().invoke(
            [SystemMessage(content=repair_system), HumanMessage(content=repair_prompt)]
        )
        return str(response.content).strip()

"""도시 추천 에이전트 - Agent A"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from utils.config import get_llm
from utils.logger import setup_logger, log_agent_input, log_agent_output
from retrieval.search_service import search_city_context_tool
from workflow.state import TravelState, AgentType
from workflow.agents.tool_runner import invoke_with_tool_calls
from workflow.agents.response_guard import parse_json, missing_required_keys


class CityRecommenderAgent:
    """여행 주제에 맞는 해외 도시를 추천하는 에이전트 (RAG 지원)"""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.CITY_RECOMMENDER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        
        self.system_prompt = """당신은 전문 여행 컨설턴트입니다.
사용자의 여행 주제에 가장 적합한 해외 도시 2~3개를 추천해주세요.

{rag_instruction}

Few-shot 예시 1:
입력: 여행 주제=미식 여행, 여행 일수=4일, 예산=1500000
출력:
{{
  "rationale": "겨울 미식 접근성과 이동 동선을 고려해 단거리 도시를 우선 추천했습니다.",
  "recommended_cities": [
    {{"city": "도쿄", "country": "일본", "reason": "시장/이자카야 중심 미식 동선이 좋습니다."}},
    {{"city": "오사카", "country": "일본", "reason": "현지 음식 밀집 지역이 풍부합니다."}}
  ]
}}

Few-shot 예시 2:
입력: 여행 주제=휴양, 여행 일수=5일, 예산=2000000
출력:
{{
  "rationale": "휴양 중심과 예산 균형을 기준으로 해변 접근성이 높은 도시를 골랐습니다.",
  "recommended_cities": [
    {{"city": "발리", "country": "인도네시아", "reason": "휴양/스파/리조트 선택지가 넓습니다."}},
    {{"city": "푸켓", "country": "태국", "reason": "비용 대비 해변 품질이 우수합니다."}}
  ]
}}

응답은 반드시 다음 JSON 형식으로 작성하세요:
{{
  "rationale": "추천 근거 한 문장",
  "recommended_cities": [
    {{
      "city": "도시명",
      "country": "국가명",
      "reason": "추천 이유 한 문장"
    }}
  ]
}}

주의사항:
- 정확한 JSON 형식을 유지하세요
- 2~3개의 도시만 추천하세요
- 각 도시의 추천 이유는 구체적이고 명확하게 작성하세요
- 입력이 모호하거나 부족하면, 합리적 가정을 짧게 `rationale`에 포함하세요
- 필수 키가 누락되면 스스로 JSON을 1회 보정해서 완전한 형식으로 응답하세요
"""

    def run(self, state: TravelState) -> TravelState:
        """도시 추천 실행"""
        
        # 입력 로깅
        log_agent_input(self.logger, self.role, state)

        # 프롬프트 생성
        prompt = self._create_prompt(state)

        # 시스템 프롬프트에 RAG 안내 추가
        rag_instruction = ""
        if self.enable_rag:
            rag_instruction = (
                "최신 정보가 필요하면 search_city_context 도구를 1회 이상 호출해 근거를 확인하세요."
            )
        else:
            rag_instruction = "도구를 사용하지 말고, 당신의 지식을 바탕으로 추천해주세요."

        system_prompt = self.system_prompt.format(rag_instruction=rag_instruction)

        # LLM + Tool 호출
        self.logger.info(f"[LLM] 호출 시작 (프롬프트 길이: {len(prompt)} 문자)")
        if self.enable_rag:
            response_text = invoke_with_tool_calls(
                system_prompt=system_prompt,
                user_prompt=prompt,
                tools=[search_city_context_tool],
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
            missing = missing_required_keys(result, ["recommended_cities", "rationale"])

            if missing:
                self.logger.warning(f"[파싱] 필수 키 누락 감지: {missing}, 보정 1회 시도")
                repaired_text = self._repair_json_once(cleaned_text, missing)
                result, _ = parse_json(repaired_text)

            self.logger.info("[파싱] JSON 추출 완료")
            recommended_cities = result.get("recommended_cities", [])
            self.logger.info(f"[파싱] {len(recommended_cities)}개 도시 추출 성공")
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"[파싱 오류] {e}")
            self.logger.error(f"응답: {response_text[:200]}...")
            recommended_cities = []
        
        # 상태 업데이트
        new_state = state.copy()
        new_state["recommended_cities"] = recommended_cities
        new_state["current_step"] = AgentType.CITY_RECOMMENDER
        new_state["flight_available"] = False
        new_state["flight_unavailability_reason"] = None
        new_state["flight_search_attempts"] = 0
        new_state["flight_info"] = None
        new_state["messages"].append({
            "role": self.role,
            "content": f"추천 도시: {', '.join([city['city'] for city in recommended_cities])}"
        })
        decision_memory = list(new_state.get("decision_memory", []))
        constraints_memory = dict(new_state.get("constraints_memory", {}))
        
        # 첫 번째 도시를 자동 선택 (MVP 단순화)
        if recommended_cities:
            new_state["selected_city_index"] = 0
            new_state["selected_city"] = recommended_cities[0]
            self.logger.info(f"[선택] 자동 선택된 도시: {recommended_cities[0]['city']}")
            decision_memory.append(
                f"CITY_RECOMMENDER: {recommended_cities[0]['city']}를 1순위로 선택"
            )

        constraints_memory["travel_theme"] = str(state.get("travel_theme", ""))
        constraints_memory["travel_days"] = str(state.get("travel_days", ""))
        constraints_memory["budget"] = str(state.get("budget", ""))
        constraints_memory["departure_city"] = str(state.get("departure_city", "서울"))
        new_state["decision_memory"] = decision_memory[-10:]
        new_state["constraints_memory"] = constraints_memory
        
        # 출력 로깅
        log_agent_output(self.logger, self.role, recommended_cities)
        
        return new_state

    def _create_prompt(self, state: TravelState) -> str:
        """프롬프트 생성"""
        prompt = f"여행 주제: {state['travel_theme']}\n"
        
        if state.get("travel_days"):
            prompt += f"여행 일수: {state['travel_days']}일\n"
        
        if state.get("budget"):
            prompt += f"예산: {state['budget']:,}원\n"
        
        if self.enable_rag:
            suggested_query = f"{state['travel_theme']} 여행 추천 도시 해외 최신 트렌드"
            prompt += (
                f"도시 맥락 검색 필요 시 search_city_context를 사용하세요.\n"
                f"권장 검색어: {suggested_query}\n"
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

        prompt += "\n위 조건에 맞는 해외 여행 도시를 추천해주세요."
        
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

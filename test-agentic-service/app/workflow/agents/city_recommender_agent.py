"""도시 추천 에이전트 - Agent A"""
import json
from typing import Dict
from langchain_core.messages import HumanMessage, SystemMessage
from utils.config import get_llm
from utils.logger import setup_logger, log_agent_input, log_agent_output, log_search_context
from retrieval.search_service import search_with_context
from workflow.state import TravelState, AgentType


class CityRecommenderAgent:
    """여행 주제에 맞는 해외 도시를 추천하는 에이전트 (RAG 지원)"""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.CITY_RECOMMENDER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        
        self.system_prompt = """당신은 전문 여행 컨설턴트입니다.
사용자의 여행 주제에 가장 적합한 해외 도시 2~3개를 추천해주세요.

{rag_instruction}

응답은 반드시 다음 JSON 형식으로 작성하세요:
{{
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
"""

    def run(self, state: TravelState) -> TravelState:
        """도시 추천 실행"""
        
        # 입력 로깅
        log_agent_input(self.logger, self.role, state)
        
        # RAG: 웹 검색으로 여행지 정보 수집
        search_context = ""
        if self.enable_rag:
            search_query = f"{state['travel_theme']} 여행 추천 도시 해외"
            self.logger.info(f"[RAG] 검색 쿼리 생성: {search_query}")
            search_context = search_with_context(search_query, max_results=3)
            log_search_context(self.logger, search_query, search_context)
        
        # 프롬프트 생성
        prompt = self._create_prompt(state, search_context)
        
        # 시스템 프롬프트에 RAG 안내 추가
        rag_instruction = ""
        if self.enable_rag and search_context:
            rag_instruction = "아래 검색 결과를 참고하여 더욱 구체적이고 정확한 추천을 해주세요."
        else:
            rag_instruction = "당신의 지식을 바탕으로 추천해주세요."
        
        system_prompt = self.system_prompt.format(rag_instruction=rag_instruction)
        
        # LLM 호출
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt)
        ]
        
        self.logger.info(f"[LLM] 호출 시작 (프롬프트 길이: {len(prompt)} 문자)")
        response = get_llm().invoke(messages)
        response_text = response.content.strip()
        self.logger.info(f"[LLM] 응답 받음 (길이: {len(response_text)} 문자)")
        
        # JSON 파싱
        try:
            # JSON 블록 추출 (```json ... ``` 제거)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            self.logger.info("[파싱] JSON 추출 완료")
            result = json.loads(response_text)
            recommended_cities = result.get("recommended_cities", [])
            self.logger.info(f"[파싱] {len(recommended_cities)}개 도시 추출 성공")
        except json.JSONDecodeError as e:
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
        
        # 첫 번째 도시를 자동 선택 (MVP 단순화)
        if recommended_cities:
            new_state["selected_city_index"] = 0
            new_state["selected_city"] = recommended_cities[0]
            self.logger.info(f"[선택] 자동 선택된 도시: {recommended_cities[0]['city']}")
        
        # 출력 로깅
        log_agent_output(self.logger, self.role, recommended_cities)
        
        return new_state

    def _create_prompt(self, state: TravelState, search_context: str = "") -> str:
        """프롬프트 생성"""
        prompt = f"여행 주제: {state['travel_theme']}\n"
        
        if state.get("travel_days"):
            prompt += f"여행 일수: {state['travel_days']}일\n"
        
        if state.get("budget"):
            prompt += f"예산: {state['budget']:,}원\n"
        
        # RAG 컨텍스트 추가
        if search_context:
            prompt += f"\n{search_context}\n"
        
        prompt += "\n위 조건에 맞는 해외 여행 도시를 추천해주세요."
        
        return prompt

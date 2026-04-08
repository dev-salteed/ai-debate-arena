"""Final recommendation agent."""
import json
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from utils.config import get_llm
from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.agents.response_guard import missing_required_keys, parse_json
from workflow.state import AgentType, DiningState


class RecommendationAgent:
    """Produces the final user-facing dining recommendations."""

    def __init__(self):
        self.role = AgentType.RECOMMENDATION
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        self.system_prompt = """당신은 최종 추천을 정리하는 Dining Recommendation Agent입니다.
사용자 요청과 검색 근거를 바탕으로 바로 고를 수 있는 추천 리스트를 완성하세요.

Few-shot 예시:
입력: 홍대, 조용한 카페, 작업
출력:
{
  "summary": "홍대 안에서도 소음이 덜하고 오래 머물기 쉬운 카페 위주로 추렸습니다.",
  "recommendations": [
    {
      "name": "카페 A",
      "location": "홍대",
      "category": "카페",
      "features": ["조용한 좌석", "콘센트", "넓은 테이블"],
      "best_for": "작업",
      "why_recommended": "집중 환경과 체류 편의성이 좋아 요청과 가장 잘 맞습니다.",
      "tips": "오후 늦게는 붐빌 수 있어 이른 시간 방문이 좋습니다.",
      "source_note": "검색 결과 1"
    }
  ],
  "follow_up_questions": [
    "디저트가 강한 곳으로 더 좁혀볼까요?",
    "24시 영업 장소만 다시 추려드릴까요?"
  ]
}

응답은 반드시 아래 JSON 형식으로 작성하세요:
{
  "summary": "전체 추천 요약",
  "recommendations": [
    {
      "name": "장소명",
      "location": "지역",
      "category": "업종",
      "features": ["특징"],
      "best_for": "가장 잘 맞는 상황",
      "why_recommended": "추천 이유",
      "tips": "방문 팁",
      "source_note": "근거 출처"
    }
  ],
  "follow_up_questions": ["후속 질문"]
}

주의사항:
- recommendations는 2개 이상 4개 이하를 목표로 하세요.
- JSON만 출력하세요.
- 필수 키 누락 시 JSON을 1회 보정하세요.
"""

    def run(self, state: DiningState) -> DiningState:
        log_agent_input(self.logger, self.role, state)

        prompt = self._create_prompt(state)
        response = get_llm().invoke(
            [SystemMessage(content=self.system_prompt), HumanMessage(content=prompt)]
        )
        response_text = str(response.content).strip()

        try:
            result, cleaned_text = parse_json(response_text)
            required_keys = ["summary", "recommendations", "follow_up_questions"]
            missing = missing_required_keys(result, required_keys)
            if missing:
                self.logger.warning(f"[파싱] 필수 키 누락 감지: {missing}, 보정 1회 시도")
                repaired_text = self._repair_json_once(cleaned_text, missing)
                result, _ = parse_json(repaired_text)
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error(f"[파싱 오류] {exc}")
            result = self._fallback_response(state)

        new_state = state.copy()
        new_state["recommendations"] = result
        new_state["current_step"] = AgentType.RECOMMENDATION
        new_state["completed"] = True

        decision_memory = list(new_state.get("decision_memory", []))
        decision_memory.append(
            f"RECOMMENDATION: 최종 추천 {len(result.get('recommendations', []))}개 생성"
        )
        new_state["decision_memory"] = decision_memory[-10:]
        new_state["messages"].append(
            {
                "role": self.role,
                "content": f"최종 추천 완료: {len(result.get('recommendations', []))}개",
            }
        )

        log_agent_output(self.logger, self.role, result)
        return new_state

    def _create_prompt(self, state: DiningState) -> str:
        parsed_query = state.get("parsed_query", {})
        candidate_places = state.get("candidate_places", [])
        search_brief = state.get("search_brief", {})

        lines = [
            f"원문 요청: {state.get('user_query', '')}",
            "",
            "[구조화 조건]",
            f"- 지역: {parsed_query.get('region', '') or '미정'}",
            f"- 업종: {parsed_query.get('venue_type', '') or '미정'}",
            f"- 목적: {parsed_query.get('purpose', '') or '미정'}",
            f"- 분위기: {', '.join(parsed_query.get('atmosphere', [])) or '미정'}",
            f"- 가격대: {parsed_query.get('price_range', '') or '미정'}",
            f"- 필수 조건: {', '.join(parsed_query.get('must_have', [])) or '없음'}",
            f"- 제외 조건: {', '.join(parsed_query.get('avoid', [])) or '없음'}",
            "",
            f"[검색 요약] {search_brief.get('search_strategy', '정보 없음')}",
            "",
            "[후보 목록]",
        ]

        if candidate_places:
            for item in candidate_places:
                lines.append(
                    "- "
                    f"{item.get('name', '미상')} | {item.get('area', '')} | {item.get('category', '')} | "
                    f"태그: {', '.join(item.get('vibe_tags', [])) or '없음'} | "
                    f"특징: {', '.join(item.get('features', [])) or '없음'} | "
                    f"주의: {item.get('caution', '') or '없음'} | "
                    f"출처: {item.get('source_note', '') or '없음'}"
                )
        else:
            lines.append("- 확정 후보가 없습니다. 검색 범위를 넓혀보는 후속 질문을 제안하세요.")

        lines.extend(
            [
                "",
                "사용자가 바로 선택할 수 있도록 자연스럽고 압축적인 추천 JSON을 작성하세요.",
            ]
        )
        return "\n".join(lines)

    def _fallback_response(self, state: DiningState) -> dict:
        parsed_query = state.get("parsed_query", {})
        region = parsed_query.get("region", "요청 지역")
        venue_type = parsed_query.get("venue_type", "장소")
        return {
            "summary": f"{region} 기준으로 {venue_type} 검색 범위를 조금 넓혀 다시 보는 것이 좋습니다.",
            "recommendations": [],
            "follow_up_questions": [
                "원하는 가격대나 메뉴를 더 구체적으로 알려주실래요?",
                "조용함보다 접근성이나 분위기를 더 우선할까요?",
            ],
        }

    def _repair_json_once(self, broken_json: str, missing_keys: List[str]) -> str:
        repair_system = (
            "당신은 JSON 리페어 도우미입니다. 반드시 유효한 JSON만 출력하고 설명문은 금지합니다."
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

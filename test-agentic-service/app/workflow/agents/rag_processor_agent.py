"""RAG processor that turns search evidence into candidate places."""
import json
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from utils.config import get_llm
from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.agents.response_guard import missing_required_keys, parse_json
from workflow.state import AgentType, DiningState


class RagProcessorAgent:
    """Condenses search evidence into structured recommendation candidates."""

    def __init__(self):
        self.role = AgentType.RAG_PROCESSOR
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        self.system_prompt = """당신은 RAG Processor Agent입니다.
검색 결과에서 과장 없이 실제 추천 후보를 추출하고, 사용자 조건과 연결된 근거를 남겨야 합니다.

Few-shot 예시:
입력: 지역=성수, 업종=식당, 검색 근거 3건
출력:
{
  "selection_rationale": "지역 적합성과 사용자 분위기 조건을 기준으로 후보를 정리했습니다.",
  "candidate_places": [
    {
      "name": "레스토랑 A",
      "area": "성수",
      "category": "양식",
      "vibe_tags": ["데이트", "분위기 좋은"],
      "features": ["창가 좌석", "코스 메뉴"],
      "caution": "주말 대기 가능성이 있습니다.",
      "source_note": "검색 결과 1"
    },
    {
      "name": "비스트로 B",
      "area": "성수",
      "category": "브런치",
      "vibe_tags": ["대화하기 좋은"],
      "features": ["조용한 실내", "예약 가능"],
      "caution": "",
      "source_note": "검색 결과 2"
    }
  ],
  "coverage_note": "분위기와 접근성 중심으로 후보를 추렸습니다."
}

응답은 반드시 아래 JSON 형식으로 작성하세요:
{
  "selection_rationale": "후보 선정 근거",
  "candidate_places": [
    {
      "name": "장소명",
      "area": "지역",
      "category": "업종 또는 메뉴",
      "vibe_tags": ["태그"],
      "features": ["특징"],
      "caution": "주의사항 또는 빈 문자열",
      "source_note": "근거 출처"
    }
  ],
  "coverage_note": "검색 커버리지 메모"
}

주의사항:
- 후보는 2개 이상 5개 이하를 목표로 하세요.
- 근거가 불충분한 추측은 피하세요.
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
            required_keys = ["selection_rationale", "candidate_places", "coverage_note"]
            missing = missing_required_keys(result, required_keys)
            if missing:
                self.logger.warning(f"[파싱] 필수 키 누락 감지: {missing}, 보정 1회 시도")
                repaired_text = self._repair_json_once(cleaned_text, missing)
                result, _ = parse_json(repaired_text)
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error(f"[파싱 오류] {exc}")
            result = {
                "selection_rationale": "검색 결과 구조화에 실패해 후보를 비워 둡니다.",
                "candidate_places": [],
                "coverage_note": "후속 검색 확장이 필요합니다.",
            }

        candidate_places = result.get("candidate_places", [])

        new_state = state.copy()
        new_state["candidate_places"] = candidate_places
        new_state["current_step"] = AgentType.RAG_PROCESSOR

        decision_memory = list(new_state.get("decision_memory", []))
        decision_memory.append(
            f"RAG_PROCESSOR: 후보 {len(candidate_places)}개 정리"
        )
        new_state["decision_memory"] = decision_memory[-10:]
        new_state["messages"].append(
            {
                "role": self.role,
                "content": f"후보 정리 완료: {len(candidate_places)}개",
            }
        )

        log_agent_output(self.logger, self.role, result)
        return new_state

    def _create_prompt(self, state: DiningState) -> str:
        parsed_query = state.get("parsed_query", {})
        search_brief = state.get("search_brief", {})
        lines = [
            f"원문 요청: {state.get('user_query', '')}",
            "",
            "[구조화 조건]",
            f"- 지역: {parsed_query.get('region', '') or '미정'}",
            f"- 업종: {parsed_query.get('venue_type', '') or '미정'}",
            f"- 목적: {parsed_query.get('purpose', '') or '미정'}",
            f"- 분위기: {', '.join(parsed_query.get('atmosphere', [])) or '미정'}",
            f"- 필수 조건: {', '.join(parsed_query.get('must_have', [])) or '없음'}",
            f"- 제외 조건: {', '.join(parsed_query.get('avoid', [])) or '없음'}",
            "",
            "[검색 전략]",
            f"- {search_brief.get('search_strategy', '전략 정보 없음')}",
            f"- 최신성 메모: {search_brief.get('freshness_note', '없음')}",
            "",
            "[검색 근거]",
        ]

        highlights = search_brief.get("source_highlights", [])
        if highlights:
            for item in highlights:
                lines.append(
                    f"- 장소: {item.get('place', '미상')} | 근거: {item.get('evidence', '')} | 출처: {item.get('source', '')}"
                )
        else:
            lines.append("- 근거가 비어 있습니다. 검색을 넓혀야 할 수 있습니다.")

        lines.extend(
            [
                "",
                "사용자 조건에 맞는 후보만 추려 JSON으로 정리하세요.",
            ]
        )
        return "\n".join(lines)

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

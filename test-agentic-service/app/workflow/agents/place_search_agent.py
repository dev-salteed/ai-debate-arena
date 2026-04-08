"""Search agent that gathers fresh place context."""
import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from retrieval.search_service import search_place_context_tool
from utils.config import get_llm
from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.agents.response_guard import missing_required_keys, parse_json
from workflow.agents.tool_runner import invoke_with_tool_calls
from workflow.state import AgentType, DiningState


class PlaceSearchAgent:
    """Searches the web/vector context for relevant restaurants and cafes."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.PLACE_SEARCH
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        self.system_prompt = """당신은 로컬 맛집 리서처입니다.
사용자 의도에 맞는 장소 후보를 찾기 위해 최신 검색 결과를 읽고 핵심 근거를 정리하세요.

{rag_instruction}

Few-shot 예시:
입력: 지역=홍대, 업종=카페, 목적=데이트, 분위기=[조용한, 분위기 좋은]
출력:
{
  "search_strategy": "데이트와 대화 적합성, 조용한 좌석 환경을 우선 탐색했습니다.",
  "queries_used": [
    "홍대 조용한 카페 데이트",
    "홍대 분위기 좋은 카페"
  ],
  "source_highlights": [
    {
      "place": "카페 A",
      "evidence": "대화하기 좋은 좌석과 감성적인 인테리어가 언급되었습니다.",
      "source": "검색 결과 1"
    },
    {
      "place": "카페 B",
      "evidence": "넓은 좌석과 낮은 소음 환경이 강조되었습니다.",
      "source": "검색 결과 2"
    }
  ],
  "freshness_note": "최근 후기와 매장 소개를 함께 참고했습니다.",
  "rationale": "검색 질의를 목적과 분위기 중심으로 묶어 후보를 좁혔습니다."
}

응답은 반드시 아래 JSON 형식으로 작성하세요:
{
  "search_strategy": "검색 전략 한 문장",
  "queries_used": ["사용한 쿼리"],
  "source_highlights": [
    {
      "place": "장소명",
      "evidence": "검색 근거 요약",
      "source": "출처 힌트"
    }
  ],
  "freshness_note": "최신성 메모",
  "rationale": "정리 근거"
}

주의사항:
- JSON 이외의 문장은 출력하지 마세요.
- source_highlights는 2개 이상 6개 이하를 목표로 하세요.
- 근거가 부족하면 부족하다고 명시하고 검색 폭을 넓히세요.
- 필수 키 누락 시 JSON을 1회 보정하세요.
"""

    def run(self, state: DiningState) -> DiningState:
        log_agent_input(self.logger, self.role, state)

        parsed_query = state.get("parsed_query", {})
        prompt = self._create_prompt(state)
        rag_instruction = (
            "search_place_context 도구를 1회 이상 사용해 검색 결과를 확인한 뒤 정리하세요."
            if self.enable_rag
            else "도구를 사용하지 말고 일반적인 상권 지식을 바탕으로 후보 근거를 정리하세요."
        )
        system_prompt = self.system_prompt.replace("{rag_instruction}", rag_instruction)

        if self.enable_rag:
            response_text = invoke_with_tool_calls(
                system_prompt=system_prompt,
                user_prompt=prompt,
                tools=[search_place_context_tool],
                logger=self.logger,
            )
        else:
            response = get_llm().invoke(
                [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]
            )
            response_text = str(response.content).strip()

        try:
            result, cleaned_text = parse_json(response_text)
            required_keys = [
                "search_strategy",
                "queries_used",
                "source_highlights",
                "freshness_note",
                "rationale",
            ]
            missing = missing_required_keys(result, required_keys)
            if missing:
                self.logger.warning(f"[파싱] 필수 키 누락 감지: {missing}, 보정 1회 시도")
                repaired_text = self._repair_json_once(cleaned_text, missing)
                result, _ = parse_json(repaired_text)
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error(f"[파싱 오류] {exc}")
            result = self._fallback_brief(parsed_query)

        queries_used = [
            str(query).strip()
            for query in result.get("queries_used", [])
            if str(query).strip()
        ]
        if not queries_used:
            queries_used = self._build_query_candidates(state)
            result["queries_used"] = queries_used

        new_state = state.copy()
        new_state["search_brief"] = result
        new_state["current_step"] = AgentType.PLACE_SEARCH
        new_state["search_iterations"] = state.get("search_iterations", 0) + 1

        highlight_count = len(result.get("source_highlights", []))
        decision_memory = list(new_state.get("decision_memory", []))
        decision_memory.append(
            f"PLACE_SEARCH: 쿼리 {len(queries_used)}개, 근거 {highlight_count}개 수집"
        )
        new_state["decision_memory"] = decision_memory[-10:]
        new_state["messages"].append(
            {
                "role": self.role,
                "content": f"검색 정리 완료: 쿼리 {len(queries_used)}개, 근거 {highlight_count}개",
            }
        )

        log_agent_output(self.logger, self.role, result)
        return new_state

    def _create_prompt(self, state: DiningState) -> str:
        parsed_query = state.get("parsed_query", {})
        queries = self._build_query_candidates(state)
        lines = [
            f"원문 요청: {state.get('user_query', '')}",
            "",
            "[구조화된 요청]",
            f"- 지역: {parsed_query.get('region', '') or '미정'}",
            f"- 세부 지역: {parsed_query.get('subregion', '') or '미정'}",
            f"- 업종: {parsed_query.get('venue_type', '') or '미정'}",
            f"- 목적: {parsed_query.get('purpose', '') or '미정'}",
            f"- 분위기: {', '.join(parsed_query.get('atmosphere', [])) or '미정'}",
            f"- 가격대: {parsed_query.get('price_range', '') or '미정'}",
            f"- 필수 조건: {', '.join(parsed_query.get('must_have', [])) or '없음'}",
            f"- 제외 조건: {', '.join(parsed_query.get('avoid', [])) or '없음'}",
            "",
            "[권장 검색어]",
        ]

        for query in queries:
            lines.append(f"- {query}")

        if state.get("search_iterations", 0) > 0 and not state.get("candidate_places"):
            lines.extend(
                [
                    "",
                    "[재검색 지침]",
                    "- 이전 후보가 부족했으니 너무 좁은 조건은 완만하게 풀어 검색 범위를 넓히세요.",
                ]
            )

        decision_memory = state.get("decision_memory", [])
        if decision_memory:
            lines.append("")
            lines.append("[최근 의사결정 메모리]")
            for item in decision_memory[-3:]:
                lines.append(f"- {item}")

        lines.extend(
            [
                "",
                "위 정보를 바탕으로 검색 도구를 사용하고, 핵심 후보 근거만 JSON으로 정리하세요.",
            ]
        )
        return "\n".join(lines)

    def _build_query_candidates(self, state: DiningState) -> List[str]:
        parsed_query = state.get("parsed_query", {})
        raw_queries = [
            str(query).strip()
            for query in parsed_query.get("search_queries", [])
            if str(query).strip()
        ]
        if state.get("search_iterations", 0) <= 0:
            return raw_queries[:4]

        region = str(parsed_query.get("region", "")).strip()
        venue_type = str(parsed_query.get("venue_type", "맛집")).strip() or "맛집"
        purpose = str(parsed_query.get("purpose", "")).strip()
        atmosphere = " ".join(parsed_query.get("atmosphere", [])[:1]).strip()
        broadened = [
            f"{region} {venue_type} 추천".strip(),
            f"{region} {purpose} {venue_type}".strip(),
            f"{region} 분위기 좋은 {venue_type}".strip(),
            f"{region} {atmosphere} {venue_type}".strip(),
        ]
        merged: List[str] = []
        for query in raw_queries + broadened:
            query = query.strip()
            if query and query not in merged:
                merged.append(query)
        return merged[:4]

    def _fallback_brief(self, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        queries = [
            str(query).strip()
            for query in parsed_query.get("search_queries", [])
            if str(query).strip()
        ]
        return {
            "search_strategy": "기본 질의 조합으로 상권 및 후기 탐색을 시도했습니다.",
            "queries_used": queries[:4],
            "source_highlights": [],
            "freshness_note": "구조화 응답 파싱에 실패해 후보 근거를 충분히 정리하지 못했습니다.",
            "rationale": "후속 단계에서 검색어를 재정비할 수 있도록 최소 정보만 유지했습니다.",
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

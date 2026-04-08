"""Query parser agent for dining recommendations."""
import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from utils.config import get_llm
from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.agents.response_guard import missing_required_keys, parse_json
from workflow.state import AgentType, DiningState


class QueryParserAgent:
    """Parses a natural-language food request into structured intent."""

    def __init__(self):
        self.role = AgentType.QUERY_PARSER
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")
        self.system_prompt = """당신은 지역 기반 맛집/카페 추천 서비스의 Query Parser Agent입니다.
사용자 요청에서 지역, 업종, 분위기, 목적, 가격대, 필수 조건, 제외 조건을 구조화하세요.

Few-shot 예시 1:
입력: 강남에서 조용한 카페 추천해줘. 노트북 쓰기 좋으면 좋겠어.
출력:
{
  "region": "강남",
  "subregion": "",
  "venue_type": "카페",
  "purpose": "작업",
  "atmosphere": ["조용한", "집중하기 좋은"],
  "price_range": "중간",
  "must_have": ["노트북 사용"],
  "avoid": [],
  "search_queries": [
    "강남 조용한 카페 노트북",
    "강남 작업하기 좋은 카페"
  ],
  "response_language": "ko",
  "rationale": "지역과 분위기, 이용 목적을 중심으로 검색 조건을 구조화했습니다."
}

Few-shot 예시 2:
입력: 홍대에서 데이트하기 좋은 저녁 식당 알려줘. 너무 시끄러운 곳은 싫어.
출력:
{
  "region": "홍대",
  "subregion": "",
  "venue_type": "식당",
  "purpose": "데이트",
  "atmosphere": ["분위기 좋은", "대화하기 좋은"],
  "price_range": "중간",
  "must_have": ["저녁 식사"],
  "avoid": ["시끄러운 곳"],
  "search_queries": [
    "홍대 데이트 저녁 식당 조용한",
    "홍대 분위기 좋은 레스토랑"
  ],
  "response_language": "ko",
  "rationale": "데이트 목적과 소음 회피 조건을 우선 반영했습니다."
}

응답은 반드시 아래 JSON 형식으로 작성하세요:
{
  "region": "주요 지역",
  "subregion": "세부 지역 또는 빈 문자열",
  "venue_type": "식당/카페/바 등",
  "purpose": "혼밥/데이트/회식/작업 등",
  "atmosphere": ["분위기 태그"],
  "price_range": "저가/중간/고가/미정",
  "must_have": ["필수 조건"],
  "avoid": ["피하고 싶은 조건"],
  "search_queries": ["검색용 쿼리"],
  "response_language": "ko",
  "rationale": "해석 근거 한 문장"
}

주의사항:
- JSON 이외의 설명문은 출력하지 마세요.
- search_queries는 2개 이상 4개 이하로 작성하세요.
- 정보가 없으면 합리적으로 추정하되 rationale에 반영하세요.
- 필수 키가 누락되면 스스로 JSON을 1회 보정하세요.
"""

    def run(self, state: DiningState) -> DiningState:
        log_agent_input(self.logger, self.role, state)

        prompt = self._create_prompt(state)
        response = get_llm().invoke(
            [SystemMessage(content=self.system_prompt), HumanMessage(content=prompt)]
        )
        response_text = str(response.content).strip()

        try:
            parsed, cleaned_text = parse_json(response_text)
            required_keys = [
                "region",
                "venue_type",
                "purpose",
                "atmosphere",
                "price_range",
                "must_have",
                "avoid",
                "search_queries",
                "response_language",
                "rationale",
            ]
            missing = missing_required_keys(parsed, required_keys)
            if missing:
                self.logger.warning(f"[파싱] 필수 키 누락 감지: {missing}, 보정 1회 시도")
                repaired_text = self._repair_json_once(cleaned_text, missing)
                parsed, _ = parse_json(repaired_text)
        except (json.JSONDecodeError, ValueError) as exc:
            self.logger.error(f"[파싱 오류] {exc}")
            parsed = self._fallback_parsed_query(state["user_query"])

        parsed["search_queries"] = self._ensure_search_queries(parsed, state["user_query"])

        new_state = state.copy()
        new_state["parsed_query"] = parsed
        new_state["current_step"] = AgentType.QUERY_PARSER
        new_state["search_brief"] = {}
        new_state["candidate_places"] = []
        new_state["recommendations"] = None

        constraints_memory = dict(new_state.get("constraints_memory", {}))
        constraints_memory["region"] = parsed.get("region", "")
        constraints_memory["venue_type"] = parsed.get("venue_type", "")
        constraints_memory["purpose"] = parsed.get("purpose", "")
        constraints_memory["price_range"] = parsed.get("price_range", "")
        if parsed.get("must_have"):
            constraints_memory["must_have"] = ", ".join(parsed.get("must_have", []))
        if parsed.get("avoid"):
            constraints_memory["avoid"] = ", ".join(parsed.get("avoid", []))
        new_state["constraints_memory"] = constraints_memory

        summary = self._format_intent(parsed)
        decision_memory = list(new_state.get("decision_memory", []))
        decision_memory.append(f"QUERY_PARSER: {summary}")
        new_state["decision_memory"] = decision_memory[-10:]
        new_state["messages"].append(
            {
                "role": self.role,
                "content": f"요청 해석 완료: {summary}",
            }
        )

        log_agent_output(self.logger, self.role, parsed)
        return new_state

    def _create_prompt(self, state: DiningState) -> str:
        prompt_lines = [f"사용자 요청: {state['user_query']}"]

        constraints_memory = state.get("constraints_memory", {})
        decision_memory = state.get("decision_memory", [])
        if constraints_memory:
            prompt_lines.append("")
            prompt_lines.append("[이전 제약조건 메모리]")
            for key, value in constraints_memory.items():
                prompt_lines.append(f"- {key}: {value}")
        if decision_memory:
            prompt_lines.append("")
            prompt_lines.append("[최근 의사결정 메모리]")
            for item in decision_memory[-3:]:
                prompt_lines.append(f"- {item}")

        prompt_lines.append("")
        prompt_lines.append("사용자 의도를 구조화된 JSON으로 해석하세요.")
        return "\n".join(prompt_lines)

    def _ensure_search_queries(self, parsed: Dict[str, Any], user_query: str) -> List[str]:
        queries = [
            str(query).strip()
            for query in parsed.get("search_queries", [])
            if str(query).strip()
        ]
        if queries:
            return queries[:4]

        region = str(parsed.get("region", "")).strip()
        venue_type = str(parsed.get("venue_type", "맛집")).strip() or "맛집"
        purpose = str(parsed.get("purpose", "")).strip()
        atmosphere = " ".join(parsed.get("atmosphere", [])[:2]).strip()
        base = " ".join(part for part in [region, purpose, atmosphere, venue_type] if part).strip()
        if not base:
            base = user_query.strip()

        derived = [base, f"{base} 추천", f"{region} {venue_type} 후기".strip()]
        return [query for query in derived if query][:4]

    def _format_intent(self, parsed: Dict[str, Any]) -> str:
        parts = [
            str(parsed.get("region", "")).strip() or "지역 미지정",
            str(parsed.get("venue_type", "")).strip() or "업종 미지정",
            str(parsed.get("purpose", "")).strip() or "상황 미지정",
        ]
        atmosphere = ", ".join(parsed.get("atmosphere", [])[:2]).strip()
        if atmosphere:
            parts.append(atmosphere)
        return " / ".join(parts)

    def _fallback_parsed_query(self, user_query: str) -> Dict[str, Any]:
        return {
            "region": "",
            "subregion": "",
            "venue_type": "맛집",
            "purpose": "일반 식사",
            "atmosphere": [],
            "price_range": "미정",
            "must_have": [],
            "avoid": [],
            "search_queries": [user_query.strip(), f"{user_query.strip()} 추천"],
            "response_language": "ko",
            "rationale": "JSON 파싱에 실패해 원문 요청을 중심으로 기본 검색 조건을 구성했습니다.",
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

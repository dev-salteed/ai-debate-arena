"""Retriever for 오늘 뭐해?"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Dict, List, Sequence

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState

try:
    from retrieval.search_service import search_outing_candidates
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from app.retrieval.search_service import search_outing_candidates


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _category_terms(parsed_context: Dict[str, object]) -> List[str]:
    keywords = list(parsed_context.get("category_hints", []) or [])
    if not keywords:
        keywords = list(parsed_context.get("keywords", []) or [])
    if not keywords:
        keywords = ["카페", "전시", "체험"]
    return keywords[:5]


def _build_queries(parsed_context: Dict[str, object], broaden_search: bool) -> List[str]:
    region = _normalize_text(str(parsed_context.get("region", "서울"))) or "서울"
    companion = _normalize_text(str(parsed_context.get("companion", "상관없음")))
    weather = _normalize_text(str(parsed_context.get("weather", "상관없음")))
    time_slot = _normalize_text(str(parsed_context.get("time_slot", "상관없음")))
    budget_level = _normalize_text(str(parsed_context.get("budget_level", "상관없음")))
    mobility = _normalize_text(str(parsed_context.get("mobility", "상관없음")))
    keywords = _category_terms(parsed_context)
    intent = _normalize_text(str(parsed_context.get("intent", "")))

    keyword_block = " ".join(keywords[:3])
    queries = [
        f"{region} {companion} {weather} {time_slot} {keyword_block} 추천".strip(),
        f"{region} 실내 {keyword_block} 카페 전시 체험 원데이클래스".strip(),
        f"{region} 운영시간 예약 가능한 {keyword_block} 후기".strip(),
    ]

    if intent:
        queries[0] = f"{region} {intent} 추천".strip()
        queries[1] = f"{region} {intent} {keyword_block} 실내".strip()

    if broaden_search:
        queries.extend(
            [
                f"{region} 오늘 뭐하지 추천".strip(),
                f"{region} 데이트 혼자 친구 가볼만한 곳".strip(),
                f"{region} 비 오는 날 실내 놀거리 예약".strip(),
            ]
        )
    else:
        if budget_level != "상관없음":
            queries.append(f"{region} {budget_level} 가성비 놀거리".strip())
        if mobility != "상관없음":
            queries.append(f"{region} {mobility} 이동 쉬운 곳".strip())

    seen: List[str] = []
    for query in queries:
        cleaned = _normalize_text(query)
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen[:6]


def _has_booking_url(results: Sequence[Dict[str, object]]) -> bool:
    for result in results:
        href = str(result.get("reservation_url") or result.get("href") or "")
        if href and href != "None":
            return True
    return False


class RetrieverAgent:
    """DuckDuckGo 멀티쿼리 검색과 초기 정제를 담당한다."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.RETRIEVER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)

        new_state = deepcopy(state)
        parsed_context = dict(new_state.get("parsed_context", {}))
        constraints_memory = dict(new_state.get("constraints_memory", {}))
        decision_memory = list(new_state.get("decision_memory", []))
        broaden_search = constraints_memory.get("broaden_search", "false") == "true"

        queries = _build_queries(parsed_context, broaden_search=broaden_search)
        context_terms = [
            value
            for value in [
                parsed_context.get("region", ""),
                parsed_context.get("companion", ""),
                parsed_context.get("weather", ""),
                parsed_context.get("time_slot", ""),
                parsed_context.get("budget_level", ""),
            ]
            if value and value != "상관없음"
        ]
        context_terms.extend(parsed_context.get("keywords", []) or [])

        search_results = search_outing_candidates(
            queries=queries,
            max_results_per_query=4 if broaden_search else 3,
            context_terms=context_terms,
        )

        if not search_results and not broaden_search:
            fallback_queries = _build_queries(parsed_context, broaden_search=True)
            search_results = search_outing_candidates(
                queries=fallback_queries,
                max_results_per_query=4,
                context_terms=context_terms,
            )
            queries = fallback_queries
            broaden_search = True

        new_state["search_queries"] = queries
        new_state["raw_search_results"] = search_results
        parsed_context["result_count"] = len(search_results)
        parsed_context["query_count"] = len(queries)
        new_state["parsed_context"] = parsed_context
        constraints_memory["broaden_search"] = "true" if broaden_search else "false"
        constraints_memory["retry_attempts"] = constraints_memory.get("retry_attempts", "0")
        constraints_memory["has_booking_link"] = "true" if _has_booking_url(search_results) else "false"
        constraints_memory["result_count"] = str(len(search_results))
        new_state["constraints_memory"] = constraints_memory
        new_state["current_step"] = self.role

        messages = list(new_state.get("messages", []))
        messages.append(
            {
                "role": self.role,
                "content": (
                    f"검색 쿼리 {len(queries)}개 생성, 후보 {len(search_results)}개 수집"
                ),
            }
        )
        new_state["messages"] = messages[-20:]

        decision_memory.append(
            "RETRIEVER: "
            f"queries={len(queries)}, results={len(search_results)}, broaden={broaden_search}"
        )
        new_state["decision_memory"] = decision_memory[-12:]

        log_agent_output(
            self.logger,
            self.role,
            {"queries": queries, "results": len(search_results)},
        )
        return new_state

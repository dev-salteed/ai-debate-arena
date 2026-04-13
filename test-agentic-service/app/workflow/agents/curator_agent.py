"""Curator for 오늘 뭐해?"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Dict, List, Sequence

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.state import AgentType, TodayWhatState

try:
    from retrieval.search_service import dedupe_results
except ModuleNotFoundError:  # pragma: no cover - import path fallback
    from app.retrieval.search_service import dedupe_results


_CATEGORY_ORDER = ("전시", "카페", "체험", "산책", "공연", "맛집", "복합")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _infer_category(text: str) -> str:
    normalized = _normalize_text(text).lower()
    mapping = {
        "전시": ("전시", "미술", "갤러리", "아트", "museum", "exhibition"),
        "카페": ("카페", "커피", "브런치", "베이커리", "디저트"),
        "체험": ("체험", "공방", "클래스", "원데이", "만들기"),
        "산책": ("산책", "공원", "둘레길", "강변", "호수"),
        "공연": ("공연", "연극", "뮤지컬", "콘서트", "라이브"),
        "맛집": ("맛집", "레스토랑", "식당", "다이닝", "이자카야"),
    }
    for category in _CATEGORY_ORDER:
        keywords = mapping.get(category, ())
        if any(keyword.lower() in normalized for keyword in keywords):
            return category
    return "복합"


def _infer_area(result: Dict[str, object], fallback_region: str) -> str:
    area = _normalize_text(str(result.get("area", "")))
    if area:
        return area
    text = " ".join(
        [
            str(result.get("title", "")),
            str(result.get("body", "")),
            str(result.get("href", "")),
        ]
    )
    for keyword in (
        "서울",
        "부산",
        "인천",
        "대구",
        "대전",
        "광주",
        "울산",
        "제주",
        "성수",
        "홍대",
        "연남",
        "종로",
        "강남",
        "잠실",
        "이태원",
        "한남",
        "여의도",
        "해운대",
    ):
        if keyword in text:
            return keyword
    return fallback_region or "국내"


def _infer_indoor_outdoor(category: str, weather: str) -> str:
    if category in {"전시", "카페", "체험", "공연", "맛집"}:
        return "실내"
    if category == "산책":
        return "실외"
    if weather in {"비", "눈", "흐림"}:
        return "실내"
    return "혼합"


def _estimate_cost(category: str, budget_level: str) -> str:
    if budget_level == "가볍게":
        return "1인 0~2만원"
    if budget_level == "여유":
        return "1인 3~7만원"
    if category in {"공연", "전시"}:
        return "1인 1~4만원"
    if category == "체험":
        return "1인 2~5만원"
    if category == "맛집":
        return "1인 1.5~4만원"
    return "1인 1~3만원"


def _best_for(companion: str, weather: str, category: str) -> str:
    if companion == "썸":
        base = "분위기 있는"
    elif companion == "친구":
        base = "편하게 수다 떨기 좋은"
    elif companion == "혼자":
        base = "혼자 여유 있게 즐기기 좋은"
    elif companion == "가족":
        base = "가족과 함께하기 좋은"
    else:
        base = "상황에 맞는"

    if weather in {"비", "눈"}:
        base += " 실내"
    elif category == "산책":
        base += " 야외"
    return base


def _booking_url(result: Dict[str, object]) -> str:
    return _normalize_text(
        str(result.get("reservation_url") or result.get("href") or "")
    )


def _source_url(result: Dict[str, object]) -> str:
    return _normalize_text(str(result.get("href") or ""))


def _context_snippet(parsed_context: Dict[str, object], fallback_body: str) -> str:
    search_context = str(parsed_context.get("search_context", "") or "")
    if search_context:
        lines = [line.strip() for line in search_context.splitlines() if line.strip()]
        for line in lines:
            if line.startswith("[") or line.startswith("출처:") or "===" in line:
                continue
            return f"검색 결과 반영: {line[:80].rstrip()}"
    return fallback_body[:90].rstrip() if fallback_body else ""


def _make_recommendation(
    result: Dict[str, object],
    parsed_context: Dict[str, object],
    index: int,
) -> Dict[str, object]:
    title = _normalize_text(str(result.get("title", ""))) or f"추천 코스 {index + 1}"
    body = _normalize_text(str(result.get("body", "")))
    region = _normalize_text(str(parsed_context.get("region", "서울"))) or "서울"
    companion = _normalize_text(str(parsed_context.get("companion", "상관없음")))
    weather = _normalize_text(str(parsed_context.get("weather", "상관없음")))
    budget_level = _normalize_text(str(parsed_context.get("budget_level", "상관없음")))
    category = _normalize_text(str(result.get("category", ""))) or _infer_category(f"{title} {body}")
    area = _infer_area(result, fallback_region=region)

    why_fit_bits = [
        f"{region}에서 바로 찾아보기 좋은 {category} 코스",
        _best_for(companion, weather, category),
    ]
    context_snippet = _context_snippet(parsed_context, body)
    if context_snippet:
        why_fit_bits.append(context_snippet)

    return {
        "name": title,
        "category": category,
        "area": area,
        "why_fit": " / ".join(bit for bit in why_fit_bits if bit),
        "indoor_outdoor": _infer_indoor_outdoor(category, weather),
        "estimated_cost": _estimate_cost(category, budget_level),
        "best_for": companion if companion != "상관없음" else "상관없음",
        "source_url": _source_url(result),
        "reservation_url": _booking_url(result),
        "query": _normalize_text(str(result.get("query", ""))),
        "score": float(result.get("score", 0.0) or 0.0),
    }


def _fallback_recommendations(parsed_context: Dict[str, object], needed: int) -> List[Dict[str, object]]:
    region = _normalize_text(str(parsed_context.get("region", "서울"))) or "서울"
    companion = _normalize_text(str(parsed_context.get("companion", "상관없음")))
    weather = _normalize_text(str(parsed_context.get("weather", "상관없음")))
    budget_level = _normalize_text(str(parsed_context.get("budget_level", "상관없음")))
    keywords = list(parsed_context.get("keywords", []) or [])
    category_cycle = list(dict.fromkeys([*(keywords[:3] or []), "카페", "전시", "체험", "산책"]))

    fallback: List[Dict[str, object]] = []
    for index in range(needed):
        category = category_cycle[index % len(category_cycle)] if category_cycle else "카페"
        recommendation = {
            "name": f"{region} {category} 코스 {index + 1}",
            "category": category if category in _CATEGORY_ORDER else "복합",
            "area": region,
            "why_fit": (
                f"검색 결과가 부족할 때를 대비한 {region} 중심의 기본 대안입니다. "
                f"{companion} 상황과 {weather} 조건을 고려해 {category} 위주로 구성했습니다."
            ),
            "indoor_outdoor": "실내" if weather in {"비", "눈", "흐림"} or category in {"카페", "전시", "체험"} else "혼합",
            "estimated_cost": _estimate_cost(category, budget_level),
            "best_for": companion if companion != "상관없음" else "상관없음",
            "source_url": "",
            "reservation_url": "",
            "query": "",
            "score": 0.0,
        }
        fallback.append(recommendation)
    return fallback


class CuratorAgent:
    """검색 결과를 3~5개 추천 카드로 정리한다."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.CURATOR
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)

        new_state = deepcopy(state)
        parsed_context = dict(new_state.get("parsed_context", {}))
        raw_results = list(new_state.get("raw_search_results", []) or [])
        constraints_memory = dict(new_state.get("constraints_memory", {}))
        decision_memory = list(new_state.get("decision_memory", []))

        deduped_results = dedupe_results(raw_results)
        recommendations = [
            _make_recommendation(result, parsed_context, index)
            for index, result in enumerate(deduped_results[:5])
        ]

        if len(recommendations) < 3:
            recommendations.extend(
                _fallback_recommendations(parsed_context, 3 - len(recommendations))
            )

        recommendations = recommendations[:5]
        has_booking_link = any(bool(rec.get("reservation_url")) for rec in recommendations)

        new_state["curated_candidates"] = recommendations
        parsed_context["curated_count"] = len(recommendations)
        parsed_context["has_booking_link"] = has_booking_link
        parsed_context["search_context_applied_to_curation"] = bool(parsed_context.get("search_context"))
        new_state["parsed_context"] = parsed_context
        constraints_memory["candidate_count"] = str(len(recommendations))
        constraints_memory["has_booking_link"] = "true" if has_booking_link else "false"
        constraints_memory.setdefault("broaden_search", "false")
        new_state["constraints_memory"] = constraints_memory
        new_state["current_step"] = self.role

        messages = list(new_state.get("messages", []))
        messages.append(
            {
                "role": self.role,
                "content": (
                    f"추천 후보 {len(recommendations)}개 정리 완료"
                    + (" (예약 링크 포함)" if has_booking_link else "")
                    + (" | search_context 반영" if parsed_context.get("search_context") else "")
                ),
            }
        )
        new_state["messages"] = messages[-20:]

        decision_memory.append(
            "CURATOR: "
            f"candidates={len(recommendations)}, booking_link={has_booking_link}"
        )
        if parsed_context.get("search_context"):
            decision_memory.append("CURATOR_CONTEXT: search_context_applied=true")
        new_state["decision_memory"] = decision_memory[-12:]

        log_agent_output(self.logger, self.role, recommendations)
        return new_state

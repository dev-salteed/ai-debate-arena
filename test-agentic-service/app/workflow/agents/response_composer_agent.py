"""Response composer for 오늘 뭐해?"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Dict, List

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.agents.response_guard import extract_json_text, missing_required_keys, parse_json
from workflow.state import AgentType, TodayWhatState


_REQUIRED_KEYS = (
    "summary",
    "situation_tags",
    "recommendations",
    "timeline",
    "route_summary",
    "booking_links",
    "notes",
    "follow_up_prompt",
)


def _normalize_final_plan(payload: Dict[str, object], state: TodayWhatState) -> Dict[str, object]:
    plan = deepcopy(payload)
    parsed_context = dict(state.get("parsed_context", {}))
    recommendations = list(plan.get("recommendations", []) or [])

    if len(recommendations) < 3:
        fallback_recommendations = list(state.get("curated_candidates", []) or [])[:5]
        if len(fallback_recommendations) < 3:
            region = str(parsed_context.get("region", "서울")) or "서울"
            companion = str(parsed_context.get("companion", "상관없음"))
            weather = str(parsed_context.get("weather", "상관없음"))
            fallback_recommendations.extend(
                [
                    {
                        "name": f"{region} 카페 코스",
                        "category": "카페",
                        "area": region,
                        "why_fit": f"{companion} 상황에 맞는 가벼운 시작점입니다.",
                        "indoor_outdoor": "실내",
                        "estimated_cost": "1인 1~3만원",
                        "best_for": companion,
                        "source_url": "",
                        "reservation_url": "",
                    },
                    {
                        "name": f"{region} 전시 코스",
                        "category": "전시",
                        "area": region,
                        "why_fit": f"{weather} 날씨에도 부담이 적은 실내 코스입니다.",
                        "indoor_outdoor": "실내",
                        "estimated_cost": "1인 1~4만원",
                        "best_for": companion,
                        "source_url": "",
                        "reservation_url": "",
                    },
                    {
                        "name": f"{region} 체험 코스",
                        "category": "체험",
                        "area": region,
                        "why_fit": "검색 결과가 부족할 때 채워 넣는 대안입니다.",
                        "indoor_outdoor": "실내",
                        "estimated_cost": "1인 2~5만원",
                        "best_for": companion,
                        "source_url": "",
                        "reservation_url": "",
                    },
                ]
            )
        recommendations = fallback_recommendations[:5]
        plan["recommendations"] = recommendations

    if not plan.get("timeline"):
        time_slot = str(parsed_context.get("time_slot", "상관없음"))
        plan["timeline"] = [
            {
                "time": "13:00" if time_slot == "상관없음" else "10:00",
                "title": str(recommendations[0].get("name", "첫 번째 코스")),
                "detail": str(recommendations[0].get("why_fit", "")),
                "category": str(recommendations[0].get("category", "")),
                "place": str(recommendations[0].get("area", "")),
            },
            {
                "time": "15:00",
                "title": str(recommendations[1].get("name", "두 번째 코스")),
                "detail": str(recommendations[1].get("why_fit", "")),
                "category": str(recommendations[1].get("category", "")),
                "place": str(recommendations[1].get("area", "")),
            },
            {
                "time": "18:00",
                "title": str(recommendations[2].get("name", "세 번째 코스")),
                "detail": str(recommendations[2].get("why_fit", "")),
                "category": str(recommendations[2].get("category", "")),
                "place": str(recommendations[2].get("area", "")),
            },
        ]

    if not plan.get("booking_links"):
        links: List[Dict[str, str]] = []
        for recommendation in recommendations:
            url = str(recommendation.get("reservation_url") or recommendation.get("source_url") or "")
            if not url.startswith(("http://", "https://")):
                continue
            links.append(
                {
                    "name": str(recommendation.get("name", "")),
                    "url": url,
                    "type": "reservation" if recommendation.get("reservation_url") else "source",
                }
            )
        plan["booking_links"] = links[:5]

    missing = missing_required_keys(plan, _REQUIRED_KEYS)
    for key in missing:
        if key == "summary":
            plan[key] = "오늘 뭐해? 추천을 준비했어요."
        elif key == "situation_tags":
            plan[key] = []
        elif key == "recommendations":
            plan[key] = []
        elif key == "timeline":
            plan[key] = []
        elif key == "route_summary":
            plan[key] = "추천된 장소를 같은 권역으로 묶어 이동하기 쉽게 정리했습니다."
        elif key == "booking_links":
            plan[key] = []
        elif key == "notes":
            plan[key] = []
        elif key == "follow_up_prompt":
            plan[key] = "원하시면 조건을 바꿔 다시 추천할게요."

    if len(plan.get("recommendations", [])) > 5:
        plan["recommendations"] = plan["recommendations"][:5]

    return plan


class ResponseComposerAgent:
    """최종 상태를 UI/API가 바로 쓰기 좋은 형태로 다듬는다."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.RESPONSE_COMPOSER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)

        new_state = deepcopy(state)
        final_plan = new_state.get("final_plan", {})

        if isinstance(final_plan, str):
            try:
                parsed = parse_json(extract_json_text(final_plan))[0] if final_plan.strip() else {}
            except Exception:
                try:
                    parsed = json.loads(extract_json_text(final_plan))
                except Exception:
                    parsed = {}
            final_plan = parsed if isinstance(parsed, dict) else {}

        if not isinstance(final_plan, dict):
            final_plan = {}

        final_plan = _normalize_final_plan(final_plan, new_state)
        new_state["final_plan"] = final_plan
        new_state["current_step"] = self.role
        new_state["completed"] = True

        messages = list(new_state.get("messages", []))
        messages.append({"role": self.role, "content": "최종 응답 포맷 정리 완료"})
        new_state["messages"] = messages[-20:]

        log_agent_output(self.logger, self.role, final_plan)
        return new_state

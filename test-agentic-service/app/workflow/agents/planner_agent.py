"""Planner for 오늘 뭐해?"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import re
from typing import Dict, List

from utils.logger import log_agent_input, log_agent_output, setup_logger
from workflow.agents.prompt_assets import build_planner_prompt
from workflow.state import AgentType, TodayWhatState


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _time_anchor(time_slot: str) -> str:
    mapping = {
        "오전": "10:00",
        "오후": "14:00",
        "저녁": "18:30",
        "하루 종일": "11:00",
        "상관없음": "13:00",
    }
    return mapping.get(time_slot, "13:00")


def _timeline_steps(recommendations: List[Dict[str, object]], time_slot: str) -> List[Dict[str, str]]:
    start = _time_anchor(time_slot)
    if time_slot == "오전":
        slots = ["10:00", "12:00", "14:30"]
    elif time_slot == "오후":
        slots = ["14:00", "16:00", "18:30"]
    elif time_slot == "저녁":
        slots = ["18:30", "19:30", "21:00"]
    elif time_slot == "하루 종일":
        slots = ["11:00", "14:00", "17:00", "19:30"]
    else:
        slots = [start, "15:00", "18:00"]

    steps: List[Dict[str, str]] = []
    selected = recommendations[: len(slots)]
    for index, recommendation in enumerate(selected):
        slot = slots[index]
        steps.append(
            {
                "time": slot,
                "title": str(recommendation.get("name", f"코스 {index + 1}")),
                "detail": str(recommendation.get("why_fit", "")),
                "category": str(recommendation.get("category", "")),
                "place": str(recommendation.get("area", "")),
            }
        )

    if len(steps) < 3:
        missing = 3 - len(steps)
        for offset in range(missing):
            steps.append(
                {
                    "time": f"{14 + offset}:00",
                    "title": "틈새 시간 채우기",
                    "detail": "카페 휴식이나 가벼운 산책으로 자연스럽게 이어갑니다.",
                    "category": "보조",
                    "place": "",
                }
            )

    return steps


def _route_summary(recommendations: List[Dict[str, object]], region: str) -> str:
    areas = [str(rec.get("area", "")).strip() for rec in recommendations if rec.get("area")]
    unique_areas = [area for idx, area in enumerate(areas) if area and area not in areas[:idx]]
    if len(unique_areas) <= 1:
        focus = unique_areas[0] if unique_areas else region
        return f"{focus} 한 권역 안에서 이동 부담이 적게 이어지도록 동선을 묶었습니다."
    return f"{region} 기준으로 {unique_areas[0]}에서 시작해 {unique_areas[-1]} 쪽으로 자연스럽게 이어지는 동선입니다."


def _booking_links(recommendations: List[Dict[str, object]]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    seen = set()
    for recommendation in recommendations:
        for url_key, link_type in (("reservation_url", "reservation"), ("source_url", "source")):
            url = _normalize_text(str(recommendation.get(url_key, "")))
            if not url or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            links.append(
                {
                    "name": str(recommendation.get("name", "")),
                    "url": url,
                    "type": link_type,
                }
            )
            seen.add(url)
            break
    return links[:5]


def _context_note(parsed_context: Dict[str, object]) -> str:
    search_context = str(parsed_context.get("search_context", "") or "")
    if not search_context:
        return ""
    lines = [line.strip() for line in search_context.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("[") or line.startswith("출처:") or "===" in line:
            continue
        return f"검색 컨텍스트 반영: {line[:110].rstrip()}"
    return ""


def _fallback_plan(parsed_context: Dict[str, object]) -> Dict[str, object]:
    region = _normalize_text(str(parsed_context.get("region", "서울"))) or "서울"
    companion = _normalize_text(str(parsed_context.get("companion", "상관없음")))
    weather = _normalize_text(str(parsed_context.get("weather", "상관없음")))
    time_slot = _normalize_text(str(parsed_context.get("time_slot", "상관없음")))
    budget_level = _normalize_text(str(parsed_context.get("budget_level", "상관없음")))

    recommendations = [
        {
            "name": f"{region} 분위기 좋은 카페",
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
            "name": f"{region} 전시 또는 문화공간",
            "category": "전시",
            "area": region,
            "why_fit": f"{weather} 날씨에도 부담이 적고 대화하기 좋습니다.",
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
            "why_fit": f"{time_slot} 흐름에 맞춰 일정에 활기를 더할 수 있습니다.",
            "indoor_outdoor": "실내",
            "estimated_cost": "1인 2~5만원",
            "best_for": companion,
            "source_url": "",
            "reservation_url": "",
        },
    ]

    return {
        "summary": f"{region} 중심으로 바로 실행하기 쉬운 기본 대안을 준비했어요.",
        "situation_tags": [tag for tag in [region, companion, weather, time_slot, budget_level] if tag and tag != "상관없음"],
        "recommendations": recommendations,
        "timeline": _timeline_steps(recommendations, time_slot),
        "route_summary": f"{region}에서 무리 없이 즐길 수 있는 기본 동선입니다.",
        "booking_links": [],
        "notes": ["검색 결과가 부족해서 기본 대안으로 채웠습니다."],
        "follow_up_prompt": "지역이나 동행 조건을 바꾸면 더 정확하게 다시 짜드릴게요.",
        "fallback_option": "실내 카페 + 전시 + 체험 조합으로 재검색",
        "quick_tips": ["방문 전 운영시간을 다시 확인해 주세요.", "비가 오면 실내 비중을 높이는 편이 안정적입니다."],
    }


class PlannerAgent:
    """큐레이션된 추천을 시간대별 일정으로 묶는다."""

    def __init__(self, enable_rag: bool = True):
        self.role = AgentType.PLANNER
        self.enable_rag = enable_rag
        self.logger = setup_logger(f"{__name__}.{self.__class__.__name__}")

    def run(self, state: TodayWhatState) -> TodayWhatState:
        log_agent_input(self.logger, self.role, state)

        new_state = deepcopy(state)
        parsed_context = dict(new_state.get("parsed_context", {}))
        recommendations = list(new_state.get("curated_candidates", []) or [])
        prompt_bundle = build_planner_prompt(parsed_context, len(recommendations))

        if len(recommendations) < 3:
            final_plan = _fallback_plan(parsed_context)
        else:
            region = _normalize_text(str(parsed_context.get("region", "서울"))) or "서울"
            companion = _normalize_text(str(parsed_context.get("companion", "상관없음")))
            weather = _normalize_text(str(parsed_context.get("weather", "상관없음")))
            time_slot = _normalize_text(str(parsed_context.get("time_slot", "상관없음")))
            budget_level = _normalize_text(str(parsed_context.get("budget_level", "상관없음")))
            mobility = _normalize_text(str(parsed_context.get("mobility", "상관없음")))
            keywords = list(parsed_context.get("keywords", []) or [])

            summary = (
                f"{region}에서 {companion} 상황에 맞는 추천 {min(5, len(recommendations))}개를 골랐어요."
                if companion != "상관없음"
                else f"{region} 중심으로 바로 실행 가능한 추천 {min(5, len(recommendations))}개를 골랐어요."
            )
            if weather != "상관없음":
                summary += f" {weather} 날씨를 고려해 {('실내' if weather in {'비', '눈', '흐림'} else '혼합')} 위주로 정리했습니다."

            situation_tags = [tag for tag in [region, companion, weather, time_slot, budget_level, mobility] if tag and tag != "상관없음"]
            situation_tags.extend([keyword for keyword in keywords if keyword not in situation_tags])
            situation_tags = list(dict.fromkeys(situation_tags))[:8]

            final_plan = {
                "summary": summary,
                "situation_tags": situation_tags,
                "recommendations": recommendations[:5],
                "timeline": _timeline_steps(recommendations, time_slot),
                "route_summary": _route_summary(recommendations, region),
                "booking_links": _booking_links(recommendations),
                "notes": [
                    f"{region} 기준으로 검색 결과를 정리했습니다.",
                    "운영시간과 휴무일은 방문 전 다시 확인해 주세요.",
                ],
                "follow_up_prompt": "원하면 지역, 예산, 동행 조건을 바꿔서 다시 짜드릴게요.",
                "fallback_option": (
                    "검색이 더 필요하면 실내 카페 + 전시 + 체험 조합으로 다시 좁혀볼 수 있어요."
                ),
                "quick_tips": [
                    "예약 링크가 있는 곳은 미리 확인하면 대기 시간을 줄일 수 있어요.",
                    "비가 오면 실내 코스부터 시작하는 편이 안정적입니다.",
                    f"현재 시간대는 {time_slot or '상관없음'} 기준으로 묶었습니다.",
                ],
            }
            context_note = _context_note(parsed_context)
            if context_note:
                final_plan["notes"].append(context_note)

        final_plan.setdefault("summary", "")
        final_plan.setdefault("situation_tags", [])
        final_plan.setdefault("recommendations", [])
        final_plan.setdefault("timeline", [])
        final_plan.setdefault("route_summary", "")
        final_plan.setdefault("booking_links", [])
        final_plan.setdefault("notes", [])
        final_plan.setdefault("follow_up_prompt", "원하시면 조건을 바꿔 다시 추천할게요.")
        final_plan.setdefault("fallback_option", "실내 카페 + 전시 + 체험 조합으로 재검색")
        final_plan.setdefault("quick_tips", [])

        if not final_plan["recommendations"]:
            final_plan["recommendations"] = _fallback_plan(parsed_context)["recommendations"]
            final_plan["timeline"] = _timeline_steps(final_plan["recommendations"], str(parsed_context.get("time_slot", "상관없음")))
            final_plan["booking_links"] = _booking_links(final_plan["recommendations"])

        new_state["final_plan"] = final_plan
        new_state["current_step"] = self.role

        messages = list(new_state.get("messages", []))
        messages.append(
            {
                "role": self.role,
                "content": (
                    "추천 일정과 응답 구조를 최종 정리했습니다. "
                    f"| role_prompt={prompt_bundle['role']} few_shot={len(prompt_bundle['few_shot_examples'])}"
                    + (" | search_context 반영" if parsed_context.get("search_context") else "")
                ),
            }
        )
        new_state["messages"] = messages[-20:]
        decision_memory = list(new_state.get("decision_memory", []))
        decision_memory.append(
            "PLANNER_PROMPT: "
            f"role={prompt_bundle['role']}, few_shot={len(prompt_bundle['few_shot_examples'])}"
        )
        new_state["decision_memory"] = decision_memory[-12:]
        new_state["completed"] = True

        log_agent_output(self.logger, self.role, final_plan)
        return new_state

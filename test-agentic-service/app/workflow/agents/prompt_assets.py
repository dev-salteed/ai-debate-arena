"""Role-based prompt bundles used by core workflow agents."""
from __future__ import annotations

from typing import Dict, List


def build_context_analyzer_prompt(user_query: str, defaults: Dict[str, str]) -> Dict[str, object]:
    system_prompt = """You are the Context Analyzer for '오늘 뭐해?'.
- Read one Korean user request and normalize it into outing-planning context.
- Focus on region, companion, weather, time slot, budget, mobility, and activity hints.
- Prefer concise, execution-oriented interpretations over broad summaries.
- When the weather implies friction, bias toward indoor-friendly suggestions."""

    few_shot_examples: List[Dict[str, str]] = [
        {
            "input": "비 오는 날 성수에서 썸이랑 전시 보고 카페 가고 싶어",
            "output": "region=성수; companion=썸; weather=비; time_slot=상관없음; keywords=전시,카페; prefer_indoor=true",
        },
        {
            "input": "혼자 홍대에서 가볍게 오후에 놀고 싶어",
            "output": "region=홍대; companion=혼자; weather=상관없음; time_slot=오후; budget_level=가볍게; keywords=카페,산책",
        },
    ]

    user_prompt = (
        f"사용자 요청: {user_query}\n"
        f"기본값: region={defaults.get('region', '서울')}, companion={defaults.get('companion', '상관없음')}, "
        f"weather={defaults.get('weather', '상관없음')}, time_slot={defaults.get('time_slot', '상관없음')}, "
        f"budget_level={defaults.get('budget_level', '상관없음')}, mobility={defaults.get('mobility', '상관없음')}"
    )

    return {
        "role": "Context Analyzer",
        "system_prompt": system_prompt,
        "few_shot_examples": few_shot_examples,
        "user_prompt": user_prompt,
    }


def build_planner_prompt(parsed_context: Dict[str, object], recommendation_count: int) -> Dict[str, object]:
    system_prompt = """You are the Planner for '오늘 뭐해?'.
- Turn curated candidates into an immediately usable outing plan.
- Keep the response practical: summary, timeline, route flow, booking links, and quick tips.
- Reflect the user's relationship, weather, and time-slot constraints in the tone of the plan.
- Do not over-explain; make the plan feel ready to execute."""

    few_shot_examples: List[Dict[str, str]] = [
        {
            "input": "region=성수, companion=썸, weather=비, time_slot=저녁, candidates=3",
            "output": "summary=실내 위주 저녁 데이트 제안; timeline=18:30-전시,19:30-카페,21:00-체험; route_summary=도보 이동 최소화",
        },
        {
            "input": "region=서울, companion=혼자, weather=상관없음, time_slot=오후, candidates=4",
            "output": "summary=혼자 가볍게 머물 코스; timeline=14:00-카페,16:00-전시,18:30-산책; quick_tips=운영시간 재확인",
        },
    ]

    user_prompt = (
        f"parsed_context={parsed_context}; curated_candidates={recommendation_count}; "
        "필수 출력 키=summary,recommendations,timeline,route_summary,booking_links,notes,follow_up_prompt"
    )

    return {
        "role": "Planner",
        "system_prompt": system_prompt,
        "few_shot_examples": few_shot_examples,
        "user_prompt": user_prompt,
    }


def build_retriever_prompt(parsed_context: Dict[str, object], query: str) -> Dict[str, object]:
    system_prompt = """You are the Retriever for '오늘 뭐해?'.
- Use the provided search tool to gather up-to-date outing context.
- Prefer practical and location-aware information over generic summaries.
- Look for signals about indoor suitability, reservations, and visitability.
- Keep the final answer short because downstream ranking logic will do detailed scoring."""

    few_shot_examples: List[Dict[str, str]] = [
        {
            "input": "query=성수 비 오는 날 데이트 전시 카페 추천",
            "output": "실내 데이트와 예약 가능성이 보이는 전시/카페 중심 컨텍스트 요약",
        },
        {
            "input": "query=홍대 혼자 오후 카페 전시 추천",
            "output": "혼자 머물기 좋은 카페/전시와 이동 부담이 낮은 권역 정보 요약",
        },
    ]

    user_prompt = f"parsed_context={parsed_context}\nprimary_query={query}\n반드시 search_outing_context 도구를 먼저 고려하세요."

    return {
        "role": "Retriever",
        "system_prompt": system_prompt,
        "few_shot_examples": few_shot_examples,
        "user_prompt": user_prompt,
    }


def build_response_composer_prompt(
    parsed_context: Dict[str, object],
    recommendation_count: int,
) -> Dict[str, object]:
    system_prompt = """You are the Response Composer for '오늘 뭐해?'.
- Normalize the response into a stable structure even when user input varies.
- Always preserve the required output keys and keep the shape UI-friendly.
- If information is sparse, prefer safe fallback structure over omission."""

    few_shot_examples: List[Dict[str, str]] = [
        {
            "input": "region=서울, weather=비, recommendations=2",
            "output": "required keys filled; fallback recommendation added; timeline and booking_links normalized",
        },
        {
            "input": "region=부산, companion=친구, recommendations=5",
            "output": "summary/timeline/notes/follow_up_prompt all preserved with stable schema",
        },
    ]

    user_prompt = (
        f"parsed_context={parsed_context}; recommendation_count={recommendation_count}; "
        "required_keys=summary,situation_tags,recommendations,timeline,route_summary,booking_links,notes,follow_up_prompt"
    )

    return {
        "role": "Response Composer",
        "system_prompt": system_prompt,
        "few_shot_examples": few_shot_examples,
        "user_prompt": user_prompt,
    }

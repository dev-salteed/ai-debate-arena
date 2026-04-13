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

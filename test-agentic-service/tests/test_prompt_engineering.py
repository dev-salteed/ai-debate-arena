import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.city_recommender_agent import CityRecommenderAgent
from workflow.agents.flight_search_agent import FlightSearchAgent
from workflow.agents.itinerary_agent import ItineraryAgent


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _SequentialLLM:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0

    def invoke(self, _messages):
        if self._idx >= len(self._responses):
            return _FakeResponse(self._responses[-1])
        content = self._responses[self._idx]
        self._idx += 1
        return _FakeResponse(content)


class PromptEngineeringTests(unittest.TestCase):
    def test_prompts_include_few_shot_and_consistency_guards(self):
        city = CityRecommenderAgent(enable_rag=False)
        flight = FlightSearchAgent(enable_rag=False)
        itinerary = ItineraryAgent(enable_rag=False)

        self.assertIn("Few-shot 예시", city.system_prompt)
        self.assertIn("Few-shot 예시", flight.system_prompt)
        self.assertIn("Few-shot 예시", itinerary.system_prompt)

        self.assertIn("rationale", city.system_prompt)
        self.assertIn("rationale", flight.system_prompt)
        self.assertIn("rationale", itinerary.system_prompt)
        self.assertIn("필수 키", city.system_prompt)

    @patch("workflow.agents.city_recommender_agent.get_llm")
    def test_city_agent_repairs_missing_required_keys_once(self, mock_get_llm):
        # 첫 응답은 rationale 누락, 두 번째 응답은 보정 JSON
        mock_get_llm.return_value = _SequentialLLM(
            [
                """{"recommended_cities":[{"city":"도쿄","country":"일본","reason":"미식"}]}""",
                """{"rationale":"입력이 제한적이라 미식 접근성 기준으로 추천","recommended_cities":[{"city":"도쿄","country":"일본","reason":"미식"}]}""",
            ]
        )

        agent = CityRecommenderAgent(enable_rag=False)
        state = {
            "travel_theme": "미식 여행",
            "travel_days": 4,
            "budget": None,
            "departure_city": "서울",
            "recommended_cities": [],
            "selected_city": None,
            "flight_info": None,
            "flight_available": False,
            "flight_unavailability_reason": None,
            "selected_city_index": 0,
            "flight_search_attempts": 0,
            "max_flight_search_attempts": 3,
            "itinerary": None,
            "decision_memory": [],
            "constraints_memory": {},
            "current_step": "",
            "messages": [],
            "completed": False,
        }

        new_state = agent.run(state)
        self.assertGreaterEqual(len(new_state.get("recommended_cities", [])), 1)
        self.assertEqual(new_state.get("selected_city", {}).get("city"), "도쿄")

    @patch("workflow.agents.city_recommender_agent.invoke_with_tool_calls")
    def test_city_agent_uses_city_context_tool_when_rag_enabled(self, mock_invoke):
        mock_invoke.return_value = (
            '{"rationale":"검색 근거 반영","recommended_cities":[{"city":"도쿄","country":"일본","reason":"미식"}]}'
        )

        agent = CityRecommenderAgent(enable_rag=True)
        state = {
            "travel_theme": "미식 여행",
            "travel_days": 4,
            "budget": None,
            "departure_city": "서울",
            "recommended_cities": [],
            "selected_city": None,
            "flight_info": None,
            "flight_available": False,
            "flight_unavailability_reason": None,
            "selected_city_index": 0,
            "flight_search_attempts": 0,
            "max_flight_search_attempts": 3,
            "itinerary": None,
            "decision_memory": [],
            "constraints_memory": {},
            "current_step": "",
            "messages": [],
            "completed": False,
        }

        new_state = agent.run(state)

        self.assertEqual(new_state.get("selected_city", {}).get("city"), "도쿄")
        self.assertTrue(mock_invoke.called)
        passed_tools = mock_invoke.call_args.kwargs.get("tools", [])
        self.assertEqual(len(passed_tools), 1)
        self.assertEqual(getattr(passed_tools[0], "name", ""), "search_city_context")


if __name__ == "__main__":
    unittest.main()

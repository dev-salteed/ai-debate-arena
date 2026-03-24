import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.flight_search_agent import FlightSearchAgent


class FlightToolIntegrationTests(unittest.TestCase):
    @patch("workflow.agents.flight_search_agent.invoke_with_tool_calls")
    def test_tool_observation_is_used_as_search_context(self, mock_invoke):
        mock_invoke.return_value = (
            """{
              "rationale": "검색 결과를 반영했습니다.",
              "flight": {
                "departure_airport": "ICN",
                "arrival_airport": "LYR",
                "departure_date": "2026-05-01",
                "return_date": "2026-05-06",
                "airline": "테스트항공",
                "price": 1200000
              }
            }""",
            "No flights are available for selected dates.",
        )

        agent = FlightSearchAgent(enable_rag=True)
        state = {
            "travel_theme": "오로라 여행",
            "travel_days": 5,
            "budget": None,
            "departure_city": "서울",
            "recommended_cities": [{"city": "롱이어비엔", "country": "노르웨이"}],
            "selected_city": {"city": "롱이어비엔", "country": "노르웨이"},
            "selected_city_index": 0,
            "flight_info": None,
            "flight_available": False,
            "flight_unavailability_reason": None,
            "flight_search_attempts": 0,
            "max_flight_search_attempts": 3,
            "itinerary": None,
            "decision_memory": [],
            "constraints_memory": {},
            "current_step": "CITY_RECOMMENDER",
            "messages": [],
            "completed": False,
        }

        new_state = agent.run(state)

        self.assertTrue(mock_invoke.called)
        self.assertEqual(
            getattr(mock_invoke.call_args.kwargs["tools"][0], "name", ""),
            "search_flight_context",
        )
        self.assertTrue(mock_invoke.call_args.kwargs["return_last_observation"])

        self.assertFalse(new_state["flight_available"])
        self.assertIn("미가용 신호", new_state["flight_unavailability_reason"])


if __name__ == "__main__":
    unittest.main()

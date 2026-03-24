import sys
import unittest
from pathlib import Path

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.supervisor_agent import SupervisorAgent
from workflow.state import AgentType


def make_state(**overrides):
    base = {
        "travel_theme": "테스트",
        "travel_days": 5,
        "budget": None,
        "departure_city": "서울",
        "recommended_cities": [
            {"city": "도쿄", "country": "일본", "reason": "가깝고 인기"},
            {"city": "오사카", "country": "일본", "reason": "미식 여행"},
        ],
        "selected_city": {"city": "도쿄", "country": "일본", "reason": "가깝고 인기"},
        "selected_city_index": 0,
        "flight_info": None,
        "flight_available": False,
        "flight_unavailability_reason": "운항 없음",
        "flight_search_attempts": 1,
        "max_flight_search_attempts": 3,
        "itinerary": None,
        "current_step": AgentType.FLIGHT_SEARCH,
        "messages": [],
        "completed": False,
    }
    base.update(overrides)
    return base


class SupervisorRoutingTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = SupervisorAgent()

    def test_routes_to_itinerary_when_flight_available(self):
        state = make_state(flight_available=True)
        routed = self.supervisor.route_next(state)
        self.assertEqual(routed, AgentType.ITINERARY_PLANNER)

    def test_switches_to_next_city_and_retries_when_unavailable(self):
        state = make_state()
        updated = self.supervisor.run(state)

        self.assertEqual(updated.get("selected_city_index"), 1)
        self.assertEqual(updated.get("selected_city", {}).get("city"), "오사카")
        self.assertIn("분기", updated.get("messages", [])[-1].get("content"))

        routed = self.supervisor.route_next(updated)
        self.assertEqual(routed, AgentType.FLIGHT_SEARCH)

    def test_routes_to_itinerary_when_no_more_retry_candidates(self):
        state = make_state(selected_city_index=1, flight_search_attempts=3)
        updated = self.supervisor.run(state)
        routed = self.supervisor.route_next(updated)
        self.assertEqual(routed, AgentType.ITINERARY_PLANNER)


if __name__ == "__main__":
    unittest.main()


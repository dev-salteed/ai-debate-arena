import sys
import unittest
from pathlib import Path

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.flight_search_agent import FlightSearchAgent
from workflow.agents.itinerary_agent import ItineraryAgent


class MemoryFlowTests(unittest.TestCase):
    def test_flight_prompt_includes_memory_context(self):
        agent = FlightSearchAgent(enable_rag=True)
        state = {
            "departure_city": "서울",
            "travel_days": 5,
            "selected_city": {"city": "오슬로", "country": "노르웨이"},
            "constraints_memory": {"last_flight_unavailability_reason": "운항 없음"},
            "decision_memory": ["SUPERVISOR: 오슬로로 재검색"],
        }
        prompt = agent._create_prompt(
            state=state,
            departure_date="2026-05-01",
            return_date="2026-05-06",
            search_context="",
        )
        self.assertIn("[제약조건 메모리]", prompt)
        self.assertIn("last_flight_unavailability_reason", prompt)
        self.assertIn("[최근 의사결정 메모리]", prompt)
        self.assertIn("재검색", prompt)

    def test_itinerary_prompt_includes_recent_decisions(self):
        agent = ItineraryAgent(enable_rag=True)
        state = {
            "selected_city": {"city": "도쿄", "country": "일본"},
            "travel_theme": "미식 여행",
            "travel_days": 3,
            "flight_info": {
                "airline": "대한항공",
                "departure_date": "2026-05-01",
                "return_date": "2026-05-04",
                "price": 420000,
            },
            "budget": None,
            "constraints_memory": {"departure_city": "서울"},
            "decision_memory": ["FLIGHT_SEARCH: 가용 항공권 확보 (대한항공, 420,000원)"],
        }
        prompt = agent._create_prompt(state=state)
        self.assertIn("[최근 의사결정 메모리]", prompt)
        self.assertIn("가용 항공권 확보", prompt)


if __name__ == "__main__":
    unittest.main()


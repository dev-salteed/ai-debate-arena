import sys
import unittest
from pathlib import Path

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.flight_search_agent import FlightSearchAgent


class FlightAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.agent = FlightSearchAgent(enable_rag=False)

    def test_available_when_required_fields_present_and_no_negative_signal(self):
        flight_info = {
            "departure_airport": "ICN",
            "arrival_airport": "NRT",
            "departure_date": "2026-05-01",
            "return_date": "2026-05-06",
            "airline": "대한항공",
            "price": 350000,
        }
        available, reason = self.agent._evaluate_availability(
            flight_info=flight_info,
            search_context="항공권 검색 결과 요약",
        )
        self.assertTrue(available)
        self.assertEqual(reason, "")

    def test_unavailable_when_price_is_invalid(self):
        flight_info = {
            "departure_airport": "ICN",
            "arrival_airport": "NRT",
            "departure_date": "2026-05-01",
            "return_date": "2026-05-06",
            "airline": "대한항공",
            "price": 0,
        }
        available, reason = self.agent._evaluate_availability(
            flight_info=flight_info,
            search_context="",
        )
        self.assertFalse(available)
        self.assertIn("가격", reason)

    def test_unavailable_when_negative_signal_in_search_context(self):
        flight_info = {
            "departure_airport": "ICN",
            "arrival_airport": "LYR",
            "departure_date": "2026-05-01",
            "return_date": "2026-05-06",
            "airline": "테스트항공",
            "price": 1200000,
        }
        available, reason = self.agent._evaluate_availability(
            flight_info=flight_info,
            search_context="No flights are available for selected dates.",
        )
        self.assertFalse(available)
        self.assertIn("미가용 신호", reason)

    def test_collects_availability_signal_keywords(self):
        keywords = self.agent._collect_availability_signals(
            "항공편 출도착 스케줄과 예약 가능 여부를 확인하세요."
        )
        self.assertIn("예약 가능 여부", keywords)
        self.assertIn("출도착", keywords)


if __name__ == "__main__":
    unittest.main()

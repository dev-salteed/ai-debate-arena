import sys
import unittest
from pathlib import Path

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import build_continued_state, build_initial_state


class UiMultiturnStateTests(unittest.TestCase):
    def test_build_initial_state_sets_clean_defaults(self):
        state = build_initial_state(
            travel_theme="미식 여행",
            travel_days=4,
            budget=1500000,
            departure_city="서울",
        )
        self.assertEqual(state["travel_theme"], "미식 여행")
        self.assertEqual(state["travel_days"], 4)
        self.assertEqual(state["budget"], 1500000)
        self.assertEqual(state["current_step"], "")
        self.assertFalse(state["completed"])
        self.assertEqual(state["messages"], [])

    def test_build_continued_state_preserves_memory_and_overrides_inputs(self):
        previous = build_initial_state(
            travel_theme="해변 휴양",
            travel_days=5,
            budget=2000000,
            departure_city="서울",
        )
        previous["decision_memory"] = ["SUPERVISOR: 항공권 미가용으로 도시 전환"]
        previous["constraints_memory"] = {"last_flight_unavailability_reason": "운항 없음"}
        previous["completed"] = True
        previous["current_step"] = "ITINERARY_PLANNER"

        continued = build_continued_state(
            previous_state=previous,
            travel_theme="온천 여행",
            travel_days=3,
            budget=1200000,
            departure_city="부산",
        )

        self.assertEqual(continued["travel_theme"], "온천 여행")
        self.assertEqual(continued["travel_days"], 3)
        self.assertEqual(continued["budget"], 1200000)
        self.assertEqual(continued["departure_city"], "부산")
        self.assertFalse(continued["completed"])
        self.assertEqual(continued["current_step"], "")
        self.assertIn("항공권 미가용", continued["decision_memory"][0])
        self.assertEqual(
            continued["constraints_memory"]["last_flight_unavailability_reason"],
            "운항 없음",
        )


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api.main import app


class _FakeGraph:
    def invoke(self, state):
        state = dict(state)
        state["completed"] = True
        state["current_step"] = "ITINERARY_PLANNER"
        state["recommended_cities"] = [
            {"city": "도쿄", "country": "일본", "reason": "미식"}
        ]
        state["selected_city"] = state["recommended_cities"][0]
        return state


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    @patch("api.main.create_travel_graph")
    def test_create_plan(self, mock_create_graph):
        mock_create_graph.return_value = _FakeGraph()

        payload = {
            "travel_theme": "미식 여행",
            "travel_days": 4,
            "budget": 1500000,
            "departure_city": "서울",
            "enable_rag": True,
            "max_flight_search_attempts": 3,
        }
        res = self.client.post("/api/plan", json=payload)

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["result"]["completed"])
        self.assertEqual(body["result"]["selected_city"]["city"], "도쿄")

    def test_create_plan_validation_error(self):
        res = self.client.post("/api/plan", json={"travel_theme": ""})
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()


import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from api.main import app


class _FakeGraph:
    def invoke(self, state, config=None):
        state = dict(state)
        state["completed"] = True
        state["current_step"] = "RESPONSE_COMPOSER"
        state["final_plan"] = {
            "summary": "성수 실내 데이트 코스를 추천합니다.",
            "recommendations": [{"name": "테스트 전시", "reservation_url": "https://example.com/book"}],
            "timeline": [{"time": "18:00", "title": "전시 보기"}],
            "route_summary": "성수역에서 도보 10분 내 이동",
            "booking_links": ["https://example.com/book"],
            "notes": [],
            "follow_up_prompt": "취향을 더 알려주면 다시 추천할게요.",
            "situation_tags": ["비", "데이트"],
        }
        return state


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    @patch("api.main.create_today_what_graph")
    def test_create_plan(self, mock_create_graph):
        mock_create_graph.return_value = _FakeGraph()

        payload = {
            "user_query": "비 오는 날 성수에서 데이트 뭐해?",
            "region": "성수",
            "companion": "썸",
            "weather": "비",
            "time_slot": "저녁",
            "budget_level": "보통",
            "mobility": "대중교통",
            "enable_rag": True,
        }
        res = self.client.post("/api/plan", json=payload)

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["result"]["completed"])
        self.assertEqual(body["result"]["final_plan"]["recommendations"][0]["name"], "테스트 전시")

    def test_create_plan_validation_error(self):
        res = self.client.post("/api/plan", json={"user_query": ""})
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()

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
        state["current_step"] = "RECOMMENDATION"
        state["parsed_query"] = {"region": "강남", "venue_type": "카페", "purpose": "작업"}
        state["recommendations"] = {
            "summary": "강남에서 작업하기 좋은 카페를 추렸습니다.",
            "recommendations": [
                {
                    "name": "카페 A",
                    "location": "강남",
                    "category": "카페",
                    "features": ["조용한 좌석"],
                    "best_for": "작업",
                    "why_recommended": "집중하기 좋아요.",
                    "tips": "오전 방문 추천",
                    "source_note": "검색 결과 1",
                }
            ],
            "follow_up_questions": [],
        }
        return state


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @patch("api.main.create_dining_graph")
    def test_recommend(self, mock_create_graph):
        mock_create_graph.return_value = _FakeGraph()

        response = self.client.post(
            "/api/recommend",
            json={"user_query": "강남에서 조용한 카페 추천해줘", "enable_rag": True},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["result"]["completed"])
        self.assertEqual(body["result"]["parsed_query"]["region"], "강남")
        self.assertEqual(
            body["result"]["recommendations"]["recommendations"][0]["name"],
            "카페 A",
        )

    def test_recommend_validation_error(self):
        response = self.client.post("/api/recommend", json={"user_query": ""})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

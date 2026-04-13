import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.curator_agent import CuratorAgent
from workflow.agents.retriever_agent import RetrieverAgent


class RetrievalAndCurationTests(unittest.TestCase):
    @patch("workflow.agents.retriever_agent.invoke_with_tool_calls")
    @patch("workflow.agents.retriever_agent.search_outing_candidates")
    def test_retriever_builds_multiple_queries_and_collects_results(self, mock_search_outing_candidates, mock_invoke_with_tool_calls):
        mock_invoke_with_tool_calls.return_value = "웹/벡터 통합 컨텍스트"
        mock_search_outing_candidates.return_value = [
            {
                "title": "성수 전시 추천",
                "body": "실내 데이트에 잘 맞는 전시 공간",
                "href": "https://example.com/exhibit",
                "reservation_url": "https://example.com/exhibit/book",
                "category": "전시",
                "area": "성수",
                "score": 7.5,
            }
        ]
        agent = RetrieverAgent(enable_rag=True)
        state = {
            "user_query": "비 오는 날 성수에서 데이트 뭐해?",
            "region": "성수",
            "companion": "썸",
            "weather": "비",
            "time_slot": "저녁",
            "budget_level": "보통",
            "mobility": "대중교통",
            "parsed_context": {
                "region": "성수",
                "companion": "썸",
                "weather": "비",
                "time_slot": "저녁",
                "budget_level": "보통",
                "mobility": "대중교통",
                "intent": "비 오는 날 성수에서 데이트 뭐해?",
                "keywords": ["데이트", "전시", "카페"],
            },
            "search_queries": [],
            "raw_search_results": [],
            "curated_candidates": [],
            "final_plan": {},
            "decision_memory": [],
            "constraints_memory": {"retry_attempts": "0", "broaden_search": "false"},
            "messages": [],
            "current_step": "CONTEXT_ANALYZER",
            "completed": False,
        }

        new_state = agent.run(state)

        self.assertGreaterEqual(len(new_state["search_queries"]), 3)
        self.assertEqual(len(new_state["raw_search_results"]), 1)
        self.assertEqual(new_state["constraints_memory"]["has_booking_link"], "true")
        self.assertEqual(new_state["constraints_memory"]["search_context_mode"], "tool_calling")
        self.assertEqual(new_state["parsed_context"]["search_context"], "웹/벡터 통합 컨텍스트")
        self.assertTrue(new_state["parsed_context"]["search_strategy"]["tool_calling_used"])
        mock_invoke_with_tool_calls.assert_called_once()

    def test_curator_returns_three_to_five_recommendations(self):
        agent = CuratorAgent(enable_rag=True)
        state = {
            "user_query": "비 오는 날 성수에서 데이트 뭐해?",
            "region": "성수",
            "companion": "썸",
            "weather": "비",
            "time_slot": "저녁",
            "budget_level": "보통",
            "mobility": "대중교통",
            "parsed_context": {"region": "성수", "companion": "썸", "weather": "비", "budget_level": "보통"},
            "search_queries": ["성수 비 오는 날 데이트 추천"],
            "raw_search_results": [
                {
                    "title": "성수 전시 추천",
                    "body": "실내 데이트에 좋은 전시 공간",
                    "href": "https://example.com/exhibit",
                    "reservation_url": "https://example.com/exhibit/book",
                    "category": "전시",
                    "area": "성수",
                    "score": 7.5,
                },
                {
                    "title": "성수 감성 카페",
                    "body": "조용하게 대화하기 좋은 카페",
                    "href": "https://example.com/cafe",
                    "reservation_url": "",
                    "category": "카페",
                    "area": "성수",
                    "score": 6.3,
                },
            ],
            "curated_candidates": [],
            "final_plan": {},
            "decision_memory": [],
            "constraints_memory": {"retry_attempts": "0", "broaden_search": "false"},
            "messages": [],
            "current_step": "RETRIEVER",
            "completed": False,
        }

        new_state = agent.run(state)

        self.assertGreaterEqual(len(new_state["curated_candidates"]), 3)
        self.assertLessEqual(len(new_state["curated_candidates"]), 5)
        self.assertIn("why_fit", new_state["curated_candidates"][0])
        self.assertEqual(new_state["current_step"], "CURATOR")


if __name__ == "__main__":
    unittest.main()

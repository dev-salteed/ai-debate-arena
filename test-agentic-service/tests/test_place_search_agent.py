import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.place_search_agent import PlaceSearchAgent


class PlaceSearchAgentTests(unittest.TestCase):
    def test_build_query_candidates_broadens_on_retry(self):
        agent = PlaceSearchAgent(enable_rag=True)
        queries = agent._build_query_candidates(
            {
                "parsed_query": {
                    "region": "강남",
                    "venue_type": "카페",
                    "purpose": "작업",
                    "atmosphere": ["조용한"],
                    "search_queries": ["강남 조용한 카페 작업"],
                },
                "search_iterations": 1,
            }
        )
        self.assertGreaterEqual(len(queries), 2)
        self.assertIn("강남 카페 추천", queries)

    @patch("workflow.agents.place_search_agent.invoke_with_tool_calls")
    def test_run_updates_search_brief_and_iterations(self, mock_invoke):
        mock_invoke.return_value = """{
          "search_strategy": "작업 적합성 중심으로 탐색했습니다.",
          "queries_used": ["강남 조용한 카페 작업"],
          "source_highlights": [
            {"place": "카페 A", "evidence": "콘센트와 넓은 좌석", "source": "검색 결과 1"}
          ],
          "freshness_note": "최근 후기 반영",
          "rationale": "검색어를 목적 중심으로 묶었습니다."
        }"""

        agent = PlaceSearchAgent(enable_rag=True)
        new_state = agent.run(
            {
                "user_query": "강남에서 작업하기 좋은 카페",
                "parsed_query": {
                    "region": "강남",
                    "subregion": "",
                    "venue_type": "카페",
                    "purpose": "작업",
                    "atmosphere": ["조용한"],
                    "price_range": "중간",
                    "must_have": ["콘센트"],
                    "avoid": [],
                    "search_queries": ["강남 조용한 카페 작업"],
                },
                "search_brief": {},
                "candidate_places": [],
                "recommendations": None,
                "search_iterations": 0,
                "max_search_iterations": 2,
                "decision_memory": [],
                "constraints_memory": {},
                "current_step": "QUERY_PARSER",
                "messages": [],
                "completed": False,
            }
        )

        self.assertEqual(new_state["current_step"], "PLACE_SEARCH")
        self.assertEqual(new_state["search_iterations"], 1)
        self.assertEqual(new_state["search_brief"]["queries_used"][0], "강남 조용한 카페 작업")


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import build_continued_state, build_initial_state


class UiMultiturnStateTests(unittest.TestCase):
    def test_build_initial_state_sets_clean_defaults(self):
        state = build_initial_state(
            user_query="강남에서 조용한 카페 추천",
            max_search_iterations=3,
            thread_id="thread-1",
        )
        self.assertEqual(state["user_query"], "강남에서 조용한 카페 추천")
        self.assertEqual(state["max_search_iterations"], 3)
        self.assertEqual(state["search_iterations"], 0)
        self.assertEqual(state["current_step"], "")
        self.assertFalse(state["completed"])
        self.assertEqual(state["messages"], [])

    def test_build_continued_state_preserves_memory_and_resets_outputs(self):
        previous = build_initial_state("홍대 데이트 카페 추천", thread_id="thread-1")
        previous["decision_memory"] = ["QUERY_PARSER: 홍대 / 카페 / 데이트"]
        previous["constraints_memory"] = {"region": "홍대", "purpose": "데이트"}
        previous["search_brief"] = {"search_strategy": "이전 검색"}
        previous["candidate_places"] = [{"name": "카페 A"}]
        previous["recommendations"] = {"summary": "이전 추천", "recommendations": [], "follow_up_questions": []}
        previous["completed"] = True
        previous["current_step"] = "RECOMMENDATION"

        continued = build_continued_state(
            previous_state=previous,
            user_query="홍대에서 조금 더 조용한 카페로 다시 추천",
            continued_last_run=True,
        )

        self.assertEqual(continued["user_query"], "홍대에서 조금 더 조용한 카페로 다시 추천")
        self.assertEqual(continued["search_brief"], {})
        self.assertEqual(continued["candidate_places"], [])
        self.assertEqual(continued["recommendations"]["summary"], "")
        self.assertFalse(continued["completed"])
        self.assertEqual(continued["current_step"], "")
        self.assertIn("홍대", continued["constraints_memory"]["region"])
        self.assertIn("데이트", continued["constraints_memory"]["purpose"])


if __name__ == "__main__":
    unittest.main()

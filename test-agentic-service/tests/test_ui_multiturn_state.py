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
            user_query="비 오는 날 성수에서 데이트 뭐해?",
            region="성수",
            companion="썸",
            weather="비",
            time_slot="저녁",
            budget_level="보통",
            mobility="대중교통",
        )
        self.assertEqual(state["user_query"], "비 오는 날 성수에서 데이트 뭐해?")
        self.assertEqual(state["region"], "성수")
        self.assertEqual(state["current_step"], "")
        self.assertFalse(state["completed"])
        self.assertEqual(state["messages"], [])
        self.assertTrue({"user_query", "region", "companion"}.issubset(state.keys()))

    def test_build_continued_state_preserves_memory_and_overrides_inputs(self):
        previous = build_initial_state(
            user_query="혼자 조용히 놀고 싶어",
            region="서울",
            companion="혼자",
            weather="상관없음",
            time_slot="오후",
            budget_level="가볍게",
            mobility="도보 위주",
        )
        previous["decision_memory"] = ["SUPERVISOR: 검색 범위를 넓혀 한 번 더 수집"]
        previous["constraints_memory"] = {"retry_attempts": "1", "broaden_search": "true"}
        previous["completed"] = True
        previous["current_step"] = "RESPONSE_COMPOSER"

        continued = build_continued_state(
            previous_state=previous,
            user_query="부산에서 친구랑 저녁 코스 추천해줘",
            region="부산",
            companion="친구",
            weather="맑음",
            time_slot="저녁",
            budget_level="보통",
            mobility="대중교통",
        )

        self.assertEqual(continued["user_query"], "부산에서 친구랑 저녁 코스 추천해줘")
        self.assertEqual(continued["region"], "부산")
        self.assertEqual(continued["companion"], "친구")
        self.assertFalse(continued["completed"])
        self.assertEqual(continued["current_step"], "")
        self.assertIn("검색 범위를 넓혀", continued["decision_memory"][0])
        self.assertEqual(continued["constraints_memory"]["retry_attempts"], "1")


if __name__ == "__main__":
    unittest.main()

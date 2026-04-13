import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.planner_agent import PlannerAgent
from workflow.agents.response_composer_agent import ResponseComposerAgent


class PlannerAndResponseTests(unittest.TestCase):
    def test_planner_creates_required_final_plan_keys(self):
        planner = PlannerAgent(enable_rag=True)
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
                "keywords": ["전시", "카페"],
            },
            "search_queries": [],
            "raw_search_results": [],
            "curated_candidates": [
                {"name": "전시 A", "category": "전시", "area": "성수", "why_fit": "실내 데이트에 좋아요", "reservation_url": "https://a"},
                {"name": "카페 B", "category": "카페", "area": "성수", "why_fit": "대화하기 좋아요", "reservation_url": ""},
                {"name": "체험 C", "category": "체험", "area": "성수", "why_fit": "함께 하기 좋아요", "reservation_url": "https://c"},
            ],
            "final_plan": {},
            "decision_memory": [],
            "constraints_memory": {},
            "messages": [],
            "current_step": "CURATOR",
            "completed": False,
        }

        new_state = planner.run(state)
        final_plan = new_state["final_plan"]

        self.assertIn("summary", final_plan)
        self.assertIn("recommendations", final_plan)
        self.assertIn("timeline", final_plan)
        self.assertIn("route_summary", final_plan)
        self.assertIn("booking_links", final_plan)
        self.assertGreaterEqual(len(final_plan["timeline"]), 3)
        self.assertIn("PLANNER_PROMPT", "\n".join(new_state["decision_memory"]))
        self.assertIn("role_prompt=Planner", new_state["messages"][-1]["content"])

    def test_response_composer_fills_missing_structure(self):
        composer = ResponseComposerAgent(enable_rag=True)
        state = {
            "user_query": "오늘 뭐해?",
            "region": "서울",
            "companion": "혼자",
            "weather": "상관없음",
            "time_slot": "오후",
            "budget_level": "가볍게",
            "mobility": "도보 위주",
            "parsed_context": {"region": "서울", "companion": "혼자", "weather": "상관없음", "time_slot": "오후"},
            "search_queries": [],
            "raw_search_results": [],
            "curated_candidates": [{"name": "서울 카페 코스", "category": "카페", "area": "서울", "why_fit": "혼자 머물기 좋음", "source_url": "https://example.com"}],
            "final_plan": {"summary": "가볍게 갈 만한 곳을 골랐어요."},
            "decision_memory": [],
            "constraints_memory": {},
            "messages": [],
            "current_step": "PLANNER",
            "completed": False,
        }

        new_state = composer.run(state)
        final_plan = new_state["final_plan"]

        self.assertTrue(new_state["completed"])
        self.assertGreaterEqual(len(final_plan["recommendations"]), 3)
        self.assertGreaterEqual(len(final_plan["timeline"]), 3)
        self.assertIn("follow_up_prompt", final_plan)


if __name__ == "__main__":
    unittest.main()

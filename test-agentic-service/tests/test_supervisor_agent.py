import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.supervisor_agent import SupervisorAgent
from workflow.state import AgentType


def make_state(**overrides):
    base = {
        "user_query": "비 오는 날 성수에서 데이트 뭐해?",
        "region": "성수",
        "companion": "썸",
        "weather": "비",
        "time_slot": "저녁",
        "budget_level": "보통",
        "mobility": "대중교통",
        "parsed_context": {"region": "성수", "weather": "비"},
        "search_queries": ["성수 실내 데이트 추천"],
        "raw_search_results": [],
        "curated_candidates": [],
        "final_plan": {},
        "decision_memory": [],
        "constraints_memory": {"retry_attempts": "0", "broaden_search": "false"},
        "current_step": AgentType.CURATOR,
        "messages": [],
        "completed": False,
    }
    base.update(overrides)
    return base


class SupervisorRoutingTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = SupervisorAgent()

    def test_routes_to_retriever_after_context_analysis(self):
        state = make_state(current_step=AgentType.CONTEXT_ANALYZER)
        routed = self.supervisor.route_next(state)
        self.assertEqual(routed, AgentType.RETRIEVER)

    def test_requests_broader_retry_when_candidates_are_insufficient(self):
        state = make_state(
            curated_candidates=[{"name": "테스트 장소", "reservation_url": ""}],
            current_step=AgentType.CURATOR,
        )
        updated = self.supervisor.run(state)

        self.assertEqual(updated["constraints_memory"]["broaden_search"], "true")
        self.assertEqual(updated["constraints_memory"]["retry_attempts"], "1")
        self.assertIn("검색 범위를 넓혀", updated["messages"][-1]["content"])

        routed = self.supervisor.route_next(updated)
        self.assertEqual(routed, AgentType.RETRIEVER)

    def test_routes_to_planner_when_candidates_are_sufficient(self):
        state = make_state(
            curated_candidates=[
                {"name": "A", "reservation_url": "https://a"},
                {"name": "B", "reservation_url": "https://b"},
                {"name": "C", "reservation_url": "https://c"},
            ],
            current_step=AgentType.CURATOR,
        )
        updated = self.supervisor.run(state)
        routed = self.supervisor.route_next(updated)
        self.assertEqual(routed, AgentType.PLANNER)

    def test_routes_to_response_composer_after_planner(self):
        state = make_state(current_step=AgentType.PLANNER)
        routed = self.supervisor.route_next(state)
        self.assertEqual(routed, AgentType.RESPONSE_COMPOSER)


if __name__ == "__main__":
    unittest.main()

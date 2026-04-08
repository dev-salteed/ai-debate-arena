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
        "user_query": "홍대 데이트 카페 추천",
        "parsed_query": {
            "region": "홍대",
            "venue_type": "카페",
            "purpose": "데이트",
        },
        "search_brief": {},
        "candidate_places": [],
        "recommendations": None,
        "search_iterations": 1,
        "max_search_iterations": 2,
        "decision_memory": [],
        "constraints_memory": {},
        "current_step": AgentType.RAG_PROCESSOR,
        "messages": [],
        "completed": False,
    }
    base.update(overrides)
    return base


class SupervisorRoutingTests(unittest.TestCase):
    def setUp(self):
        self.supervisor = SupervisorAgent()

    def test_routes_to_recommendation_when_candidates_exist(self):
        state = make_state(candidate_places=[{"name": "카페 A"}])
        routed = self.supervisor.route_next(state)
        self.assertEqual(routed, AgentType.RECOMMENDATION)

    def test_retries_search_when_candidates_are_missing(self):
        state = make_state()
        updated = self.supervisor.run(state)
        self.assertEqual(updated["constraints_memory"]["broaden_search"], "true")
        self.assertIn("검색 범위를 완화", updated["messages"][-1]["content"])
        routed = self.supervisor.route_next(updated)
        self.assertEqual(routed, AgentType.PLACE_SEARCH)

    def test_routes_to_recommendation_when_retry_budget_is_exhausted(self):
        state = make_state(search_iterations=2)
        routed = self.supervisor.route_next(state)
        self.assertEqual(routed, AgentType.RECOMMENDATION)


if __name__ == "__main__":
    unittest.main()

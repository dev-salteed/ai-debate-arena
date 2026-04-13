import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.context_analyzer_agent import ContextAnalyzerAgent


class ContextAnalyzerTests(unittest.TestCase):
    def test_extracts_structured_context_from_user_query(self):
        agent = ContextAnalyzerAgent(enable_rag=False)
        state = {
            "user_query": "비 오는 날 성수에서 썸이랑 전시 보고 카페 가고 싶어",
            "region": "서울",
            "companion": "상관없음",
            "weather": "상관없음",
            "time_slot": "상관없음",
            "budget_level": "보통",
            "mobility": "상관없음",
            "parsed_context": {},
            "search_queries": [],
            "raw_search_results": [],
            "curated_candidates": [],
            "final_plan": {},
            "decision_memory": [],
            "constraints_memory": {},
            "messages": [],
            "current_step": "",
            "completed": False,
        }

        new_state = agent.run(state)

        self.assertEqual(new_state["region"], "성수")
        self.assertEqual(new_state["companion"], "썸")
        self.assertEqual(new_state["weather"], "비")
        self.assertIn("전시", new_state["parsed_context"]["keywords"])
        self.assertEqual(new_state["parsed_context"]["prompt_strategy"]["role"], "Context Analyzer")
        self.assertEqual(new_state["parsed_context"]["prompt_strategy"]["few_shot_count"], 2)
        self.assertIn("CONTEXT_ANALYZER_PROMPT", "\n".join(new_state["decision_memory"]))
        self.assertEqual(new_state["current_step"], "CONTEXT_ANALYZER")


if __name__ == "__main__":
    unittest.main()

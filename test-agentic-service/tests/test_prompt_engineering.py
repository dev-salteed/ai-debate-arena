import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.place_search_agent import PlaceSearchAgent
from workflow.agents.query_parser_agent import QueryParserAgent
from workflow.agents.recommendation_agent import RecommendationAgent


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


class _SequentialLLM:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0

    def invoke(self, _messages):
        if self._idx >= len(self._responses):
            return _FakeResponse(self._responses[-1])
        content = self._responses[self._idx]
        self._idx += 1
        return _FakeResponse(content)


def make_state():
    return {
        "user_query": "강남에서 조용한 카페 추천해줘",
        "parsed_query": {},
        "search_brief": {},
        "candidate_places": [],
        "recommendations": None,
        "search_iterations": 0,
        "max_search_iterations": 2,
        "decision_memory": [],
        "constraints_memory": {},
        "current_step": "",
        "messages": [],
        "completed": False,
    }


class PromptEngineeringTests(unittest.TestCase):
    def test_prompts_include_few_shot_and_consistency_guards(self):
        parser = QueryParserAgent()
        search = PlaceSearchAgent(enable_rag=False)
        recommendation = RecommendationAgent()

        self.assertIn("Few-shot 예시", parser.system_prompt)
        self.assertIn("Few-shot 예시", search.system_prompt)
        self.assertIn("Few-shot 예시", recommendation.system_prompt)
        self.assertIn("rationale", parser.system_prompt)
        self.assertIn("필수 키", parser.system_prompt)

    @patch("workflow.agents.query_parser_agent.get_llm")
    def test_query_parser_repairs_missing_required_keys_once(self, mock_get_llm):
        mock_get_llm.return_value = _SequentialLLM(
            [
                """{"region":"강남","venue_type":"카페","purpose":"작업","atmosphere":["조용한"],"price_range":"중간","must_have":[],"avoid":[],"search_queries":["강남 조용한 카페"],"response_language":"ko"}""",
                """{"region":"강남","subregion":"","venue_type":"카페","purpose":"작업","atmosphere":["조용한"],"price_range":"중간","must_have":[],"avoid":[],"search_queries":["강남 조용한 카페"],"response_language":"ko","rationale":"작업 목적과 조용한 분위기를 반영했습니다."}""",
            ]
        )

        agent = QueryParserAgent()
        new_state = agent.run(make_state())
        self.assertEqual(new_state["parsed_query"]["region"], "강남")
        self.assertEqual(new_state["parsed_query"]["rationale"], "작업 목적과 조용한 분위기를 반영했습니다.")

    @patch("workflow.agents.place_search_agent.invoke_with_tool_calls")
    def test_place_search_uses_place_context_tool_when_rag_enabled(self, mock_invoke):
        mock_invoke.return_value = """{
          "search_strategy": "조용한 작업 카페 위주 탐색",
          "queries_used": ["강남 조용한 카페 작업"],
          "source_highlights": [{"place":"카페 A","evidence":"넓은 좌석","source":"검색 결과 1"}],
          "freshness_note": "최근 후기 반영",
          "rationale": "검색 결과 요약"
        }"""

        agent = PlaceSearchAgent(enable_rag=True)
        state = make_state()
        state["parsed_query"] = {
            "region": "강남",
            "subregion": "",
            "venue_type": "카페",
            "purpose": "작업",
            "atmosphere": ["조용한"],
            "price_range": "중간",
            "must_have": [],
            "avoid": [],
            "search_queries": ["강남 조용한 카페 작업"],
        }

        new_state = agent.run(state)
        self.assertEqual(new_state["search_brief"]["queries_used"][0], "강남 조용한 카페 작업")
        self.assertEqual(
            getattr(mock_invoke.call_args.kwargs["tools"][0], "name", ""),
            "search_place_context",
        )


if __name__ == "__main__":
    unittest.main()

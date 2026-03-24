import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure `app` directory is importable.
ROOT_DIR = Path(__file__).resolve().parents[1]
APP_DIR = ROOT_DIR / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from workflow.agents.tool_runner import invoke_with_tool_calls


class _FakeAIResponse:
    def __init__(self, content: str, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeLLM:
    def __init__(self, responses):
        self._responses = responses
        self._idx = 0
        self.first_invoke_messages = None

    def bind_tools(self, _tools):
        return self

    def invoke(self, messages):
        if self.first_invoke_messages is None:
            self.first_invoke_messages = messages
        if self._idx >= len(self._responses):
            return self._responses[-1]
        resp = self._responses[self._idx]
        self._idx += 1
        return resp


class _FakeTool:
    name = "search_web"

    def invoke(self, args):
        return f"tool_result_for:{args.get('query', '')}"


class ToolRunnerReactTests(unittest.TestCase):
    @patch("workflow.agents.tool_runner.get_llm")
    def test_react_policy_and_tool_loop(self, mock_get_llm):
        fake_llm = _FakeLLM(
            [
                _FakeAIResponse(
                    content="도구 호출 필요",
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "search_web",
                            "args": {"query": "도쿄 여행"},
                        }
                    ],
                ),
                _FakeAIResponse(
                    content='{"recommended_cities":[{"city":"도쿄","country":"일본","reason":"미식"}],"rationale":"검색 근거 반영"}'
                ),
            ]
        )
        mock_get_llm.return_value = fake_llm

        logger = logging.getLogger("test_tool_runner_react")
        result = invoke_with_tool_calls(
            system_prompt="테스트 시스템 프롬프트",
            user_prompt="도시 추천",
            tools=[_FakeTool()],
            logger=logger,
            max_iterations=3,
        )

        self.assertIn("recommended_cities", result)
        first_messages = fake_llm.first_invoke_messages
        self.assertEqual(first_messages[0].content, "테스트 시스템 프롬프트")
        self.assertIn("ReAct", first_messages[1].content)


if __name__ == "__main__":
    unittest.main()


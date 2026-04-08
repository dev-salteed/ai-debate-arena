import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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
        response = self._responses[self._idx]
        self._idx += 1
        return response


class _FakeTool:
    name = "search_place_context"

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
                            "name": "search_place_context",
                            "args": {"query": "홍대 데이트 카페"},
                        }
                    ],
                ),
                _FakeAIResponse(content='{"recommendations":[{"name":"카페 A"}]}'),
            ]
        )
        mock_get_llm.return_value = fake_llm

        result = invoke_with_tool_calls(
            system_prompt="테스트 시스템 프롬프트",
            user_prompt="홍대 데이트 카페 추천",
            tools=[_FakeTool()],
            logger=logging.getLogger("test_tool_runner_react"),
            max_iterations=3,
        )

        self.assertIn("recommendations", result)
        first_messages = fake_llm.first_invoke_messages
        self.assertEqual(first_messages[0].content, "테스트 시스템 프롬프트")
        self.assertIn("ReAct", first_messages[1].content)

    @patch("workflow.agents.tool_runner.get_llm")
    def test_returns_last_observation_when_requested(self, mock_get_llm):
        fake_llm = _FakeLLM(
            [
                _FakeAIResponse(
                    content="도구 호출 필요",
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "search_place_context",
                            "args": {"query": "강남 조용한 카페"},
                        }
                    ],
                ),
                _FakeAIResponse(content='{"ok":true}'),
            ]
        )
        mock_get_llm.return_value = fake_llm

        final_text, last_observation = invoke_with_tool_calls(
            system_prompt="테스트 시스템 프롬프트",
            user_prompt="강남 조용한 카페 추천",
            tools=[_FakeTool()],
            logger=logging.getLogger("test_tool_runner_observation"),
            max_iterations=3,
            return_last_observation=True,
        )

        self.assertIn('"ok":true', final_text)
        self.assertIn("tool_result_for:강남 조용한 카페", last_observation)


if __name__ == "__main__":
    unittest.main()

"""Tool binding 기반 LLM 실행 유틸리티."""
from __future__ import annotations

from typing import Any, List, Optional
import logging
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from utils.config import get_llm

REACT_POLICY = """도구 사용 시 ReAct 방식으로 진행하세요.
- Thought: 무엇을 확인할지 한 문장으로 내부 정리
- Action: 필요한 도구 호출
- Observation: 도구 결과를 근거로 반영
최종 응답은 반드시 사용자 요구 JSON 스키마만 출력하세요."""


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    chunks.append(str(text))
            else:
                chunks.append(str(item))
        return "\n".join(chunks).strip()
    if content is None:
        return ""
    return str(content)


def invoke_with_tool_calls(
    system_prompt: str,
    user_prompt: str,
    tools: List[BaseTool],
    logger: Optional[logging.Logger] = None,
    max_iterations: int = 3,
) -> str:
    """LLM에 도구를 바인딩해 tool call 루프를 수행하고 최종 텍스트를 반환한다."""
    messages = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=REACT_POLICY),
        HumanMessage(content=user_prompt),
    ]

    if not tools:
        response = get_llm().invoke(messages)
        return _content_to_text(response.content).strip()

    llm = get_llm().bind_tools(tools)
    tools_by_name = {tool.name: tool for tool in tools}

    for _ in range(max_iterations):
        response = llm.invoke(messages)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return _content_to_text(response.content).strip()

        if logger:
            logger.info(f"[ReAct] iteration start tool_calls={len(tool_calls)}")

        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "")
            tool_args = tool_call.get("args", {}) or {}
            tool_call_id = tool_call.get("id", "")

            tool = tools_by_name.get(tool_name)
            if tool is None:
                tool_result = f"알 수 없는 도구입니다: {tool_name}"
            else:
                try:
                    tool_result = tool.invoke(tool_args)
                except Exception as e:
                    if logger:
                        logger.warning(f"[Tool 호출 실패] {tool_name}: {e}")
                    tool_result = f"도구 실행 중 오류: {e}"

            if logger:
                logger.info(
                    f"[ReAct] action={tool_name} args={tool_args} "
                    f"observation_len={len(str(tool_result))}"
                )

            messages.append(
                ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                )
            )

    # 최대 루프 후에도 종료되지 않으면 마지막으로 한 번 더 답변 시도
    final_response = llm.invoke(messages)
    return _content_to_text(final_response.content).strip()

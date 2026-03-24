"""Tool binding 기반 LLM 실행 유틸리티."""
from __future__ import annotations

from typing import Any, List, Optional
import logging
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from utils.config import get_llm


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
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

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
                    f"[Tool 호출] {tool_name} args={tool_args} "
                    f"result_len={len(str(tool_result))}"
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

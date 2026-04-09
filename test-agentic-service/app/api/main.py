"""FastAPI backend for the 오늘 뭐해? workflow."""
from __future__ import annotations

from typing import Any, Dict, Optional
import uuid

from fastapi import FastAPI
from pydantic import BaseModel, Field

from workflow.graph import create_today_what_graph
from workflow.state import TodayWhatState


class TodayWhatPlanRequest(BaseModel):
    user_query: str = Field(..., min_length=1, description="사용자 자연어 요청")
    region: str = Field(default="서울", min_length=1)
    companion: str = Field(default="상관없음")
    weather: str = Field(default="상관없음")
    time_slot: str = Field(default="상관없음")
    budget_level: str = Field(default="상관없음")
    mobility: str = Field(default="상관없음")
    enable_rag: bool = Field(default=True)
    thread_id: Optional[str] = Field(default=None)


class TodayWhatPlanResponse(BaseModel):
    status: str
    result: Dict[str, Any]


app = FastAPI(
    title="오늘 뭐해? API",
    version="2.0.0",
    description="상황형 액티비티 추천과 일정 구성을 위한 LangGraph API",
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/plan", response_model=TodayWhatPlanResponse)
def create_plan(payload: TodayWhatPlanRequest) -> TodayWhatPlanResponse:
    initial_state = TodayWhatState(
        user_query=payload.user_query,
        region=payload.region,
        companion=payload.companion,
        weather=payload.weather,
        time_slot=payload.time_slot,
        budget_level=payload.budget_level,
        mobility=payload.mobility,
        parsed_context={},
        search_queries=[],
        raw_search_results=[],
        curated_candidates=[],
        final_plan={},
        decision_memory=[],
        constraints_memory={"retry_attempts": "0", "broaden_search": "false"},
        messages=[],
        current_step="",
        completed=False,
    )

    graph = create_today_what_graph(enable_rag=payload.enable_rag)
    thread_id = payload.thread_id or f"api-{uuid.uuid4()}"
    result = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )
    return TodayWhatPlanResponse(status="ok", result=result)

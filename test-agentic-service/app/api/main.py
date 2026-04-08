"""FastAPI backend for the dining recommendation workflow."""
from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import FastAPI
from pydantic import BaseModel, Field

from workflow.graph import create_dining_graph
from workflow.state import DiningState


class DiningRecommendationRequest(BaseModel):
    user_query: str = Field(..., min_length=1, description="자연어 추천 요청")
    enable_rag: bool = Field(default=True)
    max_search_iterations: int = Field(default=2, ge=1, le=4)


class DiningRecommendationResponse(BaseModel):
    status: str
    result: Dict[str, Any]


app = FastAPI(
    title="What Should I Eat API",
    version="2.0.0",
    description="LangGraph 기반 맛집/카페 추천 API",
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/recommend", response_model=DiningRecommendationResponse)
def recommend(payload: DiningRecommendationRequest) -> DiningRecommendationResponse:
    initial_state = DiningState(
        user_query=payload.user_query,
        parsed_query={},
        search_brief={},
        candidate_places=[],
        recommendations=None,
        search_iterations=0,
        max_search_iterations=payload.max_search_iterations,
        decision_memory=[],
        constraints_memory={},
        current_step="",
        messages=[],
        completed=False,
    )

    graph = create_dining_graph(enable_rag=payload.enable_rag)
    thread_id = f"api-{uuid.uuid4()}"
    result = graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": thread_id}},
    )
    return DiningRecommendationResponse(status="ok", result=result)

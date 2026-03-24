"""FastAPI backend for travel planning workflow."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from workflow.graph import create_travel_graph
from workflow.state import TravelState


class TravelPlanRequest(BaseModel):
    travel_theme: str = Field(..., min_length=1, description="여행 주제")
    travel_days: Optional[int] = Field(default=5, ge=1, le=30)
    budget: Optional[int] = Field(default=None, ge=0)
    departure_city: str = Field(default="서울")
    enable_rag: bool = Field(default=True)
    max_flight_search_attempts: int = Field(default=3, ge=1, le=10)


class TravelPlanResponse(BaseModel):
    status: str
    result: Dict[str, Any]


app = FastAPI(
    title="Travel Agentic Service API",
    version="1.0.0",
    description="LangGraph 기반 여행 계획 생성 API",
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/plan", response_model=TravelPlanResponse)
def create_plan(payload: TravelPlanRequest) -> TravelPlanResponse:
    initial_state = TravelState(
        travel_theme=payload.travel_theme,
        travel_days=payload.travel_days,
        budget=payload.budget if payload.budget and payload.budget > 0 else None,
        departure_city=payload.departure_city,
        recommended_cities=[],
        selected_city=None,
        selected_city_index=0,
        flight_info=None,
        flight_available=False,
        flight_unavailability_reason=None,
        flight_search_attempts=0,
        max_flight_search_attempts=payload.max_flight_search_attempts,
        itinerary=None,
        decision_memory=[],
        constraints_memory={},
        current_step="",
        messages=[],
        completed=False,
    )

    graph = create_travel_graph(enable_rag=payload.enable_rag)
    result = graph.invoke(initial_state)
    return TravelPlanResponse(status="ok", result=result)


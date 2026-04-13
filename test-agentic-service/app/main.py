"""오늘 뭐해? - 상황형 활동 추천 Streamlit UI."""
from __future__ import annotations

import html
import logging
import uuid
from typing import Any, Dict, List, Optional

import streamlit as st

from workflow.graph import create_today_what_graph
from workflow.state import TodayWhatState


logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)

LOGGER = logging.getLogger("today_what.ui")

COMPANION_OPTIONS = ["상관없음", "혼자", "썸", "연인", "친구", "가족"]
WEATHER_OPTIONS = ["상관없음", "맑음", "비", "흐림", "눈"]
TIME_SLOT_OPTIONS = ["상관없음", "오전", "오후", "저녁", "하루 종일"]
BUDGET_OPTIONS = ["상관없음", "가볍게", "보통", "여유"]
MOBILITY_OPTIONS = ["상관없음", "도보 위주", "대중교통", "택시 가능"]
REGION_PRESETS = ["서울", "성수", "홍대", "부산", "해운대", "제주", "서귀포"]

SCENARIO_PRESETS = [
    {
        "label": "비 오는 날 데이트",
        "today_what_query": "비 오는 날 썸 타는 사람이랑 갈만한 곳 추천해줘",
        "today_what_region": "서울",
        "today_what_companion": "썸",
        "today_what_weather": "비",
        "today_what_time_slot": "저녁",
        "today_what_budget_level": "보통",
        "today_what_mobility": "대중교통",
    },
    {
        "label": "혼자 조용히",
        "today_what_query": "혼자 조용하게 전시나 카페 가고 싶어",
        "today_what_region": "서울",
        "today_what_companion": "혼자",
        "today_what_weather": "상관없음",
        "today_what_time_slot": "오후",
        "today_what_budget_level": "가볍게",
        "today_what_mobility": "도보 위주",
    },
    {
        "label": "친구랑 가볍게",
        "today_what_query": "친구랑 전시 보고 카페 가고 저녁까지 보낼 곳 추천해줘",
        "today_what_region": "홍대",
        "today_what_companion": "친구",
        "today_what_weather": "맑음",
        "today_what_time_slot": "오후",
        "today_what_budget_level": "보통",
        "today_what_mobility": "대중교통",
    },
    {
        "label": "주말 코스",
        "today_what_query": "주말에 전시, 카페, 체험이 이어지는 코스 추천해줘",
        "today_what_region": "성수",
        "today_what_companion": "연인",
        "today_what_weather": "상관없음",
        "today_what_time_slot": "하루 종일",
        "today_what_budget_level": "보통",
        "today_what_mobility": "대중교통",
    },
]


def _default_final_plan() -> Dict[str, Any]:
    return {
        "summary": "",
        "situation_tags": [],
        "recommendations": [],
        "timeline": [],
        "route_summary": "",
        "booking_links": [],
        "notes": [],
        "follow_up_prompt": "",
        "fallback_option": "",
        "quick_tips": [],
    }


def _normalize_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _ensure_option(key: str, options: List[str], default: str) -> None:
    current = st.session_state.get(key)
    if current not in options:
        st.session_state[key] = default


def _ensure_session_defaults() -> None:
    defaults = {
        "today_what_plan_state": None,
        "today_what_messages": [],
        "today_what_logs": [],
        "today_what_thread_id": None,
        "today_what_thread_id_input": "",
        "today_what_continue_mode": False,
        "today_what_graph": None,
        "today_what_graph_rag": None,
        "today_what_enable_rag": True,
        "today_what_query": "",
        "today_what_region": "서울",
        "today_what_companion": "상관없음",
        "today_what_weather": "상관없음",
        "today_what_time_slot": "상관없음",
        "today_what_budget_level": "상관없음",
        "today_what_mobility": "상관없음",
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default

    _ensure_option("today_what_companion", COMPANION_OPTIONS, "상관없음")
    _ensure_option("today_what_weather", WEATHER_OPTIONS, "상관없음")
    _ensure_option("today_what_time_slot", TIME_SLOT_OPTIONS, "상관없음")
    _ensure_option("today_what_budget_level", BUDGET_OPTIONS, "상관없음")
    _ensure_option("today_what_mobility", MOBILITY_OPTIONS, "상관없음")


def initialize_state() -> None:
    """세션 상태 초기화."""
    _ensure_session_defaults()


def _apply_scenario_preset(preset: Dict[str, str]) -> None:
    for key, value in preset.items():
        st.session_state[key] = value


def _compose_fallback_query(
    region: str,
    companion: str,
    weather: str,
    time_slot: str,
    budget_level: str,
    mobility: str,
) -> str:
    parts: List[str] = []
    if region:
        parts.append(region)
    if companion != "상관없음":
        parts.append(f"{companion}이랑")
    if weather != "상관없음":
        parts.append(f"{weather} 날")
    if time_slot != "상관없음":
        parts.append(time_slot)
    if budget_level != "상관없음":
        parts.append(f"{budget_level} 예산")
    if mobility != "상관없음":
        parts.append(mobility)
    parts.append("오늘 뭐할지 추천")
    return " ".join(part for part in parts if part).strip()


def build_initial_state(
    user_query: str = "",
    region: str = "서울",
    companion: str = "상관없음",
    weather: str = "상관없음",
    time_slot: str = "상관없음",
    budget_level: str = "상관없음",
    mobility: str = "상관없음",
    enable_rag: bool = True,
) -> TodayWhatState:
    """새 계획 생성용 초기 상태."""
    state = TodayWhatState(
        user_query=_normalize_text(user_query),
        region=_normalize_text(region, "서울"),
        companion=companion,
        weather=weather,
        time_slot=time_slot,
        budget_level=budget_level,
        mobility=mobility,
        parsed_context={},
        search_queries=[],
        raw_search_results=[],
        curated_candidates=[],
        final_plan=_default_final_plan(),
        decision_memory=[],
        constraints_memory={"retry_attempts": "0", "broaden_search": "false"},
        messages=[],
        current_step="",
        completed=False,
    )
    return state


def build_continued_state(
    previous_state: TodayWhatState,
    user_query: str = "",
    region: str = "서울",
    companion: str = "상관없음",
    weather: str = "상관없음",
    time_slot: str = "상관없음",
    budget_level: str = "상관없음",
    mobility: str = "상관없음",
    enable_rag: bool = True,
) -> TodayWhatState:
    """이전 상태를 기반으로 입력 조건을 반영해 재실행 상태를 만든다."""
    previous = dict(previous_state or {})
    state = build_initial_state(
        user_query=user_query,
        region=region,
        companion=companion,
        weather=weather,
        time_slot=time_slot,
        budget_level=budget_level,
        mobility=mobility,
        enable_rag=enable_rag,
    )

    state["decision_memory"] = list(previous.get("decision_memory", []))
    constraints_memory = dict(previous.get("constraints_memory", {}))
    constraints_memory.setdefault("retry_attempts", "0")
    constraints_memory.setdefault("broaden_search", "false")
    state["constraints_memory"] = constraints_memory
    state["messages"] = list(previous.get("messages", []))
    state["current_step"] = ""
    state["completed"] = False
    state["parsed_context"] = {}
    state["search_queries"] = []
    state["raw_search_results"] = []
    state["curated_candidates"] = []
    state["final_plan"] = _default_final_plan()

    return state


def get_or_create_workflow_graph(enable_rag: bool):
    """RAG 모드별 그래프를 세션에 캐시한다."""
    if (
        st.session_state.today_what_graph is None
        or st.session_state.today_what_graph_rag != enable_rag
    ):
        st.session_state.today_what_graph = create_today_what_graph(enable_rag=enable_rag)
        st.session_state.today_what_graph_rag = enable_rag
    return st.session_state.today_what_graph


class StreamlitLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        log_entry = self.format(record)
        if "today_what_logs" in st.session_state:
            st.session_state.today_what_logs.append(log_entry)


def _clean_list(values: Any) -> List[Any]:
    if isinstance(values, list):
        return values
    if values in (None, ""):
        return []
    return [values]


def _normalize_link_item(item: Any, fallback_label: str) -> Optional[Dict[str, str]]:
    if not isinstance(item, dict):
        return None
    url = _normalize_text(item.get("url") or item.get("href") or item.get("source_url"), "")
    if not url:
        return None
    return {
        "label": _normalize_text(item.get("label") or item.get("name") or fallback_label, fallback_label),
        "url": url,
        "type": _normalize_text(item.get("type") or item.get("kind"), "링크"),
    }


def _normalize_plan(state: Dict[str, Any]) -> Dict[str, Any]:
    plan = dict(state.get("final_plan") or {})
    normalized = _default_final_plan()
    normalized.update({k: v for k, v in plan.items() if k in normalized})

    situation_tags = [tag for tag in _clean_list(normalized.get("situation_tags")) if tag]
    if not situation_tags:
        situation_tags = [
            state.get("region", "서울"),
            state.get("companion", "상관없음"),
            state.get("weather", "상관없음"),
            state.get("time_slot", "상관없음"),
        ]
        situation_tags = [tag for tag in situation_tags if tag and tag != "상관없음"]
    normalized["situation_tags"] = situation_tags

    recommendations: List[Dict[str, Any]] = []
    for idx, item in enumerate(_clean_list(plan.get("recommendations"))):
        if not isinstance(item, dict):
            continue
        recommendation = {
            "name": _normalize_text(item.get("name") or item.get("title") or f"추천 {idx + 1}", f"추천 {idx + 1}"),
            "category": _normalize_text(item.get("category"), "활동"),
            "area": _normalize_text(item.get("area"), state.get("region", "")),
            "why_fit": _normalize_text(item.get("why_fit") or item.get("reason"), "상황에 잘 맞는 후보예요."),
            "indoor_outdoor": _normalize_text(item.get("indoor_outdoor") or item.get("mode"), "상관없음"),
            "estimated_cost": _normalize_text(item.get("estimated_cost") or item.get("cost"), "상관없음"),
            "best_for": _normalize_text(item.get("best_for") or item.get("best_match"), "상관없음"),
            "source_url": _normalize_text(item.get("source_url") or item.get("url"), ""),
            "reservation_url": _normalize_text(item.get("reservation_url") or item.get("booking_url"), ""),
        }
        recommendations.append(recommendation)
    normalized["recommendations"] = recommendations

    timeline: List[Dict[str, Any]] = []
    for idx, item in enumerate(_clean_list(plan.get("timeline"))):
        if not isinstance(item, dict):
            continue
        timeline.append(
            {
                "time": _normalize_text(item.get("time") or item.get("slot") or item.get("label"), f"Step {idx + 1}"),
                "title": _normalize_text(item.get("title") or item.get("place") or item.get("name"), f"Step {idx + 1}"),
                "detail": _normalize_text(item.get("detail") or item.get("description") or item.get("plan"), ""),
                "duration": _normalize_text(item.get("duration") or item.get("estimated_duration"), ""),
                "location": _normalize_text(item.get("location") or item.get("area"), ""),
            }
        )
    normalized["timeline"] = timeline

    booking_links: List[Dict[str, str]] = []
    for item in _clean_list(plan.get("booking_links")):
        normalized_link = _normalize_link_item(item, "예약 링크")
        if normalized_link:
            booking_links.append(normalized_link)
    if not booking_links:
        for recommendation in recommendations:
            url = recommendation.get("reservation_url") or recommendation.get("source_url")
            if url:
                booking_links.append(
                    {
                        "label": recommendation.get("name", "추천 링크"),
                        "url": url,
                        "type": recommendation.get("category", "링크"),
                    }
                )
    normalized["booking_links"] = booking_links

    notes = [note for note in _clean_list(plan.get("notes")) if note]
    normalized["notes"] = notes
    quick_tips = [tip for tip in _clean_list(plan.get("quick_tips")) if tip]
    normalized["quick_tips"] = quick_tips
    normalized["summary"] = _normalize_text(plan.get("summary"), "아직 결과가 준비되지 않았어요.")
    normalized["route_summary"] = _normalize_text(plan.get("route_summary"), "")
    normalized["fallback_option"] = _normalize_text(plan.get("fallback_option"), "")
    normalized["follow_up_prompt"] = _normalize_text(
        plan.get("follow_up_prompt"),
        "원하는 분위기나 지역을 조금만 더 알려주면 다시 좁혀드릴게요.",
    )
    return normalized


def _escape(value: Any) -> str:
    return html.escape(_normalize_text(value, ""))


def _render_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #f5efe7;
            --bg-alt: #efe5d8;
            --surface: rgba(255, 252, 247, 0.88);
            --surface-strong: #fffaf4;
            --text: #1f2933;
            --muted: #5d676f;
            --line: rgba(31, 41, 51, 0.10);
            --accent: #335c52;
            --accent-2: #d87c57;
            --accent-soft: rgba(51, 92, 82, 0.12);
            --shadow: 0 18px 45px rgba(31, 41, 51, 0.10);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(216, 124, 87, 0.14), transparent 24%),
                radial-gradient(circle at top right, rgba(51, 92, 82, 0.12), transparent 28%),
                linear-gradient(180deg, #faf5ed 0%, #f5efe7 55%, #efe4d6 100%);
            color: var(--text);
        }

        [data-testid="stAppViewContainer"] > .main {
            background: transparent;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f8f1e6 0%, #f3e8da 100%);
            border-right: 1px solid rgba(31, 41, 51, 0.08);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2.5rem;
            max-width: 1200px;
        }

        h1, h2, h3, h4 {
            letter-spacing: -0.035em;
            color: var(--text);
        }

        p, label, .stMarkdown, .stCaption {
            color: var(--text);
        }

        .hero-shell {
            padding: 1.35rem 1.4rem 1.1rem;
            border-radius: 28px;
            background: linear-gradient(180deg, rgba(255, 250, 243, 0.96) 0%, rgba(255, 250, 243, 0.78) 100%);
            border: 1px solid rgba(31, 41, 51, 0.08);
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
        }

        .hero-kicker {
            text-transform: uppercase;
            letter-spacing: 0.18em;
            color: var(--accent);
            font-size: 0.72rem;
            margin-bottom: 0.35rem;
            font-weight: 700;
        }

        .hero-title {
            font-size: clamp(2.1rem, 4vw, 4rem);
            line-height: 0.98;
            margin: 0;
            color: var(--text);
        }

        .hero-copy {
            margin-top: 0.75rem;
            margin-bottom: 0;
            color: var(--muted);
            font-size: 1.02rem;
            max-width: 58rem;
        }

        .panel-card {
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 24px;
            box-shadow: var(--shadow);
            padding: 1rem 1rem 0.95rem;
            backdrop-filter: blur(14px);
        }

        .panel-card.compact {
            padding: 0.8rem 0.9rem;
        }

        .card-title {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
            color: var(--text);
        }

        .card-subtitle {
            color: var(--muted);
            font-size: 0.9rem;
            margin-bottom: 0.8rem;
        }

        .section-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin: 0 0 0.35rem 0;
        }

        .section-subtitle {
            color: var(--muted);
            margin: 0 0 0.85rem 0;
            font-size: 0.92rem;
        }

        .status-pill,
        .meta-pill,
        .tag-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            padding: 0.32rem 0.7rem;
            font-size: 0.82rem;
            line-height: 1;
            white-space: nowrap;
        }

        .status-pill {
            background: rgba(51, 92, 82, 0.11);
            color: var(--accent);
            border: 1px solid rgba(51, 92, 82, 0.20);
            font-weight: 600;
        }

        .meta-pill,
        .tag-pill {
            background: rgba(31, 41, 51, 0.05);
            color: var(--text);
            border: 1px solid rgba(31, 41, 51, 0.08);
        }

        .chip-note {
            margin-top: 0.5rem;
            color: var(--muted);
            font-size: 0.88rem;
        }

        .recommend-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 1rem;
        }

        .recommend-card,
        .timeline-card,
        .link-card,
        .memory-card,
        .summary-card {
            background: var(--surface-strong);
            border: 1px solid rgba(31, 41, 51, 0.08);
            border-radius: 22px;
            box-shadow: 0 12px 35px rgba(31, 41, 51, 0.08);
            padding: 1rem 1rem 0.95rem;
        }

        .recommend-card h4,
        .timeline-card h4,
        .link-card h4,
        .memory-card h4,
        .summary-card h4 {
            margin: 0.2rem 0 0.45rem 0;
            font-size: 1.02rem;
        }

        .recommend-card p,
        .timeline-card p,
        .link-card p,
        .memory-card p,
        .summary-card p {
            margin: 0.2rem 0;
            color: var(--text);
        }

        .recommend-badge,
        .timeline-badge,
        .link-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            padding: 0.28rem 0.65rem;
            font-size: 0.76rem;
            background: rgba(216, 124, 87, 0.12);
            color: #a54f2d;
            border: 1px solid rgba(216, 124, 87, 0.18);
            margin-bottom: 0.6rem;
        }

        .recommend-links {
            margin-top: 0.75rem;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }

        .recommend-links a,
        .link-card a {
            color: var(--accent);
            text-decoration: none;
            font-weight: 600;
        }

        .timeline-wrap {
            display: grid;
            gap: 0.9rem;
        }

        .timeline-row {
            display: grid;
            grid-template-columns: minmax(90px, 120px) 1fr;
            gap: 0.9rem;
            align-items: start;
        }

        .timeline-time {
            font-weight: 700;
            color: var(--accent);
        }

        .timeline-detail {
            color: var(--muted);
            margin-top: 0.25rem;
        }

        .info-strip {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin: 0.7rem 0 0.5rem;
        }

        .hero-cta button,
        div[data-testid="stButton"] > button {
            border-radius: 999px;
            border: 1px solid rgba(31, 41, 51, 0.10);
            background: linear-gradient(180deg, #ffffff 0%, #f5eee6 100%);
            color: var(--text);
            font-weight: 650;
            box-shadow: 0 10px 24px rgba(31, 41, 51, 0.08);
            transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
        }

        .hero-cta button:hover,
        div[data-testid="stButton"] > button:hover {
            border-color: rgba(51, 92, 82, 0.28);
            box-shadow: 0 14px 28px rgba(31, 41, 51, 0.12);
            transform: translateY(-1px);
        }

        div[data-testid="stButton"] > button[kind="primary"],
        .hero-cta button[kind="primary"] {
            background: linear-gradient(135deg, var(--accent) 0%, #496f64 100%);
            color: white;
            border: none;
        }

        div[data-testid="stButton"] > button[kind="primary"]:hover,
        .hero-cta button[kind="primary"]:hover {
            color: white;
        }

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] div,
        [data-testid="stMultiSelect"] div {
            border-radius: 18px;
        }

        [data-testid="stSidebar"] .stButton > button {
            width: 100%;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.9rem;
                padding-right: 0.9rem;
                padding-top: 1rem;
            }

            .hero-shell {
                padding: 1rem;
            }

            .timeline-row {
                grid-template-columns: 1fr;
                gap: 0.35rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_chip_grid(
    label: str,
    presets: List[Dict[str, str]],
    key_prefix: str,
    columns_per_row: int,
) -> None:
    st.markdown(f'<div class="card-title">{_escape(label)}</div>', unsafe_allow_html=True)
    for start in range(0, len(presets), columns_per_row):
        row = st.columns(columns_per_row)
        for offset, col in enumerate(row):
            idx = start + offset
            if idx >= len(presets):
                break
            preset = presets[idx]
            with col:
                st.button(
                    preset["label"],
                    key=f"{key_prefix}_{idx}",
                    use_container_width=True,
                    on_click=_apply_scenario_preset,
                    args=(preset,),
                )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="panel-card compact">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">실행 옵션</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-subtitle">thread_id 이어하기와 RAG 사용 여부를 정합니다.</div>', unsafe_allow_html=True)

        continue_disabled = st.session_state.today_what_plan_state is None
        st.checkbox(
            "이어서 실행",
            key="today_what_continue_mode",
            disabled=continue_disabled,
            help="같은 thread_id로 이전 맥락을 이어가면서 다시 계획합니다.",
        )
        st.text_input(
            "thread_id",
            key="today_what_thread_id_input",
            placeholder="자동 생성됩니다",
            help="직접 입력하면 동일한 thread를 계속 사용할 수 있습니다.",
        )
        st.checkbox(
            "DuckDuckGo 검색(RAG) 사용",
            key="today_what_enable_rag",
            help="검색 기반 최신 정보를 함께 반영합니다.",
        )
        if st.session_state.today_what_thread_id:
            st.caption(f"마지막 thread_id: `{st.session_state.today_what_thread_id}`")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="panel-card compact" style="margin-top: 0.9rem;">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">서비스 가이드</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="card-subtitle">
            오늘의 상황만 적으면, 활동 후보와 일정 흐름, 예약 가능한 링크까지 한 번에 정리합니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <ul style="margin: 0 0 0 1.1rem; padding: 0; color: var(--text);">
              <li>자연어 한 줄로 입력</li>
              <li>상황 선택 칩으로 빠르게 보정</li>
              <li>추천 카드 + 타임라인 + 링크 패널로 출력</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.today_what_logs:
            with st.expander("실행 로그", expanded=False):
                for log in st.session_state.today_what_logs[-60:]:
                    st.text(log)

        if st.session_state.today_what_plan_state:
            with st.expander("최근 메모리", expanded=False):
                st.write("decision_memory")
                st.code("\n".join(st.session_state.today_what_plan_state.get("decision_memory", [])) or "없음")
                st.write("constraints_memory")
                st.json(st.session_state.today_what_plan_state.get("constraints_memory", {}))


def _render_hero() -> None:
    st.markdown(
        """
        <div class="hero-shell">
          <div class="hero-kicker">오늘 뭐해?</div>
          <h1 class="hero-title">오늘 할 일, 한 번에 고르기</h1>
          <p class="hero-copy">
            자연어로 상황을 넣으면, 비슷한 선택지를 뒤져보지 않아도
            바로 실행 가능한 추천 카드와 동선, 링크를 묶어서 보여줍니다.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_input_area() -> None:
    left_col, right_col = st.columns([1.45, 1.0], gap="large")

    with left_col:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">프롬프트</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-subtitle">오늘의 분위기나 요청을 자연스럽게 적어주세요.</div>', unsafe_allow_html=True)
        st.text_area(
            "오늘 뭐할지",
            key="today_what_query",
            height=160,
            placeholder="예: 비 오는 날 썸 타는 사람이랑 갈만한 곳 추천해줘",
            label_visibility="collapsed",
        )
        st.markdown(
            '<div class="chip-note">짧아도 괜찮아요. 선택값이 있으면 함께 보강해서 실행합니다.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height: 0.75rem;'></div>", unsafe_allow_html=True)
        _render_chip_grid("상황 프리셋", SCENARIO_PRESETS, "scenario_preset", columns_per_row=2)
        st.markdown("</div>", unsafe_allow_html=True)

    with right_col:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">상황 선택</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-subtitle">칩과 셀렉트로 상황을 빠르게 정리합니다.</div>', unsafe_allow_html=True)

        st.text_input(
            "지역",
            key="today_what_region",
            placeholder="서울 / 성수 / 해운대 / 제주",
            help="검색의 중심이 되는 기준 지역입니다.",
        )
        st.markdown('<div style="height: 0.4rem;"></div>', unsafe_allow_html=True)
        st.caption("빠른 지역 칩")
        for start in range(0, len(REGION_PRESETS), 3):
            row = st.columns(3)
            for offset, col in enumerate(row):
                idx = start + offset
                if idx >= len(REGION_PRESETS):
                    break
                region = REGION_PRESETS[idx]
                with col:
                    st.button(
                        region,
                        key=f"region_chip_{idx}",
                        use_container_width=True,
                        on_click=lambda value=region: st.session_state.__setitem__("today_what_region", value),
                    )

        st.markdown('<div style="height: 0.35rem;"></div>', unsafe_allow_html=True)
        st.selectbox("동행", COMPANION_OPTIONS, key="today_what_companion")
        st.selectbox("날씨", WEATHER_OPTIONS, key="today_what_weather")
        st.selectbox("시간대", TIME_SLOT_OPTIONS, key="today_what_time_slot")
        st.selectbox("예산 감도", BUDGET_OPTIONS, key="today_what_budget_level")
        st.selectbox("이동 방식", MOBILITY_OPTIONS, key="today_what_mobility")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_submit_area() -> bool:
    st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)
    return st.button("오늘 뭐할지 추천받기", type="primary", use_container_width=True)


def _render_status_strip(state: Dict[str, Any], continued: bool) -> None:
    tags = []
    for value in (
        state.get("region"),
        state.get("companion"),
        state.get("weather"),
        state.get("time_slot"),
        state.get("budget_level"),
        state.get("mobility"),
    ):
        if value and value != "상관없음":
            tags.append(value)

    strip_html = ["<div class='info-strip'>"]
    strip_html.append(f"<span class='status-pill'>Thread ID: { _escape(st.session_state.today_what_thread_id or '미생성') }</span>")
    strip_html.append(f"<span class='status-pill'>이어하기: {'예' if continued else '아니오'}</span>")
    strip_html.append(f"<span class='status-pill'>RAG: {'켜짐' if st.session_state.today_what_enable_rag else '꺼짐'}</span>")
    for tag in tags:
        strip_html.append(f"<span class='tag-pill'>{_escape(tag)}</span>")
    strip_html.append("</div>")
    st.markdown("".join(strip_html), unsafe_allow_html=True)


def _render_summary_card(plan: Dict[str, Any]) -> None:
    tags = plan.get("situation_tags", [])
    tag_html = "".join(f"<span class='meta-pill'>{_escape(tag)}</span>" for tag in tags[:6])
    quick_tips = plan.get("quick_tips", [])
    quick_tip_html = ""
    if quick_tips:
        quick_tip_html = "<ul style='margin: 0.7rem 0 0 1.1rem; color: var(--text);'>" + "".join(
            f"<li>{_escape(tip)}</li>" for tip in quick_tips[:4]
        ) + "</ul>"

    st.markdown(
        f"""
        <div class="summary-card">
          <div class="recommend-badge">추천 요약</div>
          <h4>{_escape(plan.get('summary') or '추천 결과를 정리하는 중이에요.')}</h4>
          <div style="display:flex; gap:0.45rem; flex-wrap:wrap; margin-top:0.6rem;">{tag_html}</div>
          {quick_tip_html}
          <p style="margin-top:0.85rem; color: var(--muted);"><strong>다음 제안:</strong> {_escape(plan.get('follow_up_prompt'))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_recommendations(plan: Dict[str, Any]) -> None:
    recommendations = plan.get("recommendations", [])
    st.markdown('<div class="section-title">추천 카드</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">상황에 맞는 곳을 3~5개 정도로 추려 보여줍니다.</div>', unsafe_allow_html=True)

    if not recommendations:
        st.info("아직 추천 카드가 비어 있어요. 프롬프트를 조금 더 구체적으로 바꾸거나 RAG를 켜보세요.")
        return

    cols = st.columns(2, gap="large")
    for idx, recommendation in enumerate(recommendations):
        col = cols[idx % 2]
        with col:
            source_url = recommendation.get("source_url")
            reservation_url = recommendation.get("reservation_url")
            links_html = []
            if source_url:
                links_html.append(f'<a href="{_escape(source_url)}" target="_blank" rel="noopener noreferrer">출처</a>')
            if reservation_url:
                links_html.append(f'<a href="{_escape(reservation_url)}" target="_blank" rel="noopener noreferrer">예약/방문</a>')
            link_block = ""
            if links_html:
                link_block = '<div class="recommend-links">' + " | ".join(links_html) + '</div>'

            st.markdown(
                f"""
                <div class="recommend-card">
                  <div class="recommend-badge">{_escape(recommendation.get('category', '활동'))}</div>
                  <h4>{_escape(recommendation.get('name', '추천 장소'))}</h4>
                  <p><strong>지역:</strong> {_escape(recommendation.get('area', ''))}</p>
                  <p><strong>실내/야외:</strong> {_escape(recommendation.get('indoor_outdoor', '상관없음'))}</p>
                  <p><strong>예산:</strong> {_escape(recommendation.get('estimated_cost', '상관없음'))}</p>
                  <p><strong>어울리는 상황:</strong> {_escape(recommendation.get('best_for', '상관없음'))}</p>
                  <p style="margin-top:0.55rem; color: var(--muted);">{_escape(recommendation.get('why_fit', ''))}</p>
                  {link_block}
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_timeline(plan: Dict[str, Any]) -> None:
    st.markdown('<div class="section-title" style="margin-top: 0.4rem;">타임라인</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">시간대별로 어떻게 움직이면 좋은지 한 번에 보이게 정리합니다.</div>', unsafe_allow_html=True)
    timeline = plan.get("timeline", [])
    if not timeline:
        st.info("일정 타임라인이 아직 비어 있어요.")
        return

    st.markdown('<div class="timeline-wrap">', unsafe_allow_html=True)
    for item in timeline:
        st.markdown(
            f"""
            <div class="timeline-card">
              <div class="timeline-badge">{_escape(item.get('time', '시간대'))}</div>
              <div class="timeline-row">
                <div>
                  <div class="timeline-time">{_escape(item.get('title', '활동'))}</div>
                  <div style="color: var(--muted); margin-top: 0.25rem;">{_escape(item.get('location', ''))}</div>
                </div>
                <div>
                  <div class="timeline-detail">{_escape(item.get('detail', ''))}</div>
                  <div style="margin-top: 0.35rem; color: var(--muted); font-size: 0.9rem;">{_escape(item.get('duration', ''))}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)


def _render_links_and_notes(plan: Dict[str, Any]) -> None:
    st.markdown('<div class="section-title">링크 / 메모</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-subtitle">예약 가능한 링크와 함께 참고 메모를 모았습니다.</div>', unsafe_allow_html=True)

    route_summary = plan.get("route_summary")
    fallback_option = plan.get("fallback_option")
    notes = plan.get("notes", [])
    booking_links = plan.get("booking_links", [])

    st.markdown(
        f"""
        <div class="link-card">
          <div class="link-badge">이동 요약</div>
          <p>{_escape(route_summary or '아직 경로 요약이 비어 있어요.')}</p>
          <p style="margin-top:0.7rem; color: var(--muted);"><strong>대체 플랜:</strong> {_escape(fallback_option or '대체 플랜이 없으면 검색 범위를 넓혀 다시 제안합니다.')}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if booking_links:
        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='link-card'><div class='link-badge'>링크 패널</div></div>",
            unsafe_allow_html=True,
        )
        for link in booking_links:
            st.markdown(
                f"""
                <div class="link-card" style="margin-top:0.6rem;">
                  <p><strong>{_escape(link.get('type', '링크'))}</strong> · <a href="{_escape(link.get('url'))}" target="_blank" rel="noopener noreferrer">{_escape(link.get('label'))}</a></p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    if notes:
        st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='memory-card'><div class='card-title'>참고 메모</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<ul style='margin: 0.7rem 0 0 1.1rem; color: var(--text);'>"
            + "".join(f"<li>{_escape(note)}</li>" for note in notes)
            + "</ul>",
            unsafe_allow_html=True,
        )


def _render_debug_panel(final_state: Dict[str, Any], plan: Dict[str, Any]) -> None:
    with st.expander("원본 결과 보기", expanded=False):
        st.caption("그래프에서 받은 상태와 정리된 final_plan을 함께 확인할 수 있습니다.")
        st.json(final_state)
        st.json(plan)


def _run_workflow(
    user_query: str,
    region: str,
    companion: str,
    weather: str,
    time_slot: str,
    budget_level: str,
    mobility: str,
    enable_rag: bool,
    continue_mode: bool,
) -> Optional[Dict[str, Any]]:
    effective_query = _normalize_text(user_query)
    if not effective_query:
        effective_query = _compose_fallback_query(region, companion, weather, time_slot, budget_level, mobility)

    previous_state = st.session_state.today_what_plan_state
    if continue_mode and previous_state:
        thread_id = _normalize_text(st.session_state.today_what_thread_id_input, "") or st.session_state.today_what_thread_id or str(uuid.uuid4())
        initial_state = build_continued_state(
            previous_state=previous_state,
            user_query=effective_query,
            region=region,
            companion=companion,
            weather=weather,
            time_slot=time_slot,
            budget_level=budget_level,
            mobility=mobility,
            enable_rag=enable_rag,
        )
        st.session_state.today_what_continued_last_run = True
    else:
        thread_id = _normalize_text(st.session_state.today_what_thread_id_input, "") or str(uuid.uuid4())
        initial_state = build_initial_state(
            user_query=effective_query,
            region=region,
            companion=companion,
            weather=weather,
            time_slot=time_slot,
            budget_level=budget_level,
            mobility=mobility,
            enable_rag=enable_rag,
        )
        st.session_state.today_what_continued_last_run = False

    st.session_state.today_what_thread_id = thread_id

    graph = get_or_create_workflow_graph(enable_rag=enable_rag)
    return graph.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})


def _reset_current_result() -> None:
    st.session_state.today_what_plan_state = None
    st.session_state.today_what_messages = []
    st.session_state.today_what_thread_id = None
    st.session_state.today_what_logs = []
    st.session_state.today_what_continued_last_run = False


def main() -> None:
    """메인 애플리케이션."""
    st.set_page_config(
        page_title="오늘 뭐해?",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    initialize_state()
    _render_style()
    _render_sidebar()
    _render_hero()
    _render_input_area()

    submitted = _render_submit_area()
    if submitted:
        st.session_state.today_what_logs = []
        handler = StreamlitLogHandler()
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            with st.spinner("오늘의 상황을 읽고 추천을 정리하는 중..."):
                final_state = _run_workflow(
                    user_query=st.session_state.today_what_query,
                    region=st.session_state.today_what_region,
                    companion=st.session_state.today_what_companion,
                    weather=st.session_state.today_what_weather,
                    time_slot=st.session_state.today_what_time_slot,
                    budget_level=st.session_state.today_what_budget_level,
                    mobility=st.session_state.today_what_mobility,
                    enable_rag=st.session_state.today_what_enable_rag,
                    continue_mode=st.session_state.today_what_continue_mode,
                )
            if final_state:
                st.session_state.today_what_plan_state = final_state
                st.session_state.today_what_messages = list(final_state.get("messages", []))
                st.success("추천 결과를 정리했어요.")
        except Exception as exc:  # pragma: no cover - UI runtime safety
            LOGGER.exception("오늘 뭐해? workflow execution failed")
            st.error(f"추천 생성 중 오류가 발생했습니다: {exc}")
        finally:
            root_logger.removeHandler(handler)

    if st.session_state.today_what_plan_state:
        final_state = st.session_state.today_what_plan_state
        plan = _normalize_plan(final_state)

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        _render_status_strip(final_state, st.session_state.today_what_continued_last_run)
        st.markdown("<div style='height: 0.8rem;'></div>", unsafe_allow_html=True)

        top_cols = st.columns([1.35, 0.75], gap="large")
        with top_cols[0]:
            _render_summary_card(plan)
        with top_cols[1]:
            st.markdown(
                f"""
                <div class="memory-card">
                  <div class="card-title">실행 정보</div>
                  <p><strong>thread_id</strong></p>
                  <p style="color: var(--muted); word-break: break-all;">{_escape(st.session_state.today_what_thread_id or '미생성')}</p>
                  <p style="margin-top:0.7rem;"><strong>검색 모드</strong></p>
                  <p style="color: var(--muted);">{'DuckDuckGo 검색 사용' if st.session_state.today_what_enable_rag else '검색 없이 실행'}</p>
                  <p style="margin-top:0.7rem;"><strong>메시지 수</strong></p>
                  <p style="color: var(--muted);">{len(final_state.get('messages', []))}개</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
        content_cols = st.columns([1.2, 0.8], gap="large")
        with content_cols[0]:
            _render_recommendations(plan)
            st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
            _render_timeline(plan)
        with content_cols[1]:
            _render_links_and_notes(plan)
            st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div class="memory-card">
                  <div class="card-title">원하는 다음 단계</div>
                  <p style="color: var(--muted);">{_escape(plan.get('follow_up_prompt'))}</p>
                  <div style="margin-top:0.8rem; display:flex; gap:0.45rem; flex-wrap:wrap;">
                    <span class="meta-pill">지역 변경</span>
                    <span class="meta-pill">분위기 변경</span>
                    <span class="meta-pill">이어하기</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        _render_debug_panel(final_state, plan)

        st.markdown("<div style='height: 1.1rem;'></div>", unsafe_allow_html=True)
        action_cols = st.columns([0.35, 0.65])
        with action_cols[1]:
            if st.button("새 추천 시작", use_container_width=True):
                _reset_current_result()
                st.rerun()
    else:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">아직 결과가 없어요</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="section-subtitle">프롬프트와 상황 선택을 입력한 뒤 추천받기 버튼을 눌러보세요.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <ul style="margin: 0 0 0 1.1rem; color: var(--text);">
              <li>비 오는 날 데이트</li>
              <li>혼자 조용한 카페와 전시</li>
              <li>친구랑 가볍게 보낼 저녁 코스</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

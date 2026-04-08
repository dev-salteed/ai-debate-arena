"""오늘 뭐먹지 - 음식점/카페 추천 서비스."""

from __future__ import annotations

from copy import deepcopy
from html import escape
import logging
import uuid
from typing import Any, Dict, List, Optional

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - keeps unit tests importable without Streamlit
    class _SessionState(dict):
        def __getattr__(self, name: str) -> Any:
            return self.get(name)

        def __setattr__(self, name: str, value: Any) -> None:
            self[name] = value

    class _NoopContext:
        def __enter__(self) -> "_NoopContext":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def __getattr__(self, name: str):
            def _noop(*args, **kwargs):
                return None

            return _noop

    class _NoopStreamlit:
        def __init__(self) -> None:
            self.session_state = _SessionState()
            self.sidebar = _NoopContext()

        def set_page_config(self, *args, **kwargs) -> None:
            return None

        def markdown(self, *args, **kwargs) -> None:
            return None

        def columns(self, count):
            if isinstance(count, int):
                return [_NoopContext() for _ in range(count)]
            return [_NoopContext() for _ in range(len(count))]

        def form(self, *args, **kwargs):
            return _NoopContext()

        def text_area(self, *args, **kwargs):
            key = kwargs.get("key")
            if key is not None:
                return self.session_state.get(key, "")
            return ""

        def checkbox(self, *args, **kwargs):
            return kwargs.get("value", False)

        def form_submit_button(self, *args, **kwargs):
            return False

        def button(self, *args, **kwargs):
            return False

        def chat_message(self, *args, **kwargs):
            return _NoopContext()

        def expander(self, *args, **kwargs):
            return _NoopContext()

        def spinner(self, *args, **kwargs):
            return _NoopContext()

        def caption(self, *args, **kwargs) -> None:
            return None

        def info(self, *args, **kwargs) -> None:
            return None

        def warning(self, *args, **kwargs) -> None:
            return None

        def success(self, *args, **kwargs) -> None:
            return None

        def error(self, *args, **kwargs) -> None:
            return None

        def write(self, *args, **kwargs) -> None:
            return None

        def json(self, *args, **kwargs) -> None:
            return None

        def rerun(self) -> None:
            return None

    st = _NoopStreamlit()

from workflow.graph import create_dining_graph

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

APP_NAME = "오늘 뭐먹지"
APP_SUBTITLE = "자연어 한 줄로 오늘의 식당과 카페를 골라드립니다."


def _blank_recommendations() -> Dict[str, Any]:
    return {"summary": "", "recommendations": [], "follow_up_questions": []}


def _blank_state() -> Dict[str, Any]:
    return {
        "user_query": "",
        "parsed_query": {},
        "search_brief": {},
        "candidate_places": [],
        "recommendations": _blank_recommendations(),
        "search_iterations": 0,
        "max_search_iterations": 2,
        "decision_memory": [],
        "constraints_memory": {},
        "current_step": "",
        "messages": [],
        "completed": False,
        "thread_id": None,
        "continued_last_run": False,
    }


def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for message in messages:
        if isinstance(message, dict):
            normalized.append(dict(message))
        else:
            normalized.append({"role": "assistant", "content": str(message)})
    return normalized


def _normalize_recommendations(recommendations: Any) -> Dict[str, Any]:
    if not isinstance(recommendations, dict):
        return _blank_recommendations()
    normalized = _blank_recommendations()
    normalized.update(recommendations)
    normalized["recommendations"] = (
        list(recommendations.get("recommendations", []))
        if isinstance(recommendations.get("recommendations"), list)
        else []
    )
    normalized["follow_up_questions"] = (
        list(recommendations.get("follow_up_questions", []))
        if isinstance(recommendations.get("follow_up_questions"), list)
        else []
    )
    normalized["summary"] = str(recommendations.get("summary", ""))
    return normalized


def _normalize_state(value: Dict[str, Any]) -> Dict[str, Any]:
    state = _blank_state()
    state.update(value or {})
    state["messages"] = _normalize_messages(state.get("messages"))
    state["recommendations"] = _normalize_recommendations(state.get("recommendations"))
    state["candidate_places"] = (
        list(state.get("candidate_places"))
        if isinstance(state.get("candidate_places"), list)
        else []
    )
    state["parsed_query"] = (
        dict(state.get("parsed_query"))
        if isinstance(state.get("parsed_query"), dict)
        else {}
    )
    state["search_brief"] = (
        dict(state.get("search_brief"))
        if isinstance(state.get("search_brief"), dict)
        else {}
    )
    state["decision_memory"] = (
        list(state.get("decision_memory"))
        if isinstance(state.get("decision_memory"), list)
        else []
    )
    state["constraints_memory"] = (
        dict(state.get("constraints_memory"))
        if isinstance(state.get("constraints_memory"), dict)
        else {}
    )
    return state


def initialize_state() -> None:
    if "recommendation_state" not in st.session_state:
        st.session_state.recommendation_state = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "continued_last_run" not in st.session_state:
        st.session_state.continued_last_run = False
    if "workflow_graph" not in st.session_state:
        st.session_state.workflow_graph = None
    if "workflow_graph_rag" not in st.session_state:
        st.session_state.workflow_graph_rag = None
    if "user_query_draft" not in st.session_state:
        st.session_state.user_query_draft = ""


def build_initial_state(
    user_query: str,
    max_search_iterations: int = 2,
    thread_id: Optional[str] = None,
    continued_last_run: bool = False,
) -> Dict[str, Any]:
    state = _blank_state()
    state.update(
        {
            "user_query": user_query,
            "max_search_iterations": max_search_iterations,
            "thread_id": thread_id,
            "continued_last_run": continued_last_run,
        }
    )
    return _normalize_state(state)


def build_continued_state(
    previous_state: Dict[str, Any],
    user_query: str,
    max_search_iterations: Optional[int] = None,
    thread_id: Optional[str] = None,
    continued_last_run: bool = True,
) -> Dict[str, Any]:
    state = _normalize_state(deepcopy(previous_state))
    state.update(
        {
            "user_query": user_query,
            "search_brief": {},
            "candidate_places": [],
            "recommendations": _blank_recommendations(),
            "current_step": "",
            "completed": False,
            "search_iterations": 0,
            "thread_id": thread_id if thread_id is not None else state.get("thread_id"),
            "continued_last_run": continued_last_run,
        }
    )
    if max_search_iterations is not None:
        state["max_search_iterations"] = max_search_iterations
    return _normalize_state(state)


def get_or_create_workflow_graph(enable_rag: bool):
    if (
        st.session_state.workflow_graph is None
        or st.session_state.workflow_graph_rag != enable_rag
    ):
        st.session_state.workflow_graph = create_dining_graph(enable_rag=enable_rag)
        st.session_state.workflow_graph_rag = enable_rag
    return st.session_state.workflow_graph


def _seed_query(prompt: str) -> None:
    st.session_state.user_query_draft = prompt


def _render_badge(label: str) -> str:
    return f'<span class="meal-badge">{escape(label)}</span>'


def _render_card(title: str, body: str, footer: Optional[str] = None, accent: str = "gold") -> str:
    footer_html = f'<div class="card-footer">{escape(footer)}</div>' if footer else ""
    return f"""
    <div class="meal-card meal-card-{accent}">
        <div class="meal-card-title">{escape(title)}</div>
        <div class="meal-card-body">{body}</div>
        {footer_html}
    </div>
    """


def _apply_custom_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg-1: #fff8f1;
            --bg-2: #fff1df;
            --surface: rgba(255, 255, 255, 0.82);
            --text: #2f241f;
            --muted: #7f6656;
            --accent: #d97706;
            --border: rgba(122, 92, 70, 0.12);
            --shadow: 0 20px 60px rgba(116, 76, 45, 0.14);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(217, 119, 6, 0.12), transparent 28%),
                radial-gradient(circle at top right, rgba(245, 158, 11, 0.10), transparent 22%),
                linear-gradient(180deg, var(--bg-1) 0%, #fffdf8 40%, var(--bg-2) 100%);
            color: var(--text);
            font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", "Segoe UI", sans-serif;
        }

        .hero-shell {
            padding: 1.4rem 1.5rem 1.1rem;
            border: 1px solid var(--border);
            border-radius: 28px;
            background: linear-gradient(135deg, rgba(255,255,255,0.92), rgba(255,248,239,0.86));
            box-shadow: var(--shadow);
            margin-bottom: 1.2rem;
        }

        .hero-kicker {
            color: var(--accent);
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            font-size: 0.78rem;
            margin-bottom: 0.35rem;
        }

        .hero-title {
            font-size: 2.6rem;
            line-height: 1.08;
            font-weight: 800;
            margin: 0;
            color: var(--text);
        }

        .hero-subtitle {
            font-size: 1.02rem;
            color: var(--muted);
            margin-top: 0.55rem;
        }

        .meal-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.33rem 0.7rem;
            border-radius: 999px;
            background: rgba(217, 119, 6, 0.11);
            color: #8a4b08;
            border: 1px solid rgba(217, 119, 6, 0.16);
            font-size: 0.82rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }

        .meal-card {
            border-radius: 22px;
            padding: 1rem 1rem 0.9rem;
            border: 1px solid var(--border);
            background: var(--surface);
            box-shadow: 0 10px 28px rgba(104, 66, 35, 0.08);
            height: 100%;
        }

        .meal-card-gold {
            background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(255,247,233,0.94));
        }

        .meal-card-rose {
            background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(255,243,239,0.94));
        }

        .meal-card-title {
            font-size: 1.04rem;
            font-weight: 800;
            margin-bottom: 0.4rem;
            color: var(--text);
        }

        .meal-card-body {
            color: var(--muted);
            line-height: 1.6;
            font-size: 0.96rem;
        }

        .card-footer {
            margin-top: 0.7rem;
            padding-top: 0.65rem;
            border-top: 1px dashed rgba(122, 92, 70, 0.18);
            color: #8d6d58;
            font-size: 0.88rem;
        }

        .metric-chip {
            border-radius: 18px;
            padding: 0.9rem 0.95rem;
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(122, 92, 70, 0.10);
            box-shadow: 0 8px 24px rgba(104, 66, 35, 0.06);
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.82rem;
            margin-bottom: 0.2rem;
        }

        .metric-value {
            font-size: 1.4rem;
            font-weight: 800;
            color: var(--text);
        }

        .metric-note {
            margin-top: 0.2rem;
            color: var(--muted);
            font-size: 0.82rem;
        }

        div[data-testid="stForm"] {
            border: 1px solid rgba(122, 92, 70, 0.10);
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.70);
            padding: 1rem 1rem 0.6rem;
            box-shadow: 0 16px 36px rgba(104, 66, 35, 0.08);
        }

        .stTextArea textarea {
            background: #fffdf9;
            border-radius: 18px;
            border: 1px solid rgba(122, 92, 70, 0.14);
        }

        .stButton > button {
            border-radius: 14px;
            border: 1px solid rgba(217, 119, 6, 0.20);
            background: linear-gradient(180deg, #ffb23e, #d97706);
            color: white;
            font-weight: 800;
            box-shadow: 0 12px 26px rgba(217, 119, 6, 0.22);
        }

        .empty-state {
            border: 1px dashed rgba(217, 119, 6, 0.22);
            border-radius: 24px;
            background: rgba(255, 255, 255, 0.68);
            padding: 1.35rem;
            color: var(--muted);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="hero-kicker">Dining guide</div>
            <div class="hero-title">{escape(APP_NAME)}</div>
            <div class="hero-subtitle">{escape(APP_SUBTITLE)}</div>
            <div style="margin-top: 0.85rem;">
                {_render_badge("맛집")}
                {_render_badge("카페")}
                {_render_badge("멀티에이전트")}
                {_render_badge("RAG 검색")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_examples() -> None:
    st.markdown("### 예시 프롬프트")
    st.caption("버튼을 누르면 입력창이 채워집니다.")
    examples = [
        "성수에서 조용하고 분위기 좋은 브런치 카페 추천해줘",
        "홍대 근처 혼밥하기 좋은 가성비 한식 식당",
        "강남에서 데이트하기 좋은 와인바나 이탈리안",
        "을지로에서 대화하기 좋은 저녁 식당 추천해줘",
    ]
    columns = st.columns(2)
    for index, prompt in enumerate(examples):
        with columns[index % len(columns)]:
            st.button(
                prompt,
                key=f"example_{index}",
                on_click=_seed_query,
                args=(prompt,),
                use_container_width=True,
            )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 오늘 뭐먹지")
        st.markdown(
            """
            - 지역, 분위기, 가격대, 동행자를 같이 적어주세요.
            - 결과는 검색 근거와 함께 정리됩니다.
            - 이어서 재실행하면 앞선 조건 메모리가 이어집니다.
            """
        )
        st.markdown("---")
        for badge in ["카페", "브런치", "혼밥", "데이트", "회식", "가성비", "디저트"]:
            st.markdown(_render_badge(badge), unsafe_allow_html=True)
        st.markdown("---")
        current = st.session_state.get("recommendation_state")
        if current:
            st.write(f"Thread ID: `{current.get('thread_id') or '없음'}`")
            st.write(f"연속 실행: {'예' if current.get('continued_last_run') else '아니오'}")
        else:
            st.write("아직 추천 결과가 없습니다.")


def _render_metric_grid(state: Dict[str, Any]) -> None:
    parsed_query = state.get("parsed_query", {})
    search_brief = state.get("search_brief", {})
    recommendations = state.get("recommendations", {})
    metrics = [
        ("지역", parsed_query.get("region", "미정"), parsed_query.get("subregion", "세부 지역 미정")),
        ("업종", parsed_query.get("venue_type", "미정"), parsed_query.get("purpose", "상황 미정")),
        (
            "후보",
            str(len(state.get("candidate_places", []))),
            search_brief.get("freshness_note", "검색 노트 없음"),
        ),
        (
            "후속 질문",
            str(len(recommendations.get("follow_up_questions", []))),
            "연속 실행 가능",
        ),
    ]
    columns = st.columns(4)
    for index, column in enumerate(columns):
        label, value, note = metrics[index]
        with column:
            st.markdown(
                f"""
                <div class="metric-chip">
                    <div class="metric-label">{escape(label)}</div>
                    <div class="metric-value">{escape(value)}</div>
                    <div class="metric-note">{escape(note)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_search_section(state: Dict[str, Any]) -> None:
    search_brief = state.get("search_brief", {})
    parsed_query = state.get("parsed_query", {})
    col1, col2 = st.columns(2)

    with col1:
        badges = "".join(
            _render_badge(label)
            for label in [
                parsed_query.get("region", "지역 미정"),
                parsed_query.get("venue_type", "업종 미정"),
                parsed_query.get("purpose", "상황 미정"),
                parsed_query.get("price_range", "가격대 미정"),
            ]
            if label
        )
        atmosphere = "".join(_render_badge(item) for item in parsed_query.get("atmosphere", []))
        st.markdown(
            _render_card(
                "요청 해석",
                badges + atmosphere,
                footer=parsed_query.get("rationale", "파서 근거 없음"),
                accent="rose",
            ),
            unsafe_allow_html=True,
        )

    with col2:
        constraints = state.get("constraints_memory", {})
        constraints_body = (
            "".join(
                _render_badge(f"{key}: {value}")
                for key, value in constraints.items()
                if value
            )
            or "추가 제약 메모가 없습니다."
        )
        st.markdown(
            _render_card(
                "누적 조건",
                constraints_body,
                footer="이어서 재실행 시 메모리가 유지됩니다.",
            ),
            unsafe_allow_html=True,
        )

    queries_used = search_brief.get("queries_used", [])
    with st.expander("검색 브리프와 사용한 질의 보기", expanded=False):
        st.write(search_brief.get("search_strategy", "검색 전략 정보가 없습니다."))
        if queries_used:
            st.markdown("".join(_render_badge(query) for query in queries_used), unsafe_allow_html=True)
        highlights = search_brief.get("source_highlights", [])
        for item in highlights:
            st.markdown(
                f"- `{item.get('place', '미상')}`: {item.get('evidence', '')} ({item.get('source', '')})"
            )


def _render_candidate_places(state: Dict[str, Any]) -> None:
    st.markdown("### 후보 장소")
    candidate_places = state.get("candidate_places", [])
    if not candidate_places:
        st.markdown(
            """
            <div class="empty-state">
                아직 후보 장소가 없습니다. 더 구체적인 지역이나 상황을 입력하면 후보를 채워드립니다.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    columns = st.columns(min(3, len(candidate_places)))
    for index, place in enumerate(candidate_places):
        features = ", ".join(place.get("features", [])) or "특징 정보 없음"
        tags = "".join(_render_badge(tag) for tag in place.get("vibe_tags", []))
        body = (
            f"{_render_badge(place.get('category', '추천'))}"
            f"{_render_badge(place.get('area', '지역 미상'))}"
            f"{tags}"
            f"<div style='margin-top:0.55rem;'>{escape(features)}</div>"
            f"<div style='margin-top:0.45rem;'>{escape(place.get('caution', '') or '주의사항 없음')}</div>"
        )
        with columns[index % len(columns)]:
            st.markdown(
                _render_card(
                    title=f"#{index + 1} {place.get('name', '후보 장소')}",
                    body=body,
                    footer=place.get("source_note", "검색 근거 없음"),
                ),
                unsafe_allow_html=True,
            )


def _render_recommendations(state: Dict[str, Any]) -> None:
    st.markdown("### 최종 추천")
    recommendations = state.get("recommendations", {})
    st.markdown(
        _render_card(
            "오늘의 한 줄 정리",
            escape(recommendations.get("summary", "")) or "결과를 생성하면 여기에 요약이 표시됩니다.",
            footer=state.get("search_brief", {}).get("freshness_note", "최신성 메모 없음"),
        ),
        unsafe_allow_html=True,
    )

    for index, recommendation in enumerate(recommendations.get("recommendations", []), start=1):
        features = "".join(_render_badge(item) for item in recommendation.get("features", []))
        body = (
            f"{_render_badge(recommendation.get('category', '추천'))}"
            f"{_render_badge(recommendation.get('location', '위치 미상'))}"
            f"{features}"
            f"<div style='margin-top:0.55rem;'>{escape(recommendation.get('why_recommended', ''))}</div>"
            f"<div style='margin-top:0.45rem;'>팁: {escape(recommendation.get('tips', '') or '없음')}</div>"
        )
        st.markdown(
            _render_card(
                title=f"추천 {index}: {recommendation.get('name', '추천 장소')}",
                body=body,
                footer=f"{recommendation.get('best_for', '')} | {recommendation.get('source_note', '')}",
                accent="rose" if index % 2 == 0 else "gold",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("### 이어질 질문")
    follow_ups = recommendations.get("follow_up_questions", [])
    if follow_ups:
        for item in follow_ups:
            st.markdown(f"- {escape(str(item))}", unsafe_allow_html=True)
    else:
        st.caption("후속 질문이 없을 정도로 조건이 충분합니다.")


def _render_messages_and_memory(state: Dict[str, Any]) -> None:
    st.markdown("### 에이전트 로그")
    messages = state.get("messages", [])
    if messages:
        for message in messages:
            role = message.get("role", "assistant")
            display_role = "assistant" if role != "user" else "user"
            with st.chat_message(display_role):
                st.markdown(f"**{escape(str(role))}**")
                st.markdown(str(message.get("content", "")))
    else:
        st.caption("아직 로그가 없습니다.")

    st.markdown("### 메모리")
    columns = st.columns(2)
    with columns[0]:
        st.json(state.get("decision_memory", []))
    with columns[1]:
        st.json(state.get("constraints_memory", {}))


def main() -> None:
    st.set_page_config(
        page_title=f"{APP_NAME} - 음식점/카페 추천",
        page_icon="🍽️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    initialize_state()
    _apply_custom_styles()
    _render_sidebar()
    _render_hero()
    _render_examples()

    previous_state = st.session_state.get("recommendation_state")
    continue_enabled = bool(previous_state)

    with st.form("food_recommendation_form", clear_on_submit=False):
        st.markdown("### 자연어 입력")
        user_query = st.text_area(
            "오늘 어떤 분위기, 메뉴, 지역을 찾고 있나요?",
            key="user_query_draft",
            placeholder="예: 성수에서 조용하고 분위기 좋은 브런치 카페, 예산은 2만원 안팎",
            height=140,
        )
        enable_rag = st.checkbox(
            "RAG 검색 사용",
            value=True,
            help="DuckDuckGo 검색과 로컬 지식을 함께 사용합니다.",
        )
        continue_mode = st.checkbox(
            "이어서 재실행",
            value=False,
            disabled=not continue_enabled,
            help="이전 thread와 메모리를 유지한 채 조건만 더 좁혀서 다시 실행합니다.",
        )
        submitted = st.form_submit_button("추천 시작", use_container_width=True)

    if submitted:
        cleaned_query = user_query.strip()
        if not cleaned_query:
            st.warning("자연어 입력을 한 줄 이상 적어주세요.")
        else:
            thread_id = (
                previous_state.get("thread_id")
                if continue_mode and previous_state and previous_state.get("thread_id")
                else str(uuid.uuid4())
            )
            if continue_mode and previous_state:
                initial_state = build_continued_state(
                    previous_state=previous_state,
                    user_query=cleaned_query,
                    thread_id=thread_id,
                    continued_last_run=True,
                )
            else:
                initial_state = build_initial_state(
                    user_query=cleaned_query,
                    thread_id=thread_id,
                    continued_last_run=False,
                )

            with st.spinner("검색과 추천을 정리하고 있습니다..."):
                try:
                    graph = get_or_create_workflow_graph(enable_rag=enable_rag)
                    final_state = graph.invoke(
                        initial_state,
                        config={"configurable": {"thread_id": thread_id}},
                    )
                    normalized = _normalize_state(dict(final_state))
                    normalized["thread_id"] = thread_id
                    normalized["continued_last_run"] = bool(continue_mode and previous_state)

                    st.session_state.recommendation_state = normalized
                    st.session_state.messages = normalized.get("messages", [])
                    st.session_state.thread_id = thread_id
                    st.session_state.continued_last_run = normalized["continued_last_run"]
                    st.success("추천 결과를 정리했습니다.")
                except Exception as exc:
                    logging.exception("추천 생성 중 오류")
                    st.error(f"추천 생성 중 오류가 발생했습니다: {exc}")

    current_state = st.session_state.get("recommendation_state")
    st.markdown("---")
    if current_state:
        _render_metric_grid(current_state)
        _render_search_section(current_state)
        _render_candidate_places(current_state)
        _render_recommendations(current_state)
        _render_messages_and_memory(current_state)

        st.markdown("---")
        if st.button("새 추천 받기", use_container_width=True):
            st.session_state.recommendation_state = None
            st.session_state.messages = []
            st.session_state.thread_id = None
            st.session_state.continued_last_run = False
            st.session_state.user_query_draft = ""
            st.rerun()
    else:
        st.markdown(
            """
            <div class="empty-state">
                아직 추천을 시작하지 않았습니다. 예시 프롬프트를 누르거나,
                자연어 입력창에 오늘의 상황을 적어 바로 시작해보세요.
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()

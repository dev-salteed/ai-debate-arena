import streamlit as st
from utils.state_manager import reset_session_state
from database.repository import debate_repository


def render_history_ui():

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("이력 새로고침", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("전체 이력 삭제", type="primary", use_container_width=True):
            if debate_repository.delete_all():
                st.rerun()

    # 토론 이력 로드
    debate_history = debate_repository.fetch()

    if not debate_history:
        st.info("저장된 토론 이력이 없습니다.")
    else:
        render_history_list(debate_history)


def render_history_list(debate_history):
    for id, topic, date, rounds in debate_history:
        with st.container(border=True):

            # 토론 주제
            st.write(f"***{topic}***")

            col1, col2, col3 = st.columns([3, 1, 1])
            # 토론 정보
            with col1:
                st.caption(f"날짜: {date} | 라운드: {rounds}")

            # 보기 버튼
            with col2:
                if st.button("보기", key=f"view_{id}", use_container_width=True):
                    topic, messages, docs = debate_repository.fetch_by_id(id)
                    if topic and messages:
                        st.session_state.viewing_history = True
                        st.session_state.messages = messages
                        st.session_state.loaded_topic = topic
                        st.session_state.loaded_debate_id = id
                        st.session_state.docs = docs
                        st.session_state.app_mode = "results"
                        st.rerun()

            # 삭제 버튼
            with col3:
                if st.button("삭제", key=f"del_{id}", use_container_width=True):
                    if debate_repository.delete_by_id(id):
                        reset_session_state()
                        st.rerun()

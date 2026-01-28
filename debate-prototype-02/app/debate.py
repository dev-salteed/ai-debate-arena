import streamlit as st
from langchain.schema import HumanMessage, SystemMessage, AIMessage

from utils.config import get_llm


# AI 응답 생성 함수 (메시지 히스토리 포함)
def generate_response(prompt, system_prompt, message_history=None):
    messages = [SystemMessage(content=system_prompt)]

    # 메시지 히스토리가 있으면 추가
    if message_history:
        for message in message_history:
            if message["role"] == "assistant":
                messages.append(AIMessage(content=message["content"]))
            else:
                messages.append(
                    HumanMessage(content=f"{message['role']}: {message['content']}")
                )

    # 현재 프롬프트 추가
    messages.append(HumanMessage(content=prompt))

    # LLM 호출
    response = get_llm().invoke(messages)
    return response.content


# 토론 단계별 기능을 함수로 분리
def handle_pro_round(topic: str):
    with st.spinner("찬성 측 의견을 생성 중입니다..."):

        if st.session_state.round == 1:
            # 첫 번째 찬성 측 의견 생성
            pro_prompt = f"""
            당신은 '{topic}'에 대해 찬성 입장을 가진 토론자입니다.
            논리적이고 설득력 있는 찬성 측 주장을 제시해주세요.
            200자 내로 작성해주세요.
            """
            system_prompt = "당신은 논리적이고 설득력 있는 찬성 측 토론자입니다."
        else:
            # 이전 반대 측 의견에 대한 반박
            previous_argument = st.session_state.messages[-1]["content"]
            pro_prompt = f"""
            당신은 '{topic}'에 대해 찬성 입장을 가진 토론자입니다.
            반대 측의 다음 주장에 대해 반박하고, 찬성 입장을 더 강화해주세요:

            반대 측 주장: "{previous_argument}"

            200자 내로 작성해주세요.
            """
            system_prompt = "당신은 논리적이고 설득력 있는 찬성 측 토론자입니다. 반대 측 주장에 대해 적극적으로 반박하세요."

        pro_argument = generate_response(
            pro_prompt, system_prompt, st.session_state.messages
        )

        st.session_state.messages.append({"role": "찬성 측", "content": pro_argument})


def handle_con_round(topic: str):
    with st.spinner("반대 측 의견을 생성 중입니다..."):
        previous_argument = st.session_state.messages[-1]["content"]
        con_prompt = f"""
        당신은 '{topic}'에 대해 반대 입장을 가진 토론자입니다.
        찬성 측의 다음 주장에 대해 반박하고, 반대 입장을 제시해주세요:

        찬성 측 주장: "{previous_argument}"

        200자 내로 작성해주세요.
        """
        system_prompt = "당신은 논리적이고 설득력 있는 반대 측 토론자입니다. 찬성 측 주장에 대해 적극적으로 반드시 욕설을 사용하며 반박하세요."

        con_argument = generate_response(
            con_prompt, system_prompt, st.session_state.messages
        )

        st.session_state.messages.append({"role": "반대 측", "content": con_argument})


def handle_judge(topic: str):
    with st.spinner("심판이 토론을 평가 중입니다..."):
        judge_prompt = f"""
        다음은 '{topic}'에 대한 찬반 토론입니다. 각 측의 주장을 분석하고 평가해주세요.

        토론 내용:
        """
        for entry in st.session_state.messages:
            judge_prompt += f"\n\n{entry['role']}: {entry['content']}"

        judge_prompt += """
        
        위 토론을 분석하여 다음을 포함하는 심사 평가를 해주세요:
        1. 양측 주장의 핵심 요약
        2. 각 측이 사용한 주요 논리와 증거의 강점과 약점
        3. 전체 토론의 승자와 그 이유
        4. 양측 모두에게 개선점 제안
        """
        system_prompt = "당신은 공정하고 논리적인 토론 심판입니다. 양측의 주장을 면밀히 검토하고 객관적으로 평가해주세요."

        judge_argument = generate_response(judge_prompt, system_prompt, [])

        st.session_state.messages.append({"role": "심판", "content": judge_argument})

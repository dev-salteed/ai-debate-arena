from workflow.state import DebateState, AgentType
from workflow.node import increment_round, pro_agent, con_agent, judge_agent
from langgraph.graph import StateGraph, END


def create_debate_graph() -> StateGraph:
    # 그래프 생성
    workflow = StateGraph(DebateState)

    # 노드 추가
    workflow.add_node(AgentType.PRO, pro_agent)
    workflow.add_node(AgentType.CON, con_agent)
    workflow.add_node(AgentType.JUDGE, judge_agent)
    workflow.add_node("INCREMENT_ROUND", increment_round)

    workflow.add_edge(AgentType.PRO, AgentType.CON)
    workflow.add_edge(AgentType.CON, "INCREMENT_ROUND")
    workflow.add_edge(AgentType.JUDGE, END)

    workflow.add_conditional_edges(
        "INCREMENT_ROUND",
        lambda s: (
            AgentType.JUDGE if s["current_round"] > s["max_rounds"] else AgentType.PRO
        ),
        [AgentType.JUDGE, AgentType.PRO],
    )

    workflow.set_entry_point(AgentType.PRO)
    workflow.add_edge(AgentType.JUDGE, END)

    return workflow.compile()


if __name__ == "__main__":

    graph = create_debate_graph()

    graph_image = graph.get_graph().draw_mermaid_png()

    output_path = "debate_graph3.png"
    with open(output_path, "wb") as f:
        f.write(graph_image)

    import subprocess

    subprocess.run(["open", output_path])

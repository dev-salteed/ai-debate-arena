"""LangGraph workflow for the dining recommendation service."""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore

from workflow.agents.place_search_agent import PlaceSearchAgent
from workflow.agents.query_parser_agent import QueryParserAgent
from workflow.agents.rag_processor_agent import RagProcessorAgent
from workflow.agents.recommendation_agent import RecommendationAgent
from workflow.agents.supervisor_agent import SupervisorAgent
from workflow.state import AgentType, DiningState

_CHECKPOINTER = MemorySaver()
_STORE = InMemoryStore()
_GRAPH_CACHE = {}


def create_dining_graph(enable_rag: bool = True):
    """Create or return a cached dining recommendation graph."""
    cache_key = f"dining_graph_rag_{enable_rag}"
    if cache_key in _GRAPH_CACHE:
        return _GRAPH_CACHE[cache_key]

    workflow = StateGraph(DiningState)

    query_parser = QueryParserAgent()
    place_search = PlaceSearchAgent(enable_rag=enable_rag)
    rag_processor = RagProcessorAgent()
    recommendation = RecommendationAgent()
    supervisor = SupervisorAgent()

    workflow.add_node(AgentType.SUPERVISOR, supervisor.run)
    workflow.add_node(AgentType.QUERY_PARSER, query_parser.run)
    workflow.add_node(AgentType.PLACE_SEARCH, place_search.run)
    workflow.add_node(AgentType.RAG_PROCESSOR, rag_processor.run)
    workflow.add_node(AgentType.RECOMMENDATION, recommendation.run)

    workflow.add_edge(AgentType.QUERY_PARSER, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.PLACE_SEARCH, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.RAG_PROCESSOR, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.RECOMMENDATION, AgentType.SUPERVISOR)

    workflow.add_conditional_edges(
        AgentType.SUPERVISOR,
        supervisor.route_next,
        {
            AgentType.QUERY_PARSER: AgentType.QUERY_PARSER,
            AgentType.PLACE_SEARCH: AgentType.PLACE_SEARCH,
            AgentType.RAG_PROCESSOR: AgentType.RAG_PROCESSOR,
            AgentType.RECOMMENDATION: AgentType.RECOMMENDATION,
            "END": END,
        },
    )
    workflow.set_entry_point(AgentType.SUPERVISOR)

    compiled = workflow.compile(checkpointer=_CHECKPOINTER, store=_STORE)
    _GRAPH_CACHE[cache_key] = compiled
    return compiled


def get_graph_runtime_components():
    """Return runtime components for tests."""
    return _CHECKPOINTER, _STORE


if __name__ == "__main__":
    graph = create_dining_graph(enable_rag=True)
    try:
        graph_image = graph.get_graph().draw_mermaid_png()
        output_path = "dining_graph.png"
        with open(output_path, "wb") as file:
            file.write(graph_image)
        print(f"그래프 이미지 저장 완료: {output_path}")
    except Exception as exc:
        print(f"그래프 시각화 실패: {exc}")

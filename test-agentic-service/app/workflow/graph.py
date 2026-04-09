"""LangGraph workflow for the 오늘 뭐해? service."""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore

from workflow.agents.context_analyzer_agent import ContextAnalyzerAgent
from workflow.agents.curator_agent import CuratorAgent
from workflow.agents.planner_agent import PlannerAgent
from workflow.agents.response_composer_agent import ResponseComposerAgent
from workflow.agents.retriever_agent import RetrieverAgent
from workflow.agents.supervisor_agent import SupervisorAgent
from workflow.state import AgentType, TodayWhatState

_CHECKPOINTER = MemorySaver()
_STORE = InMemoryStore()
_GRAPH_CACHE = {}


def create_today_what_graph(enable_rag: bool = True):
    cache_key = f"today_what_graph_rag_{enable_rag}"
    if cache_key in _GRAPH_CACHE:
        return _GRAPH_CACHE[cache_key]

    workflow = StateGraph(TodayWhatState)
    supervisor = SupervisorAgent()
    context_analyzer = ContextAnalyzerAgent(enable_rag=enable_rag)
    retriever = RetrieverAgent(enable_rag=enable_rag)
    curator = CuratorAgent(enable_rag=enable_rag)
    planner = PlannerAgent(enable_rag=enable_rag)
    response_composer = ResponseComposerAgent(enable_rag=enable_rag)

    workflow.add_node(AgentType.SUPERVISOR, supervisor.run)
    workflow.add_node(AgentType.CONTEXT_ANALYZER, context_analyzer.run)
    workflow.add_node(AgentType.RETRIEVER, retriever.run)
    workflow.add_node(AgentType.CURATOR, curator.run)
    workflow.add_node(AgentType.PLANNER, planner.run)
    workflow.add_node(AgentType.RESPONSE_COMPOSER, response_composer.run)

    workflow.add_edge(AgentType.CONTEXT_ANALYZER, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.RETRIEVER, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.CURATOR, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.PLANNER, AgentType.SUPERVISOR)
    workflow.add_edge(AgentType.RESPONSE_COMPOSER, AgentType.SUPERVISOR)

    workflow.add_conditional_edges(
        AgentType.SUPERVISOR,
        supervisor.route_next,
        {
            AgentType.CONTEXT_ANALYZER: AgentType.CONTEXT_ANALYZER,
            AgentType.RETRIEVER: AgentType.RETRIEVER,
            AgentType.CURATOR: AgentType.CURATOR,
            AgentType.PLANNER: AgentType.PLANNER,
            AgentType.RESPONSE_COMPOSER: AgentType.RESPONSE_COMPOSER,
            "END": END,
        },
    )
    workflow.set_entry_point(AgentType.SUPERVISOR)

    compiled = workflow.compile(checkpointer=_CHECKPOINTER, store=_STORE)
    _GRAPH_CACHE[cache_key] = compiled
    return compiled


def get_graph_runtime_components():
    return _CHECKPOINTER, _STORE

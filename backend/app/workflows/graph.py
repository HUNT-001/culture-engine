from typing import Literal
from langgraph.graph import END, START, StateGraph
from app.providers.interfaces import QlooProvider, ComposerProvider
from app.workflows.nodes import WorkflowDependencies, build_nodes
from app.workflows.state import RecommendationState


def build_recommendation_graph(
    qloo: QlooProvider,
    composer: ComposerProvider,
    demo_mode: bool,
    max_calls: int = 5,
):
    deps = WorkflowDependencies(qloo=qloo, composer=composer, demo_mode=demo_mode, max_calls=max_calls)
    nodes = build_nodes(deps)
    graph = StateGraph(RecommendationState)
    for name, node in nodes.items():
        graph.add_node(name, node)

    graph.add_edge(START, "validate_request")
    graph.add_edge("validate_request", "resolve_entities")
    graph.add_edge("resolve_entities", "retrieve_insights")
    graph.add_edge("retrieve_insights", "normalize_candidates")
    graph.add_edge("normalize_candidates", "rank_options")
    graph.add_edge("rank_options", "validate_evidence")
    graph.add_edge("validate_evidence", "compose_response")
    graph.add_edge("compose_response", "validate_output")
    graph.add_edge("validate_output", END)
    return graph.compile()

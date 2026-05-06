from langgraph.graph import END, START, StateGraph

from agent.nodes import (
    plan_searches,
    save_to_db_node,
    scrape_urls_node,
    search_arxiv_node,
    search_web_node,
    synthesize_node,
)
from agent.state import ResearchState


def build_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("plan_searches", plan_searches)
    graph.add_node("search_arxiv", search_arxiv_node)
    graph.add_node("search_web", search_web_node)
    graph.add_node("scrape_urls", scrape_urls_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("save_to_db", save_to_db_node)

    graph.add_edge(START, "plan_searches")
    graph.add_edge("plan_searches", "search_arxiv")
    graph.add_edge("plan_searches", "search_web")
    graph.add_edge(["search_arxiv", "search_web"], "scrape_urls")
    graph.add_edge("scrape_urls", "synthesize")
    graph.add_edge("synthesize", "save_to_db")
    graph.add_edge("save_to_db", END)

    return graph.compile()


research_graph = build_graph()

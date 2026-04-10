"""HPC Cluster Operations Agent — main graph with ReAct loop."""

import time
from langgraph.graph import StateGraph, END
from hpc_agent.state import AgentState
from hpc_agent.nodes.router import router_node
from hpc_agent.nodes.context import context_node
from hpc_agent.nodes.analyzer import analyzer_node
from hpc_agent.nodes.react_executor import react_executor_node
from hpc_agent.nodes.memory import memory_node


def timed_node(name, fn):
    def wrapper(state):
        start = time.time()
        result = fn(state)
        elapsed = time.time() - start
        print(f"  [{name}] {elapsed:.1f}s")
        return result
    return wrapper


def should_use_skill(state: AgentState) -> str:
    if state.get("selected_skill", "none") == "none":
        return "no_skill"
    return "has_skill"


def should_continue_react(state: AgentState) -> str:
    """After Analyzer: loop back for more info, or finish."""
    if state.get("follow_up_needed") and state.get("next_command"):
        return "need_more"
    return "done"


def build_graph() -> StateGraph:
    """Construct the agent graph with ReAct loop."""
    graph = StateGraph(AgentState)

    # Nodes
    graph.add_node("router", timed_node("Router", router_node))
    graph.add_node("context", timed_node("Context", context_node))
    graph.add_node("analyzer", timed_node("Analyzer", analyzer_node))
    graph.add_node("react_executor", timed_node("ReAct", react_executor_node))
    graph.add_node("memory", timed_node("Memory", memory_node))

    # Flow
    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        should_use_skill,
        {
            "has_skill": "context",
            "no_skill": END,
        },
    )

    graph.add_edge("context", "analyzer")

    # ReAct loop: analyzer decides whether to continue or finish
    graph.add_conditional_edges(
        "analyzer",
        should_continue_react,
        {
            "need_more": "react_executor",  # loop: go execute the requested command
            "done": "memory",               # finish: save and respond
        },
    )

    # After executing, go back to analyzer to re-evaluate
    graph.add_edge("react_executor", "analyzer")

    graph.add_edge("memory", END)

    return graph


def create_agent():
    """Build and compile the agent."""
    graph = build_graph()
    return graph.compile()

from langgraph.graph import StateGraph
from typing import TypedDict, Any

class AgentState(TypedDict, total=False):
    task: str
    phase: str
    memory: dict[str, Any]
    reflection: list[str]

class GraphOrchestrator:
    def build_workflow(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("reflection", lambda x: {"reflection": ["analyzed"]})
        workflow.add_node("self_correct", lambda x: x)
        workflow.set_entry_point("reflection")
        workflow.add_edge("reflection", "self_correct")
        return workflow.compile()
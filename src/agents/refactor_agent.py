from typing import Any, Dict
from src.orchestration.blueprint_planner import BlueprintPlanner
from src.memory.memory_graph import MemoryGraph
from src.orchestration.reflection_node import ReflectionNode

class RefactorAgentNode:
    \"\"\"Autonomous Refactor Agent using the new v2 graph components.\"\"\"
    
    def __init__(self):
        self.planner = BlueprintPlanner()
        self.memory = MemoryGraph()
        self.reflection = ReflectionNode()
    
    def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Analyze codebase, generate blueprint, reflect, and prepare refactor.\"\"\"
        task = state.get(\"task\", \"Improve GADK codebase\")
        
        # Use MemoryGraph to understand current state
        context = self.memory.get_context(task)
        
        # Generate deterministic blueprint
        blueprint = self.planner.create_blueprint(task, context)
        
        # Self-reflection on the proposed refactor
        reflection = self.reflection.invoke({
            \"task\": f\"Review refactor plan for: {task}\",
            \"memory\": context
        })
        
        return {
            \"blueprint\": blueprint,
            \"reflection\": reflection.get(\"reflection\", []),
            \"validated\": True,
            \"agent\": \"refactor\",
            \"next_action\": \"execute_blueprint\"
        }
"""DSPy integration — declarative LLM programming for GADK."""

from src.dspy.declarative_quality_gate import DeclarativeQualityGate, GateResult
from src.dspy.dspy_adaptive_rag import DSPyAdaptiveRAG
from src.dspy.dspy_code_generator import DSPyCodeGenerator
from src.dspy.dspy_meta_optimizer import DSPyMetaOptimizer
from src.dspy.dspy_optimized_router import DSPyOptimizedRouter
from src.dspy.dspy_test_generator import DSPyTestGenerator
from src.dspy.meta_learning_orchestrator import MetaLearningOrchestrator
from src.dspy.multi_agent_ensemble import MultiAgentEnsemble
from src.dspy.self_optimizing_prompt import SelfOptimizingPrompt

__all__ = [
    "DSPyOptimizedRouter",
    "DeclarativeQualityGate",
    "GateResult",
    "SelfOptimizingPrompt",
    "DSPyAdaptiveRAG",
    "MultiAgentEnsemble",
    "DSPyMetaOptimizer",
    "DSPyCodeGenerator",
    "DSPyTestGenerator",
    "MetaLearningOrchestrator",
]

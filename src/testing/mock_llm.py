from collections.abc import AsyncGenerator

from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


class MockLiteLlm(LiteLlm):
    """Simulates LiteLlm/Elephant for testing."""

    def __init__(self, model: str = "mock", api_key: str = "mock", api_base: str = "mock"):
        super().__init__(model=model, api_key=api_key, api_base=api_base)
        self.model = model

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False, **kwargs
    ) -> AsyncGenerator[LlmResponse, None]:
        # Simple regex-based response simulator
        # Extract last user message
        user_text = ""
        for content in reversed(llm_request.contents):
            if content.role == "user":
                for part in content.parts:
                    if part.text:
                        user_text = part.text.lower()
                        break
                if user_text:
                    break

        # Scenario: Batch Search Request (triggered by 'quantum')
        if "quantum" in user_text:
            # Simulate a tool call to batch_execute with a search and a plan
            function_call = types.FunctionCall(
                name="batch_execute",
                args={
                    "requests": [
                        {"tool_name": "search_web", "args": {"query": "quantum qbit"}},
                        {
                            "tool_name": "create_structured_task",
                            "args": {
                                "title": "Quantum Error Correction",
                                "description": "Research and implement a basic surface code simulation.",
                                "acceptance_criteria": [
                                    "Read surface code papers",
                                    "Write python simulation",
                                    "Verify error rates",
                                ],
                                "priority": 3,
                                "complexity": "large",
                            },
                        },
                    ]
                },
            )
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="I'll search for quantum and plan a task.",
                            function_call=function_call,
                        )
                    ],
                )
            )
            return

        # Scenario: Parallel Delay Request (triggered by 'delay')
        if "delay" in user_text:
            function_call = types.FunctionCall(
                name="batch_execute",
                args={
                    "requests": [
                        {"tool_name": "delay_tool", "args": {"seconds": 1}},
                        {"tool_name": "delay_tool", "args": {"seconds": 1}},
                    ]
                },
            )
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="Running parallel delay tasks.", function_call=function_call
                        )
                    ],
                )
            )
            return

        # Scenario: Structured Task Creation (triggered by 'improve our tests')
        if "improve our tests" in user_text:
            function_call = types.FunctionCall(
                name="create_structured_task",
                args={
                    "title": "Implement Property-Based Testing",
                    "description": "Improve test robustness by adding Hypothesis for property-based testing across core modules.",
                    "acceptance_criteria": [
                        "Install hypothesis in requirements.txt",
                        "Add property-based tests for StateManager",
                        "Verify test coverage increases",
                    ],
                    "priority": 2,
                    "complexity": "medium",
                    "suggested_agent": "Builder",
                },
            )
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text="I've researched testing trends. Creating a structured task now.",
                            function_call=function_call,
                        )
                    ],
                )
            )
            return

        yield LlmResponse(
            content=types.Content(
                role="model", parts=[types.Part(text="Mock response from Elephant.")]
            )
        )

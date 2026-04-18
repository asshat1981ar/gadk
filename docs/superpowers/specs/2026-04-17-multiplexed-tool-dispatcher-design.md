# Design Specification: Multiplexed Tool Dispatcher (Elephant AI Optimization)

**Date:** 2026-04-17
**Status:** Drafting
**Framework:** Google Agent Development Kit (ADK) / Python
**Model:** OpenRouter Elephant

## 1. Goal
Maximize the high-throughput, parallel reasoning capabilities of the OpenRouter Elephant model within the Cognitive Foundry by implementing a **Multiplexed Tool Dispatcher**. This design shifts from sequential, single-item tool calls to batched, asynchronous execution in a single model turn.

## 2. Approach: The Multiplexed Dispatcher (Approach 1)
Instead of forcing the model to emit 5 separate `search_web("topic")` calls and waiting for 5 sequential round-trips, we provide a single `batch_execute` or `multiplex` tool. The model provides an array of tasks (complex objects), which the framework executes concurrently via `asyncio.gather`, returning a structured array of results.

### 2.1 Why this approach?
*   **Reduced Latency:** 1 network round-trip to the LLM instead of N.
*   **Context Efficiency:** Fewer intermediate "tool execution" turns cluttering the context window.
*   **Reliability Research:** This directly tests Elephant AI's ability to generate valid, complex JSON arrays (e.g., `[{"tool": "search", "query": "X"}, {"tool": "search", "query": "Y"}]`).

## 3. Architecture & Components

### 3.1 The `BatchTool` Wrapper
We will create a generic `batch_execute` tool in `src/tools/dispatcher.py`.
It will accept a list of "Tool Request" objects.

```python
# Conceptual Schema for the LLM
class ToolRequest(BaseModel):
    tool_name: str # e.g., 'search_web', 'execute_python_code'
    args: dict     # e.g., {"query": "Elephant AI tool calling"}

async def batch_execute(requests: List[ToolRequest]) -> List[dict]:
    # 1. Map tool_name to actual Python functions
    # 2. Execute all valid requests concurrently using asyncio.gather
    # 3. Return a list of results (or errors) matching the input index
```

### 3.2 Integration with Ideator (Throughput Focus)
The Ideator currently uses `search_web` to find one topic at a time. We will update its instructions to use `batch_execute` to scavenge 3-5 trends simultaneously, drastically increasing its proactive output.

### 3.3 Integration with Critic (Coordination Focus)
The Critic can use `batch_execute` to run multiple unit tests or sandboxed snippets in parallel, validating complex staging environments much faster.

## 4. Error Handling
If one task in the batch fails (e.g., a sandbox timeout), it should not crash the entire batch. The `batch_execute` function will catch exceptions per-task and return `{"status": "error", "message": "..."}` for that specific index, allowing the model to know exactly which sub-task failed and which succeeded.

## 5. Testing & Validation (The Research Phase)
To validate Elephant AI's capabilities, we will:
1.  Prompt the model to execute a batch of 5 distinct searches.
2.  Log the raw JSON arguments it produces to verify formatting correctness.
3.  Measure the execution time difference between sequential and batched calls.

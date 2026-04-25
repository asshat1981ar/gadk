# Ollama MiniMax Cloud Backend — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> **Model:** minimax-m2.7:cloud via Ollama Cloud API
> **Approach:** Drop-in backend using `ollama-python` client with OpenAI-compatible interface

**Goal:** Replace OpenRouter with Ollama Cloud MiniMax inference — ~free cloud GPU inference for GADK agents via `minimax-m2.7:cloud` model.

**Architecture:** `OllamaCloudBackend` wraps `ollama-python` Client (`host='https://ollama.com'`, `OLLAMA_API_KEY` auth). Provides OpenAI-compatible `chat()` / `chat_stream()` interface. ModelRouter handles dispatch via `ollama/minimax-m2.7:cloud` model prefix.

**Tech Stack:** `ollama` Python client, existing `LiteLlm` abstraction, `ModelRouter`.

---

## Task 1: Create OllamaCloudBackend skeleton + install ollama

### Step 1: Write failing test

```python
# tests/services/test_ollama_cloud_backend.py
from src.services.ollama_cloud_backend import OllamaCloudBackend

def test_backend_initialization():
    backend = OllamaCloudBackend()
    assert backend.model == "minimax-m2.7:cloud"
    assert backend.base_url == "https://ollama.com"
```

**Step 2: Run test**
```bash
pytest tests/services/test_ollama_cloud_backend.py::test_backend_initialization -v
```
Expected: FAIL — module not found

### Step 3: Install ollama

```bash
.venv/bin/pip install ollama
```

### Step 4: Implement

```python
# src/services/ollama_cloud_backend.py
"""Ollama Cloud backend — MiniMax inference via Ollama's cloud infrastructure.

Uses minimax-m2.7:cloud (and similar) models through Ollama's cloud API.
No local GPU needed — inference offloaded to Ollama's cloud.

API: https://github.com/ollama/ollama-python
Auth: OLLAMA_API_KEY environment variable
"""
from __future__ import annotations

import os
from typing import Any, Iterator

from src.config import Config
from src.observability.logger import get_logger

logger = get_logger(__name__)


class OllamaCloudBackend:
    """Chat completion backend using Ollama Cloud (MiniMax and other models).

    Supports :cloud models (e.g. minimax-m2.7:cloud) which auto-offload
    to Ollama's remote inference infrastructure. No local GPU required.
    """

    def __init__(
        self,
        model: str = "minimax-m2.7:cloud",
        base_url: str = "https://ollama.com",
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OLLAMA_API_KEY")
        self._client: Any = None

    @property
    def client(self) -> Any:
        if self._client is None:
            from ollama import Client

            self._client = Client(host=self.base_url)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call Ollama Cloud chat API. Returns OpenAI-compatible response dict."""
        opts: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        if self.api_key:
            # Client with Bearer auth for cloud API
            import ollama

            self._client = ollama.Client(
                host=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

        raw = self._client.chat(**opts)

        if stream:
            return raw  # Return generator as-is

        # Convert Ollama response to OpenAI-compatible format
        content = raw.get("message", {}).get("content", "")
        return {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": raw.get("prompt_eval_count", 0),
                "completion_tokens": raw.get("eval_count", 0),
                "total_tokens": raw.get("prompt_eval_count", 0)
                + raw.get("eval_count", 0),
            },
            "model": self.model,
        }

    def chat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """Yield content chunks for streaming responses."""
        if not self.api_key:
            self.api_key = os.environ.get("OLLAMA_API_KEY")
        if self.api_key:
            import ollama

            self._client = ollama.Client(
                host=self.base_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )

        stream = self._client.chat(model=self.model, messages=messages, stream=True)
        for chunk in stream:
            if chunk.get("message", {}).get("content"):
                yield chunk["message"]["content"]
```

**Step 5: Run test**
```bash
pytest tests/services/test_ollama_cloud_backend.py::test_backend_initialization -v
```
Expected: PASS

**Step 6: Commit**
```bash
git add tests/services/test_ollama_cloud_backend.py src/services/ollama_cloud_backend.py
git commit -m "feat(ollama): add OllamaCloudBackend with MiniMax cloud support (Task 1)"
```

---

## Task 2: Add Ollama config flags

### Step 1: Write failing test

```python
# tests/services/test_ollama_cloud_backend.py (add)
def test_config_defaults():
    from src.config import Config
    assert Config.OLLAMA_MODEL == "minimax-m2.7:cloud"
    assert Config.OLLAMA_BASE_URL == "https://ollama.com"
    assert Config.OLLAMA_API_KEY is None
```

### Step 2: Run test
```bash
pytest tests/services/test_ollama_cloud_backend.py::test_config_defaults -v
```
Expected: FAIL — Config.OLLAMA_* not defined

### Step 3: Implement

Add to `Settings` class in `src/config.py`:
```python
ollama_model: str = "minimax-m2.7:cloud"
ollama_base_url: str = "https://ollama.com"
ollama_api_key: str | None = None
```

Add to `Config` class in `src/config.py`:
```python
OLLAMA_MODEL: str = "minimax-m2.7:cloud"
OLLAMA_BASE_URL: str = "https://ollama.com"
OLLAMA_API_KEY: str | None = None
```

### Step 4: Run test
Expected: PASS

### Step 5: Commit
```bash
git commit -m "feat(ollama): add Ollama config flags (Task 2)"
```

---

## Task 3: Wire OllamaCloudBackend into ModelRouter

### Step 1: Write failing test

```python
# tests/services/test_ollama_cloud_backend.py (add)
def test_model_router_ollama_prefix():
    from src.services.model_router import ModelRouter
    router = ModelRouter()
    # When model starts with "ollama/", route to OllamaCloudBackend
    backend = router.get_backend("ollama/minimax-m2.7:cloud")
    assert backend is not None
    assert hasattr(backend, "chat")
```

### Step 2: Run test
```bash
pytest tests/services/test_ollama_cloud_backend.py::test_model_router_ollama_prefix -v
```
Expected: FAIL — ModelRouter has no get_backend method

### Step 3: Implement

Add `get_backend(model: str)` method to `ModelRouter`:
```python
def get_backend(self, model: str) -> Any:
    """Get a backend instance for a model string.

    Recognizes 'ollama/' prefix for Ollama Cloud models.
    Otherwise falls back to LiteLlm via OpenRouter.
    """
    if model.startswith("ollama/"):
        model_name = model.replace("ollama/", "")
        return OllamaCloudBackend(
            model=model_name,
            base_url=Config.OLLAMA_BASE_URL,
            api_key=Config.OLLAMA_API_KEY,
        )
    # Default: return None — caller should use LiteLlm via OpenRouter
    return None
```

### Step 4: Run test
Expected: PASS

### Step 5: Commit
```bash
git commit -m "feat(ollama): wire OllamaCloudBackend into ModelRouter (Task 3)"
```

---

## Task 4: Add streaming test + verify integration

### Step 1: Write failing test

```python
# tests/services/test_ollama_cloud_backend.py (add)
def test_chat_stream_returns_chunks():
    backend = OllamaCloudBackend()
    messages = [{"role": "user", "content": "Say 'test'"}]
    chunks = list(backend.chat_stream(messages))
    assert len(chunks) >= 1
    assert any("test" in str(c).lower() for c in chunks)
```

### Step 2: Run test
```bash
pytest tests/services/test_ollama_cloud_backend.py::test_chat_stream_returns_chunks -v
```
Expected: PASS (or SKIP if no OLLAMA_API_KEY)

### Step 3: Commit
```bash
git commit -m "test(ollama): add streaming test (Task 4)"
```

---

## Task 5: Full quality gate

```bash
ruff check src/services/ollama_cloud_backend.py --fix
ruff format --check src/services/ollama_cloud_backend.py
.venv/bin/python -m mypy src/services/ollama_cloud_backend.py
pytest tests/services/test_ollama_cloud_backend.py -v
```

Commit:
```bash
git commit -m "test(ollama): full lint + test suite (Task 5)"
```

---

## Strengths and Weaknesses

| Strengths | Weaknesses |
|-----------|------------|
| ~free inference via Ollama Cloud | Ollama Cloud is young — no guaranteed SLA |
| No local GPU needed | Requires `OLLAMA_API_KEY` + `ollama signin` |
| OpenAI-compatible `chat()` interface | Limited model selection (MiniMax, DeepSeek, GPT-oss, Qwen) |
| Same API for local + cloud models | Streaming requires re-auth on each call (current impl) |
| Drops into existing ModelRouter pattern | No native tool-calling support in ollama-python |
| MiniMax M2.7: 196K context, ~100 tps (highspeed variant) | Auth token management adds complexity |

---

## API Notes

- **Base URL:** `https://ollama.com` (cloud) or `http://localhost:11434` (local)
- **Auth:** `OLLAMA_API_KEY` env var, passed as `Bearer` token
- **Model name:** `minimax-m2.7:cloud` (use `:cloud` suffix to explicitly route to Ollama cloud)
- **Streaming:** `client.chat(model=..., messages=..., stream=True)` returns generator
- **No local Ollama daemon needed** for cloud API — just the Python client + API key

---

**Plan complete. Ready to execute using full TDD cycle task-by-task. Type "continue" to proceed.**

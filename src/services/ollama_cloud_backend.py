"""Ollama Cloud backend — MiniMax inference via Ollama's cloud infrastructure.

Uses minimax-m2.7:cloud (and similar) models through Ollama's cloud API.
No local GPU needed — inference offloaded to Ollama's cloud.

API: https://github.com/ollama/ollama-python
Auth: OLLAMA_API_KEY environment variable

Example:
    from src.services.ollama_cloud_backend import OllamaCloudBackend

    backend = OllamaCloudBackend(model="minimax-m2.7:cloud")
    response = backend.chat([{"role": "user", "content": "Hello"}])
    print(response["choices"][0]["message"]["content"])
"""
from __future__ import annotations

import os
from typing import Any, Iterator

from src.observability.logger import get_logger

logger = get_logger(__name__)


class OllamaCloudBackend:
    """Chat completion backend using Ollama Cloud (MiniMax and other models).

    Supports :cloud models (e.g. minimax-m2.7:cloud) which auto-offload
    to Ollama's remote inference infrastructure. No local GPU required.

    Usage:
        backend = OllamaCloudBackend()
        response = backend.chat([{"role": "user", "content": "Hi"}])

        # Streaming
        for chunk in backend.chat_stream([{"role": "user", "content": "Hi"}]):
            print(chunk, end="", flush=True)
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
        """Lazily create the Ollama client with optional Bearer auth."""
        if self._client is None:
            from ollama import Client

            kwargs: dict[str, Any] = {"host": self.base_url}
            if self.api_key:
                kwargs["headers"] = {"Authorization": f"Bearer {self.api_key}"}
            self._client = Client(**kwargs)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call Ollama Cloud chat API.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            stream: If True, returns the raw generator (call chat_stream instead).
            **kwargs: Passed through to ollama client.chat().

        Returns:
            OpenAI-compatible response dict with 'choices', 'usage', 'model'.
        """
        opts: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        opts.update(kwargs)

        raw = self.client.chat(**opts)  # type: ignore[no-any-return]

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

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> Iterator[str]:
        """Yield content text chunks from a streaming response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
            **kwargs: Passed through to ollama client.chat().

        Yields:
            Text content strings from each streaming chunk.
        """
        opts: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }
        opts.update(kwargs)

        stream = self.client.chat(**opts)
        for chunk in stream:
            msg_content = chunk.get("message", {}).get("content", "")
            if msg_content:
                yield msg_content

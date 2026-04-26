"""Tests for the Memori Cloud client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

from src.services.memori_client import MemoriCloudClient, _prune_none


class TestMemoriCloudClient:
    """Unit tests for MemoriCloudClient."""

    def test_attribution_chainable(self) -> None:
        client = MemoriCloudClient()
        result = client.attribution("gadk-builder", "project-chimera")
        assert result is client
        assert client._entity_id == "gadk-builder"
        assert client._process_id == "project-chimera"
        assert client.configured is True

    def test_new_session_generates_uuid(self) -> None:
        client = MemoriCloudClient()
        old = client._session_id
        client.new_session()
        assert client._session_id != old
        assert len(client._session_id) == 36  # UUID hex

    def test_unconfigured_persist_warns(self, caplog) -> None:
        client = MemoriCloudClient()
        result = client.persist([{"role": "user", "content": "hello"}])
        assert result == {}
        assert "without attribution" in caplog.text.lower()

    def test_unconfigured_recall_warns(self, caplog) -> None:
        client = MemoriCloudClient()
        result = client.recall("hello")
        assert result == []
        assert "without attribution" in caplog.text.lower()

    @patch("src.services.memori_client.requests.Session")
    def test_persist_success(self, mock_session_cls: MagicMock) -> None:
        """persist() hits /v1/sdk/augmentation with correct payload."""
        mock_session = mock_session_cls.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"conversation": {"summary": "ok"}}
        mock_session.post.return_value = mock_response

        client = MemoriCloudClient(api_key="sk_test")
        client.attribution("ent-1", "proc-1")
        data = client.persist(
            messages=[
                {"role": "user", "content": "Use TDD"},
                {"role": "assistant", "content": "Noted."},
            ]
        )

        assert data == {"conversation": {"summary": "ok"}}
        call_args = mock_session.post.call_args
        assert call_args is not None
        url = call_args.kwargs.get("url") or call_args[0][0]
        assert "/v1/sdk/augmentation" in url

        sent = call_args.kwargs.get("json") or call_args[1].get("json")
        assert sent["conversation"]["messages"][0]["role"] == "user"
        assert sent["meta"]["attribution"]["entity"]["id"] == "ent-1"

    @patch("src.services.memori_client.requests.Session")
    def test_persist_429_no_raise(self, mock_session_cls: MagicMock) -> None:
        """persist() swallows 429 rate-limit gracefully."""
        mock_session = mock_session_cls.return_value
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "429", response=mock_response
        )
        mock_session.post.return_value = mock_response

        client = MemoriCloudClient()
        client.attribution("ent-1")
        data = client.persist([{"role": "user", "content": "hi"}])
        assert data == {}

    @patch("src.services.memori_client.requests.Session")
    def test_persist_network_error(self, mock_session_cls: MagicMock) -> None:
        mock_session = mock_session_cls.return_value
        mock_session.post.side_effect = requests.exceptions.ConnectionError("DNS fail")

        client = MemoriCloudClient()
        client.attribution("ent-1")
        data = client.persist([{"role": "user", "content": "hi"}])
        assert data == {}

    @patch("memori.Memori")
    def test_recall_success(self, mock_memori_cls: MagicMock) -> None:
        """recall() delegates to Memori SDK for proper auth chain."""
        mock_m = mock_memori_cls.return_value
        mock_m.recall.return_value = {
            "facts": [{"content": "The user prefers TDD.", "rank_score": 0.95}]
        }

        client = MemoriCloudClient(api_key="sk_test")
        client.attribution("ent-1", "proc-1")
        facts = client.recall("coding style", limit=3)

        assert len(facts) == 1
        assert facts[0]["content"] == "The user prefers TDD."
        mock_m.attribution.assert_called_once_with("ent-1", "proc-1")
        mock_m.set_session.assert_called_once()
        mock_m.recall.assert_called_once_with("coding style", limit=3)

    @patch("memori.Memori")
    def test_recall_sdk_error(self, mock_memori_cls: MagicMock) -> None:
        mock_memori_cls.side_effect = RuntimeError("SDK init fail")

        client = MemoriCloudClient()
        client.attribution("ent-1")
        facts = client.recall("anything")
        assert facts == []

    def test_delete_without_entity(self) -> None:
        client = MemoriCloudClient()
        assert client.delete_entity_memories(None) is False


class TestPruneNone:
    def test_prunes_null(self) -> None:
        data = {"a": 1, "b": None, "c": {"d": None, "e": 2}}
        _prune_none(data)
        assert data == {"a": 1, "c": {"e": 2}}

    def test_prunes_nested(self) -> None:
        data = {"x": [{"a": None, "b": 2}, {"c": 3}]}
        _prune_none(data)
        assert data == {"x": [{"b": 2}, {"c": 3}]}

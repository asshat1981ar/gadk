from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import src.services.structured_output as structured_output
from src.services.agent_contracts import ReviewVerdict, TaskProposal


class TestStructuredOutputParsing:
    def test_parse_task_proposal_validates_expected_shape(self):
        payload = {
            "title": "Add typed review verdicts",
            "summary": "Return structured review decisions from Critic.",
            "description": "Return structured review decisions from Critic.",
            "acceptance_criteria": ["Critic returns pass/retry/block"],
            "recommended_agent": "Critic",
        }

        proposal = structured_output.parse_task_proposal(payload)

        assert isinstance(proposal, TaskProposal)
        assert proposal.recommended_agent == "Critic"

    def test_parse_task_proposal_accepts_json_text(self):
        payload = """```json
        {
          "title": "Add typed review verdicts",
          "summary": "Return structured review decisions from Critic.",
          "description": "Return structured review decisions from Critic.",
          "acceptance_criteria": ["Critic returns pass/retry/block"],
          "recommended_agent": "Critic"
        }
        ```"""

        proposal = structured_output.parse_task_proposal(payload)

        assert proposal.title == "Add typed review verdicts"

    def test_parse_task_proposal_rejects_missing_agent(self):
        payload = {
            "title": "Broken proposal",
            "summary": "Missing recommended agent",
            "description": "Missing recommended agent",
            "acceptance_criteria": [],
        }

        with pytest.raises(ValueError, match="recommended_agent"):
            structured_output.parse_task_proposal(payload)

    def test_parse_review_verdict_parses_json_text(self):
        payload = """{
          "status": "retry",
          "summary": "missing schema validation",
          "concerns": ["builder omitted required fields"],
          "retry_reason": "builder omitted required contract fields",
          "recommended_actions": ["add validation for specialist inputs"]
        }"""

        verdict = structured_output.parse_review_verdict(payload)

        assert isinstance(verdict, ReviewVerdict)
        assert verdict.status == "retry"
        assert verdict.recommended_actions == ["add validation for specialist inputs"]

    def test_parse_discovery_tasks_supports_legacy_task_blocks(self):
        payload = """
TASK 1:
Title: Add typed review verdicts
Priority: HIGH
Description: Return structured review decisions from Critic.
File hint: src/agents/critic.py
"""

        tasks = structured_output.parse_discovery_tasks(payload)

        assert len(tasks) == 1
        assert tasks[0].priority == "HIGH"
        assert tasks[0].file_hint == "src/agents/critic.py"


class TestStructuredOutputBridge:
    @pytest.mark.asyncio
    async def test_request_structured_output_uses_instructor_bridge(self, monkeypatch):
        expected = ReviewVerdict(status="pass", summary="looks good")

        class _FakeCompletions:
            async def create_with_completion(self, **kwargs):
                assert kwargs["response_model"] is ReviewVerdict
                return expected, object()

        fake_client = type(
            "FakeClient",
            (),
            {"chat": type("FakeChat", (), {"completions": _FakeCompletions()})()},
        )()

        monkeypatch.setattr(
            structured_output,
            "build_instructor_client",
            lambda completion, *, model: fake_client,
        )

        result = await structured_output.request_structured_output(
            messages=[{"role": "user", "content": "review this"}],
            response_model=ReviewVerdict,
            model="openrouter/elephant-alpha",
            api_key=None,
            api_base=None,
            timeout=30,
            max_retries=2,
        )

        assert result is expected

    @pytest.mark.asyncio
    async def test_request_structured_output_falls_back_to_local_validation(self, monkeypatch):
        monkeypatch.setattr(
            structured_output,
            "build_instructor_client",
            lambda completion, *, model: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        completion = AsyncMock(
            return_value=structured_output.mock_litellm_response(
                """{
                  "status": "retry",
                  "summary": "missing schema validation",
                  "concerns": ["builder omitted required fields"]
                }"""
            )
        )

        result = await structured_output.request_structured_output(
            messages=[{"role": "user", "content": "review this"}],
            response_model=ReviewVerdict,
            model="openrouter/elephant-alpha",
            api_key=None,
            api_base=None,
            timeout=30,
            max_retries=2,
            completion=completion,
        )

        assert result.status == "retry"
        completion.assert_awaited_once()

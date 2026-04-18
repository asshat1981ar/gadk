from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from tenacity import wait_none

import src.tools.smithery_bridge as smithery_bridge


@pytest.mark.asyncio
async def test_call_smithery_tool_error_handling():
    # Test error when smithery command is missing or fails
    with patch("asyncio.create_subprocess_exec") as mocked_exec:
        mocked_exec.side_effect = Exception("Command not found")
        result = await smithery_bridge.call_smithery_tool("nonexistent", "tool", {})
        assert "Bridge Error" in result

@pytest.mark.asyncio
async def test_call_smithery_tool_mock_success():
    # Mock a successful smithery call
    with patch("asyncio.create_subprocess_exec") as mocked_exec:
        mock_proc = MagicMock()
        # Use AsyncMock for communicate because it is awaited
        mock_proc.communicate = AsyncMock(return_value=(b'{"status": "success"}', b''))
        mock_proc.returncode = 0
        mocked_exec.return_value = mock_proc

        result = await smithery_bridge.call_smithery_tool("test-server", "test-tool", {"key": "val"})
        assert '{"status": "success"}' in result

@pytest.mark.asyncio
async def test_call_smithery_tool_mock_error():
    # Mock a failing smithery call (e.g. tool not found)
    with patch("asyncio.create_subprocess_exec") as mocked_exec:
        mock_proc = MagicMock()
        mock_proc.communicate = AsyncMock(return_value=(b'', b'Tool not found'))
        mock_proc.returncode = 1
        mocked_exec.return_value = mock_proc

        result = await smithery_bridge.call_smithery_tool("test-server", "wrong-tool", {})
        assert "Smithery Error" in result
        assert "Tool not found" in result


@pytest.mark.asyncio
async def test_call_smithery_tool_retries_retryable_cli_failure(monkeypatch):
    monkeypatch.setattr(smithery_bridge, "_SMITHERY_RETRY_WAIT", wait_none())

    failing_proc = MagicMock()
    failing_proc.communicate = AsyncMock(return_value=(b"", b"temporary failure"))
    failing_proc.returncode = 1

    success_proc = MagicMock()
    success_proc.communicate = AsyncMock(return_value=(b'{"status":"success"}', b""))
    success_proc.returncode = 0

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=[failing_proc, success_proc],
    ) as mocked_exec:
        result = await smithery_bridge.call_smithery_tool("test-server", "test-tool", {})

    assert result == '{"status":"success"}'
    assert mocked_exec.await_count == 2

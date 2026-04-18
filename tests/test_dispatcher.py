import pytest
from src.tools.dispatcher import batch_execute, register_tool

@pytest.mark.asyncio
async def test_batch_execute_success():
    # Test executing a simple echo mock
    requests = [
        {"tool_name": "mock_echo", "args": {"msg": "Hello"}},
        {"tool_name": "mock_echo", "args": {"msg": "World"}}
    ]
    
    def mock_echo(msg: str) -> str:
        return msg
    
    register_tool("mock_echo", mock_echo)
    
    results = await batch_execute(requests)
    assert len(results) == 2
    assert results[0]["status"] == "success"
    assert results[0]["output"] == "Hello"
    assert results[1]["status"] == "success"
    assert results[1]["output"] == "World"

@pytest.mark.asyncio
async def test_batch_execute_async_tool():
    # Test executing an async tool
    requests = [
        {"tool_name": "mock_async_echo", "args": {"msg": "Async Hello"}}
    ]
    
    async def mock_async_echo(msg: str) -> str:
        return msg
    
    register_tool("mock_async_echo", mock_async_echo)
    
    results = await batch_execute(requests)
    assert len(results) == 1
    assert results[0]["status"] == "success"
    assert results[0]["output"] == "Async Hello"

@pytest.mark.asyncio
async def test_batch_execute_tool_not_found():
    requests = [
        {"tool_name": "missing_tool", "args": {}}
    ]
    results = await batch_execute(requests)
    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "not found" in results[0]["message"]

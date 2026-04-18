
import pytest

from src.tools.sandbox_executor import execute_python_code


@pytest.mark.asyncio
async def test_execute_safe_code():
    code = "print('Hello Sandbox')"
    result = await execute_python_code(code)
    assert "Hello Sandbox" in result

@pytest.mark.asyncio
async def test_execute_timeout():
    code = "import time; time.sleep(5)"
    result = await execute_python_code(code, timeout=1)
    assert "Timeout" in result

@pytest.mark.asyncio
async def test_restricted_code():
    code = "import os; os.system('ls')"
    result = await execute_python_code(code)
    assert "Error" in result or "Dangerous" in result

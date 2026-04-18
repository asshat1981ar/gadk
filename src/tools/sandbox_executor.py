import asyncio
import tempfile
import os
import sys
from src.observability.metrics import tool_timer

@tool_timer("SandboxExecutor")
async def execute_python_code(code: str, timeout: int = 5) -> str:
    """
    Executes Python code in a restricted temporary environment.
    Args:
        code: The Python code to execute.
        timeout: Maximum execution time in seconds.
    """
    # Restrict dangerous imports trivially for prototype
    dangerous_keywords = ["os.system", "subprocess.", "shutil.", "pty.", "posix.", "builtins.eval", "builtins.exec"]
    if any(keyword in code for keyword in dangerous_keywords):
        return "Error: Dangerous operations detected."

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode()
            err_output = stderr.decode()
            if err_output:
                return f"Error: {err_output}"
            return output.strip()
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return "Error: Execution Timeout."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

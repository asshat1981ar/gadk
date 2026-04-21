import json
import os
import signal
import subprocess
import sys
import time

import pytest


def _matches_startup_line(line: str) -> bool:
    """Check if a log line indicates swarm startup.
    
    Handles both JSON formatted logs (default) and plain text logs.
    """
    if "Cognitive Foundry Swarm Active" in line:
        return True
    # Also check if it's in JSON format
    try:
        log_obj = json.loads(line)
        if "Cognitive Foundry Swarm Active" in log_obj.get("message", ""):
            return True
    except (json.JSONDecodeError, ValueError):
        pass
    return False


@pytest.fixture
def swarm_process():
    """Starts the swarm as a subprocess in production mode (no mocks) and handles cleanup."""
    env = os.environ.copy()
    env["TEST_MODE"] = "false"
    env["AUTONOMOUS_MODE"] = "true"
    env["LOG_LEVEL"] = "DEBUG"
    env["PYTHONUNBUFFERED"] = "1"

    # Start swarm as subprocess
    # We use a process group to ensure cleanup of any child processes
    proc = subprocess.Popen(
        [sys.executable, "-m", "src.main"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid,
        text=True,
    )

    # Wait for startup (look for "Cognitive Foundry Swarm Active")
    # The log message can be in JSON format (with "message" field) or plain text
    start_time = time.time()
    startup_detected = False
    while time.time() - start_time < 60:
        # Check if process is still running
        if proc.poll() is not None:
            break

        # We don't want to block forever on readline, but for tests this is simpler
        line = proc.stdout.readline()
        if _matches_startup_line(line):
            startup_detected = True
            break
        time.sleep(0.1)

    if not startup_detected:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        pytest.fail("Swarm failed to start in time.")

    yield proc

    # Graceful shutdown via sentinel
    from src.cli.swarm_ctl import request_shutdown

    request_shutdown()

    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print("[FIXTURE] Swarm did not shut down gracefully, killing...")
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


@pytest.mark.asyncio
async def test_swarm_parallel_tracking(swarm_process):
    """Verifies that the swarm can execute tools in parallel via batch_execute."""
    from src.cli.swarm_ctl import enqueue_prompt

    # 1. Enqueue the parallel delay prompt
    start_time = time.time()
    enqueue_prompt("Run 2 parallel delay tasks using batch_execute tool.", user_id="test_runner")

    found_delays = 0

    # We allow up to 60 seconds for the real LLM
    while time.time() - start_time < 60:
        line = swarm_process.stdout.readline()
        if not line:
            continue

        print(f"[TEST OUTPUT] {line.strip()}")

        if "Slept for 1s" in line:
            found_delays += 1

        if found_delays >= 2:
            break

        time.sleep(0.1)

    duration = time.time() - start_time

    # 3. Asserts
    assert found_delays == 2, f"Expected 2 delay completions, found {found_delays}"
    print(f"Total test duration: {duration:.2f}s")


@pytest.mark.asyncio
async def test_swarm_state_update_on_ideation(swarm_process):
    """Verifies that ideation prompts update the state.json."""
    import json

    from src.cli.swarm_ctl import enqueue_prompt

    state_file = "state.json"
    if os.path.exists(state_file):
        os.remove(state_file)

    enqueue_prompt(
        "Ideate a new feature for quantum computing and update state.", user_id="test_runner"
    )

    # Wait for ideation to complete and state to be written
    found_state = False
    start_time = time.time()
    while time.time() - start_time < 60:
        if os.path.exists(state_file):
            with open(state_file) as f:
                try:
                    data = json.load(f)
                    if any("quantum" in k.lower() for k in data.keys()):
                        found_state = True
                        break
                except json.JSONDecodeError:
                    pass
        time.sleep(0.5)

    assert found_state, "State file was not updated with quantum task"


def test_startup_line_matching():
    """Test that _matches_startup_line correctly detects startup messages in various formats."""
    # JSON format with message field (default logging format)
    json_log = '{"timestamp":"2024-01-20T10:00:00Z","level":"INFO","logger":"main","message":"Cognitive Foundry Swarm Active","session_id":"test-123"}'
    assert _matches_startup_line(json_log) is True
    
    # JSON format with the message in session field
    json_log2 = '{"timestamp":"2024-01-20T10:00:00Z","level":"INFO","logger":"main","message":"Cognitive Foundry Swarm Active (session=test-456)","session_id":"test-456"}'
    assert _matches_startup_line(json_log2) is True
    
    # Plain text format
    plain_log = "2024-01-20 10:00:00 [INFO] main | session=test-789 | Cognitive Foundry Swarm Active"
    assert _matches_startup_line(plain_log) is True
    
    # Non-matching logs
    non_startup_log = '{"timestamp":"2024-01-20T10:00:00Z","level":"INFO","message":"Some other message"}'
    assert _matches_startup_line(non_startup_log) is False
    
    # Invalid JSON that doesn't contain the message
    invalid_log = "This is not a startup message"
    assert _matches_startup_line(invalid_log) is False
    
    # Empty line
    assert _matches_startup_line("") is False

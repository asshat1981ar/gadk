import os
import tempfile

import pytest

from src.cli.swarm_ctl import (
    clear_pid,
    clear_shutdown,
    dequeue_prompts,
    enqueue_prompt,
    get_swarm_pid,
    is_shutdown_requested,
    peek_prompts,
    request_shutdown,
    write_pid,
)


class TestSwarmCtl:
    def setup_method(self):
        for f in [".swarm_shutdown", "prompt_queue.jsonl", "swarm.pid"]:
            if os.path.exists(f):
                os.remove(f)

    def teardown_method(self):
        for f in [".swarm_shutdown", "prompt_queue.jsonl", "swarm.pid"]:
            if os.path.exists(f):
                os.remove(f)

    def test_shutdown_sentinel(self):
        assert not is_shutdown_requested()
        request_shutdown()
        assert is_shutdown_requested()
        clear_shutdown()
        assert not is_shutdown_requested()

    def test_pid_file(self):
        write_pid()
        pid = get_swarm_pid()
        assert pid == os.getpid()
        clear_pid()
        assert get_swarm_pid() is None

    def test_prompt_queue(self):
        enqueue_prompt("Hello swarm", user_id="tester")
        enqueue_prompt("Do work", user_id="tester")

        # Peek should not clear
        peeked = peek_prompts()
        assert len(peeked) == 2
        assert peeked[0]["prompt"] == "Hello swarm"

        # Dequeue should clear
        dequeued = dequeue_prompts()
        assert len(dequeued) == 2
        assert not os.path.exists("prompt_queue.jsonl")

        # Empty dequeue
        assert dequeue_prompts() == []

    def test_peek_empty(self):
        assert peek_prompts() == []

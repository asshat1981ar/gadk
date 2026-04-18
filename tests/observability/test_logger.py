import json
import logging

from src.observability.logger import (
    configure_logging,
    get_logger,
    get_session_id,
    get_task_id,
    get_trace_id,
    set_session_id,
    set_task_id,
    set_trace_id,
)


class TestContextVars:
    def test_trace_id_default(self):
        tid = get_trace_id()
        assert isinstance(tid, str) and len(tid) > 0

    def test_set_and_get_trace_id(self):
        set_trace_id("abc-123")
        assert get_trace_id() == "abc-123"

    def test_set_and_get_session_id(self):
        set_session_id("session-42")
        assert get_session_id() == "session-42"

    def test_set_and_get_task_id(self):
        set_task_id("task-7")
        assert get_task_id() == "task-7"


class TestJsonFormatter:
    def test_json_output(self, capsys):
        configure_logging(level=logging.DEBUG, json_format=True)
        logger = get_logger("test_json")
        set_trace_id("t1")
        set_session_id("s1")
        set_task_id("tk1")
        logger.info("hello")
        captured = capsys.readouterr()
        log_line = captured.out.strip()
        record = json.loads(log_line)
        assert record["message"] == "hello"
        assert record["trace_id"] == "t1"
        assert record["session_id"] == "s1"
        assert record["task_id"] == "tk1"
        assert "timestamp" in record
        assert "level" in record

    def test_plain_output(self, capsys):
        configure_logging(level=logging.DEBUG, json_format=False)
        logger = get_logger("test_plain")
        set_trace_id("t2")
        logger.info("plain")
        captured = capsys.readouterr()
        assert "plain" in captured.out
        assert "t2" in captured.out

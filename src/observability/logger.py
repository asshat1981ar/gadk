import logging
import json
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

# Context-local trace and session IDs
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_session_id: ContextVar[str] = ContextVar("session_id", default="")
_task_id: ContextVar[str] = ContextVar("task_id", default="")


def get_trace_id() -> str:
    return _trace_id.get() or str(uuid.uuid4())


def get_session_id() -> str:
    return _session_id.get() or ""


def get_task_id() -> str:
    return _task_id.get() or ""


def set_trace_id(tid: str) -> None:
    _trace_id.set(tid)


def set_session_id(sid: str) -> None:
    _session_id.set(sid)


def set_task_id(tkid: str) -> None:
    _task_id.set(tkid)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        record.session_id = get_session_id()
        record.task_id = get_task_id()
        record.agent = getattr(record, "agent", "")
        record.tool = getattr(record, "tool", "")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ""),
            "session_id": getattr(record, "session_id", ""),
            "task_id": getattr(record, "task_id", ""),
            "agent": getattr(record, "agent", ""),
            "tool": getattr(record, "tool", ""),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO, json_format: bool = True) -> None:
    """Configure root logging for the swarm."""
    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s %(agent)s%(tool)s| trace=%(trace_id)s session=%(session_id)s task=%(task_id)s | %(message)s"
        )
    handler.setFormatter(formatter)
    handler.addFilter(_ContextFilter())

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)

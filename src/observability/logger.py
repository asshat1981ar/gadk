import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

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


#: Standard ``LogRecord`` attributes set by the logging framework itself plus
#: the ones our ``_ContextFilter`` populates. Anything else on the record was
#: caller-supplied via ``extra={...}`` and should be forwarded to structured
#: output — otherwise ``logger.info("...", extra={"cycle_id": ...})`` silently
#: drops the field.
_LOGRECORD_STANDARD_ATTRS = frozenset(
    {
        # stdlib LogRecord attrs (see logging.makeLogRecord + handler machinery)
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        "asctime",
        "taskName",
        # injected by _ContextFilter above
        "trace_id",
        "session_id",
        "task_id",
        "agent",
        "tool",
    }
)


def _extract_extra_fields(record: logging.LogRecord) -> dict[str, object]:
    """Return user-supplied ``extra={...}`` fields from a LogRecord.

    Nests them under a single ``extra`` key in the JSON output so the
    top-level schema (timestamp/level/message/trace_id/...) stays stable
    as call sites add new fields.
    """
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _LOGRECORD_STANDARD_ATTRS and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", ""),
            "session_id": getattr(record, "session_id", ""),
            "task_id": getattr(record, "task_id", ""),
            "agent": getattr(record, "agent", ""),
            "tool": getattr(record, "tool", ""),
        }
        extras = _extract_extra_fields(record)
        if extras:
            log_obj["extra"] = extras
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str)


class _PlainTextFormatterWithExtras(logging.Formatter):
    """Plain-text formatter that appends user-supplied ``extra={...}`` fields.

    The stock ``logging.Formatter`` format string can only reference attribute
    names it knows about at setup time, so ``extra`` fields silently drop out
    of plain-text output. We render them as trailing ``key=value`` pairs so
    grep-based log inspection sees the same values the JSON formatter carries.
    """

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _extract_extra_fields(record)
        if not extras:
            return base
        suffix = " ".join(f"{k}={v}" for k, v in sorted(extras.items()))
        return f"{base} | {suffix}"


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def configure_logging(level: int = logging.INFO, json_format: bool = True) -> None:
    """Configure root logging for the swarm."""
    handler = logging.StreamHandler(sys.stdout)
    if json_format:
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = _PlainTextFormatterWithExtras(
            "%(asctime)s [%(levelname)s] %(name)s %(agent)s%(tool)s| trace=%(trace_id)s session=%(session_id)s task=%(task_id)s | %(message)s"
        )
    handler.setFormatter(formatter)
    handler.addFilter(_ContextFilter())

    root = logging.getLogger()
    root.handlers = []
    root.addHandler(handler)
    root.setLevel(level)

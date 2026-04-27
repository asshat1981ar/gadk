"""Re-export the ADK's built-in SQLite session service for persistence."""

try:
    from google.adk.sessions.sqlite_session_service import (
        SqliteSessionService as SQLiteSessionService,
    )
except ImportError:
    SQLiteSessionService = None

__all__ = ["SQLiteSessionService"]

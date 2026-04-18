"""Re-export the ADK's built-in SQLite session service for persistence."""

from google.adk.sessions.sqlite_session_service import SqliteSessionService as SQLiteSessionService

__all__ = ["SQLiteSessionService"]

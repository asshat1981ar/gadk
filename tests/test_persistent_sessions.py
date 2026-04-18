import os

import pytest

from src.services.session_store import SQLiteSessionService

TEST_DB = "test_sessions.db"

class TestSQLiteSessionService:
    def setup_method(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        self.service = SQLiteSessionService(db_path=TEST_DB)

    def teardown_method(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @pytest.mark.asyncio
    async def test_create_and_get_session(self):
        session = await self.service.create_session(user_id="u1", app_name="TestApp")
        assert session.id
        assert session.user_id == "u1"

        restored = await self.service.get_session(
            app_name="TestApp", session_id=session.id, user_id="u1"
        )
        assert restored is not None
        assert restored.id == session.id
        assert restored.app_name == "TestApp"

    @pytest.mark.asyncio
    async def test_session_survives_restart(self):
        session = await self.service.create_session(user_id="u1", app_name="TestApp")
        sid = session.id

        # Simulate restart with new service instance
        service2 = SQLiteSessionService(db_path=TEST_DB)
        restored = await service2.get_session(
            app_name="TestApp", session_id=sid, user_id="u1"
        )
        assert restored is not None
        assert restored.id == sid

    @pytest.mark.asyncio
    async def test_list_sessions(self):
        await self.service.create_session(user_id="u1", app_name="App1")
        await self.service.create_session(user_id="u1", app_name="App2")
        # List all sessions for user u1 across all apps
        sessions_response = await self.service.list_sessions(app_name="App1", user_id="u1")
        assert len(sessions_response.sessions) == 1
        # List sessions for app_name only
        all_app1 = await self.service.list_sessions(app_name="App1")
        assert len(all_app1.sessions) == 1

    @pytest.mark.asyncio
    async def test_delete_session(self):
        session = await self.service.create_session(user_id="u1", app_name="TestApp")
        await self.service.delete_session(
            app_name="TestApp", session_id=session.id, user_id="u1"
        )
        restored = await self.service.get_session(
            app_name="TestApp", session_id=session.id, user_id="u1"
        )
        assert restored is None

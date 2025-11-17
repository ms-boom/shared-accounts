"""Integration tests for bot/db/repositories/chat_session_repository.py."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.chat_session_repository import ChatSessionRepository


@pytest.mark.integration
class TestChatSessionRepository:
    """Tests for ChatSessionRepository."""

    @pytest.fixture
    async def chat_session_repo(self, db_session: AsyncSession):
        """Create ChatSessionRepository instance for testing."""
        return ChatSessionRepository(db_session)

    async def test_create_session_with_default_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test creating a session with default thread_id (main chat)."""
        chat_id = 123456
        email = "test@example.com"
        session_path = "/data/sessions/123456"

        session = await chat_session_repo.create(
            chat_id=chat_id,
            email=email,
            session_path=session_path,
        )

        assert session is not None
        assert session["chat_id"] == chat_id
        assert session["thread_id"] == 0  # Default thread_id
        assert session["email"] == email
        assert session["session_path"] == session_path
        assert "created_at" in session

    async def test_create_session_with_topic_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test creating a session for a specific topic."""
        chat_id = 123456
        thread_id = 999
        email = "topic@example.com"
        session_path = "/data/sessions/123456/999"

        session = await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            email=email,
            session_path=session_path,
        )

        assert session is not None
        assert session["chat_id"] == chat_id
        assert session["thread_id"] == thread_id
        assert session["email"] == email
        assert session["session_path"] == session_path

    async def test_get_session_by_chat_and_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test retrieving session by chat_id and thread_id."""
        chat_id = 123456
        thread_id = 555

        # Create session
        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            email="test@example.com",
            session_path="/data/sessions/123456/555",
        )

        # Retrieve session
        session = await chat_session_repo.get_by_chat_id(chat_id, thread_id)

        assert session is not None
        assert session["chat_id"] == chat_id
        assert session["thread_id"] == thread_id

    async def test_get_nonexistent_session_returns_none(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test that getting nonexistent session returns None."""
        session = await chat_session_repo.get_by_chat_id(999999, 0)
        assert session is None

    async def test_sessions_isolated_by_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test that sessions with different thread_id are independent."""
        chat_id = 123456

        # Create session for main chat (thread_id=0)
        main_session = await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=0,
            email="main@example.com",
            session_path="/data/sessions/123456/main",
        )

        # Create session for topic 1
        topic1_session = await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=111,
            email="topic1@example.com",
            session_path="/data/sessions/123456/111",
        )

        # Create session for topic 2
        topic2_session = await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=222,
            email="topic2@example.com",
            session_path="/data/sessions/123456/222",
        )

        # Verify all sessions exist independently
        assert main_session["thread_id"] == 0
        assert topic1_session["thread_id"] == 111
        assert topic2_session["thread_id"] == 222

        # Verify we can retrieve each session independently
        retrieved_main = await chat_session_repo.get_by_chat_id(chat_id, 0)
        retrieved_topic1 = await chat_session_repo.get_by_chat_id(chat_id, 111)
        retrieved_topic2 = await chat_session_repo.get_by_chat_id(chat_id, 222)

        assert retrieved_main["email"] == "main@example.com"
        assert retrieved_topic1["email"] == "topic1@example.com"
        assert retrieved_topic2["email"] == "topic2@example.com"

    async def test_update_last_used_with_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test updating last_used timestamp for specific thread_id."""
        chat_id = 123456
        thread_id = 333

        # Create session
        original = await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            email="test@example.com",
            session_path="/data/sessions/123456/333",
        )

        assert original["last_used"] is None

        # Update last_used
        updated = await chat_session_repo.update_last_used(chat_id, thread_id)

        assert updated is not None
        assert updated["last_used"] is not None
        assert updated["chat_id"] == chat_id
        assert updated["thread_id"] == thread_id

    async def test_delete_session_with_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test deleting session by chat_id and thread_id."""
        chat_id = 123456
        thread_id = 444

        # Create session
        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            email="test@example.com",
            session_path="/data/sessions/123456/444",
        )

        # Verify session exists
        session = await chat_session_repo.get_by_chat_id(chat_id, thread_id)
        assert session is not None

        # Delete session
        result = await chat_session_repo.delete(chat_id, thread_id)
        assert result is True

        # Verify session is deleted
        session = await chat_session_repo.get_by_chat_id(chat_id, thread_id)
        assert session is None

    async def test_delete_only_affects_specific_thread(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test that deleting session only affects specific thread_id."""
        chat_id = 123456

        # Create sessions for different threads
        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=0,
            email="main@example.com",
            session_path="/data/sessions/123456/main",
        )

        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=111,
            email="topic@example.com",
            session_path="/data/sessions/123456/111",
        )

        # Delete only topic session
        await chat_session_repo.delete(chat_id, 111)

        # Verify main session still exists
        main_session = await chat_session_repo.get_by_chat_id(chat_id, 0)
        assert main_session is not None
        assert main_session["email"] == "main@example.com"

        # Verify topic session is deleted
        topic_session = await chat_session_repo.get_by_chat_id(chat_id, 111)
        assert topic_session is None

    async def test_upsert_creates_new_session(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test upsert creates new session if not exists."""
        chat_id = 123456
        thread_id = 555

        session = await chat_session_repo.upsert(
            chat_id=chat_id,
            thread_id=thread_id,
            email="new@example.com",
            session_path="/data/sessions/123456/555",
        )

        assert session is not None
        assert session["chat_id"] == chat_id
        assert session["thread_id"] == thread_id
        assert session["email"] == "new@example.com"

    async def test_upsert_updates_existing_session(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test upsert updates existing session."""
        chat_id = 123456
        thread_id = 666

        # Create initial session
        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            email="old@example.com",
            session_path="/data/sessions/old",
        )

        # Upsert with new data
        updated = await chat_session_repo.upsert(
            chat_id=chat_id,
            thread_id=thread_id,
            email="new@example.com",
            session_path="/data/sessions/new",
        )

        assert updated is not None
        assert updated["email"] == "new@example.com"
        assert updated["session_path"] == "/data/sessions/new"

        # Verify only one session exists
        session = await chat_session_repo.get_by_chat_id(chat_id, thread_id)
        assert session["email"] == "new@example.com"

    async def test_upsert_respects_thread_id_isolation(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test upsert doesn't affect sessions with different thread_id."""
        chat_id = 123456

        # Create session for main chat
        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=0,
            email="main@example.com",
            session_path="/data/sessions/main",
        )

        # Upsert session for topic (should create new, not update main)
        topic_session = await chat_session_repo.upsert(
            chat_id=chat_id,
            thread_id=777,
            email="topic@example.com",
            session_path="/data/sessions/topic",
        )

        # Verify both sessions exist with different data
        main_session = await chat_session_repo.get_by_chat_id(chat_id, 0)
        assert main_session["email"] == "main@example.com"
        assert topic_session["email"] == "topic@example.com"

    @pytest.mark.skip(
        reason="Requires PostgreSQL FOR UPDATE - SQLite doesn't support row locking"
    )
    async def test_lock_for_update_with_thread_id(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test locking session for update with thread_id."""
        chat_id = 123456
        thread_id = 888

        # Create session
        await chat_session_repo.create(
            chat_id=chat_id,
            thread_id=thread_id,
            email="test@example.com",
            session_path="/data/sessions/123456/888",
        )

        # Lock session (this would normally be inside a transaction)
        locked = await chat_session_repo.lock_for_update(chat_id, thread_id)

        assert locked is not None
        assert locked["chat_id"] == chat_id
        assert locked["thread_id"] == thread_id

    async def test_get_all_active_includes_all_threads(
        self, chat_session_repo: ChatSessionRepository
    ) -> None:
        """Test get_all_active returns sessions from all threads."""
        # Create sessions across multiple chats and threads
        await chat_session_repo.create(
            chat_id=111,
            thread_id=0,
            email="chat1_main@example.com",
            session_path="/data/sessions/111/main",
        )

        await chat_session_repo.create(
            chat_id=111,
            thread_id=100,
            email="chat1_topic@example.com",
            session_path="/data/sessions/111/100",
        )

        await chat_session_repo.create(
            chat_id=222,
            thread_id=0,
            email="chat2_main@example.com",
            session_path="/data/sessions/222/main",
        )

        # Get all active sessions
        sessions = await chat_session_repo.get_all_active()

        assert len(sessions) == 3
        emails = {s["email"] for s in sessions}
        assert "chat1_main@example.com" in emails
        assert "chat1_topic@example.com" in emails
        assert "chat2_main@example.com" in emails

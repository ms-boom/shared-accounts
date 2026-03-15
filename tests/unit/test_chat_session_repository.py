"""Integration tests for ChatSessionRepository."""

import pytest

from core.db.repositories.chat_session_repository import ChatSessionRepository


@pytest.mark.integration
async def test__create__default_thread_id(
    chat_session_repository: ChatSessionRepository,
) -> None:
    session = await chat_session_repository.create(
        chat_id=123456,
        email="test@example.com",
        session_path="/data/sessions/123456",
    )

    assert session["chat_id"] == 123456
    assert session["thread_id"] == 0
    assert session["email"] == "test@example.com"
    assert session["session_path"] == "/data/sessions/123456"
    assert "created_at" in session


@pytest.mark.integration
async def test__create__topic_thread_id(
    chat_session_repository: ChatSessionRepository,
) -> None:
    session = await chat_session_repository.create(
        chat_id=123456,
        thread_id=999,
        email="topic@example.com",
        session_path="/data/sessions/123456/999",
    )

    assert session["thread_id"] == 999
    assert session["email"] == "topic@example.com"


@pytest.mark.integration
async def test__get_by_chat_and_thread_id(
    chat_session_repository: ChatSessionRepository,
) -> None:
    await chat_session_repository.create(
        chat_id=123456,
        thread_id=555,
        email="test@example.com",
        session_path="/data/sessions/123456/555",
    )

    session = await chat_session_repository.get_by_chat_id(123456, 555)

    assert session is not None
    assert session["chat_id"] == 123456
    assert session["thread_id"] == 555


@pytest.mark.integration
async def test__get_nonexistent__returns_none(
    chat_session_repository: ChatSessionRepository,
) -> None:
    assert await chat_session_repository.get_by_chat_id(999999, 0) is None


@pytest.mark.integration
async def test__sessions_isolated_by_thread_id(
    chat_session_repository: ChatSessionRepository,
) -> None:
    chat_id = 123456

    main = await chat_session_repository.create(
        chat_id=chat_id, thread_id=0,
        email="main@example.com", session_path="/data/sessions/123456/main",
    )
    topic1 = await chat_session_repository.create(
        chat_id=chat_id, thread_id=111,
        email="topic1@example.com", session_path="/data/sessions/123456/111",
    )
    topic2 = await chat_session_repository.create(
        chat_id=chat_id, thread_id=222,
        email="topic2@example.com", session_path="/data/sessions/123456/222",
    )

    assert main["thread_id"] == 0
    assert topic1["thread_id"] == 111
    assert topic2["thread_id"] == 222

    retrieved_main = await chat_session_repository.get_by_chat_id(chat_id, 0)
    retrieved_t1 = await chat_session_repository.get_by_chat_id(chat_id, 111)
    retrieved_t2 = await chat_session_repository.get_by_chat_id(chat_id, 222)

    assert retrieved_main["email"] == "main@example.com"
    assert retrieved_t1["email"] == "topic1@example.com"
    assert retrieved_t2["email"] == "topic2@example.com"


@pytest.mark.integration
async def test__update_last_used(
    chat_session_repository: ChatSessionRepository,
) -> None:
    original = await chat_session_repository.create(
        chat_id=123456, thread_id=333,
        email="test@example.com", session_path="/data/sessions/123456/333",
    )
    assert original["last_used"] is None

    updated = await chat_session_repository.update_last_used(123456, 333)

    assert updated is not None
    assert updated["last_used"] is not None
    assert updated["thread_id"] == 333


@pytest.mark.integration
async def test__delete__specific_thread(
    chat_session_repository: ChatSessionRepository,
) -> None:
    await chat_session_repository.create(
        chat_id=123456, thread_id=444,
        email="test@example.com", session_path="/data/sessions/123456/444",
    )

    assert await chat_session_repository.get_by_chat_id(123456, 444) is not None

    result = await chat_session_repository.delete(123456, 444)
    assert result is True

    assert await chat_session_repository.get_by_chat_id(123456, 444) is None


@pytest.mark.integration
async def test__delete__only_affects_specific_thread(
    chat_session_repository: ChatSessionRepository,
) -> None:
    await chat_session_repository.create(
        chat_id=123456, thread_id=0,
        email="main@example.com", session_path="/data/sessions/123456/main",
    )
    await chat_session_repository.create(
        chat_id=123456, thread_id=111,
        email="topic@example.com", session_path="/data/sessions/123456/111",
    )

    await chat_session_repository.delete(123456, 111)

    main = await chat_session_repository.get_by_chat_id(123456, 0)
    assert main is not None
    assert main["email"] == "main@example.com"

    assert await chat_session_repository.get_by_chat_id(123456, 111) is None


@pytest.mark.integration
async def test__upsert__creates_new(
    chat_session_repository: ChatSessionRepository,
) -> None:
    session = await chat_session_repository.upsert(
        chat_id=123456, thread_id=555,
        email="new@example.com", session_path="/data/sessions/123456/555",
    )

    assert session["chat_id"] == 123456
    assert session["thread_id"] == 555
    assert session["email"] == "new@example.com"


@pytest.mark.integration
async def test__upsert__updates_existing(
    chat_session_repository: ChatSessionRepository,
) -> None:
    await chat_session_repository.create(
        chat_id=123456, thread_id=666,
        email="old@example.com", session_path="/data/sessions/old",
    )

    updated = await chat_session_repository.upsert(
        chat_id=123456, thread_id=666,
        email="new@example.com", session_path="/data/sessions/new",
    )

    assert updated["email"] == "new@example.com"
    assert updated["session_path"] == "/data/sessions/new"

    session = await chat_session_repository.get_by_chat_id(123456, 666)
    assert session["email"] == "new@example.com"


@pytest.mark.integration
async def test__upsert__respects_thread_id_isolation(
    chat_session_repository: ChatSessionRepository,
) -> None:
    await chat_session_repository.create(
        chat_id=123456, thread_id=0,
        email="main@example.com", session_path="/data/sessions/main",
    )

    topic = await chat_session_repository.upsert(
        chat_id=123456, thread_id=777,
        email="topic@example.com", session_path="/data/sessions/topic",
    )

    main = await chat_session_repository.get_by_chat_id(123456, 0)
    assert main["email"] == "main@example.com"
    assert topic["email"] == "topic@example.com"


@pytest.mark.integration
async def test__get_all_active__includes_all_threads(
    chat_session_repository: ChatSessionRepository,
) -> None:
    await chat_session_repository.create(
        chat_id=111, thread_id=0,
        email="chat1_main@example.com", session_path="/data/sessions/111/main",
    )
    await chat_session_repository.create(
        chat_id=111, thread_id=100,
        email="chat1_topic@example.com", session_path="/data/sessions/111/100",
    )
    await chat_session_repository.create(
        chat_id=222, thread_id=0,
        email="chat2_main@example.com", session_path="/data/sessions/222/main",
    )

    sessions = await chat_session_repository.get_all_active()

    assert len(sessions) == 3
    emails = {s["email"] for s in sessions}
    assert "chat1_main@example.com" in emails
    assert "chat1_topic@example.com" in emails
    assert "chat2_main@example.com" in emails

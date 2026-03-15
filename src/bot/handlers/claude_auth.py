"""Handlers for Claude Authorization Bot commands."""

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.config import Settings
from core.db.database import Database
from core.db.repositories.chat_session_repository import ChatSessionRepository
from core.db.repositories.task_repository import TaskRepository
from core.services.validation_service import ValidationService

logger = logging.getLogger(__name__)

router = Router(name="claude_auth")


def get_thread_id(message: Message) -> int:
    """
    Extract thread_id from message.

    Args:
        message: Telegram message

    Returns:
        thread_id (0 for main chat, >0 for topics)
    """
    return message.message_thread_id if message.message_thread_id else 0


@router.message(Command("init_session"))
async def init_session_handler(
    message: Message,
    database: Database,
    settings: Settings,
) -> None:
    """
    Handle /init_session <email> command.

    Initializes a new Claude session for the chat.
    Only available to group admins or in private chats.

    Args:
        message: Incoming message
        database: Database connection
        settings: Application settings
    """
    # Check if user is admin (for groups)
    if message.chat.type in ["group", "supergroup"]:
        # Check admin status
        if not message.bot or not message.from_user:
            await message.reply("❌ Unable to verify permissions.")
            return
        try:
            chat_member = await message.bot.get_chat_member(
                message.chat.id, message.from_user.id
            )
            is_admin = chat_member.status in ["creator", "administrator"]
            if not is_admin:
                await message.reply(
                    "❌ Only group administrators can initialize sessions. "
                    "Please contact your group admin."
                )
                return
        except Exception as e:
            logger.error(f"Failed to check admin status: {e}")
            await message.reply("❌ Failed to verify permissions. Please try again.")
            return

    # Parse email from command
    if not message.text:
        await message.reply("❌ Usage: /init_session <email>")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "❌ Please provide an email address.\n\nUsage: /init_session user@example.com"
        )
        return

    email = parts[1].strip()

    # Validate email
    if not ValidationService.validate_email(email):
        await message.reply(
            "❌ Invalid email format. Please provide a valid email address."
        )
        return

    # Check for existing session and create task using SQLAlchemy session
    thread_id = get_thread_id(message)

    async with database.session_maker() as session, session.begin():
        session_repo = ChatSessionRepository(session)
        existing_session = await session_repo.get_by_chat_id(message.chat.id, thread_id)

        if existing_session:
            await message.reply(
                f"⚠️ Session already exists for this chat (email: {existing_session['email']}).\n\n"
                f"Do you want to replace it with {email}? Reply 'yes' to confirm."
            )
            # TODO: Implement confirmation flow with FSM
            return

        # Create task
        if not message.from_user:
            await message.reply("❌ Unable to identify user.")
            return

        task_repo = TaskRepository(session)
        payload = {"email": email}

        task = await task_repo.create(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            task_type="init_session",
            payload=payload,
            thread_id=thread_id,
        )

        await message.reply(
            f"🔄 Initializing session for {email}.\n"
            "Please wait for the authorization link request..."
        )

        logger.info(
            f"Created init_session task {task['id']} for chat {message.chat.id}/{thread_id}"
        )


@router.message(Command("get_code"))
async def get_code_handler(
    message: Message,
    database: Database,
) -> None:
    """
    Handle /get_code <url> command.

    Extracts authorization code from Claude authorization URL.
    Available to all chat members.

    Args:
        message: Incoming message
        database: Database connection
    """
    # Check for existing session and create task using SQLAlchemy session
    thread_id = get_thread_id(message)

    async with database.session_maker() as db_session, db_session.begin():
        session_repo = ChatSessionRepository(db_session)
        session = await session_repo.get_by_chat_id(message.chat.id, thread_id)

        if not session:
            await message.reply(
                "❌ No active session found for this chat.\n\n"
                "Run /init_session <email> first to initialize a session."
            )
            return

        # Parse URL from command
        if not message.text:
            await message.reply("❌ Usage: /get_code <url>")
            return

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply(
                "❌ Please provide the Claude authorization URL.\n\n"
                "Usage: /get_code https://claude.ai/auth/authorize?..."
            )
            return

        auth_url = parts[1].strip()

        # Validate URL
        if not ValidationService.is_claude_auth_url(auth_url):
            await message.reply(
                "❌ Invalid auth URL format. Please provide a valid Claude authorization URL.\n\n"
                "Expected format: https://claude.ai/auth/authorize?..."
            )
            return

        # Create task
        if not message.from_user:
            await message.reply("❌ Unable to identify user.")
            return

        task_repo = TaskRepository(db_session)
        payload = {"auth_url": auth_url}

        task = await task_repo.create(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            task_type="get_code",
            payload=payload,
            thread_id=thread_id,
        )

        await message.reply("🔄 Extracting authorization code...")

        logger.info(
            f"Created get_code task {task['id']} for chat {message.chat.id}/{thread_id}"
        )


@router.message(Command("health"))
async def health_handler(
    message: Message,
    database: Database,
) -> None:
    """
    Handle /health command.

    Shows bot status, database connection, active sessions, and pending tasks.
    Available to all users.

    Args:
        message: Incoming message
        database: Database connection
    """
    try:
        # Check database connection and get stats using SQLAlchemy session
        async with database.session_maker() as db_session, db_session.begin():
            # Check database connection
            import sqlalchemy as sa

            db_status: str
            try:
                result = await db_session.execute(sa.text("SELECT 1"))
                db_status = "✅ Connected" if result else "❌ Error"
            except Exception as e:
                db_status = f"❌ Disconnected ({str(e)})"
                logger.error(f"Database health check failed: {e}")

            # Get active sessions count
            session_repo = ChatSessionRepository(db_session)
            sessions_count: int | str
            try:
                sessions = await session_repo.get_all_active()
                sessions_count = len(sessions)
            except Exception as e:
                sessions_count = "Error"
                logger.error(f"Failed to get sessions count: {e}")

            # Get pending tasks count
            task_repo = TaskRepository(db_session)
            pending_count: int | str
            try:
                pending_count = await task_repo.get_pending_count()
            except Exception as e:
                pending_count = "Error"
                logger.error(f"Failed to get pending tasks count: {e}")

        # Format response
        status_message = (
            "✅ <b>Bot Status</b>\n\n"
            f"• Database: {db_status}\n"
            f"• Active sessions: {sessions_count}\n"
            f"• Pending tasks: {pending_count}\n"
            f"• Worker: Running\n"
        )

        await message.reply(status_message, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        await message.reply("❌ Failed to retrieve bot status. Please try again later.")


@router.message()
async def handle_claude_url(
    message: Message,
    database: Database,
) -> None:
    """
    Handle Claude login URLs sent by users.

    Detects Claude login links and processes them automatically.
    Ignores other messages.

    Args:
        message: Incoming message
        database: Database connection
    """
    if not message.text:
        return

    # Check if message contains Claude login URL
    if not ValidationService.is_claude_login_url(message.text.strip()):
        return

    login_url = message.text.strip()
    thread_id = get_thread_id(message)

    # Check for pending init_session and create task using SQLAlchemy session
    async with database.session_maker() as db_session, db_session.begin():
        task_repo = TaskRepository(db_session)
        recent_tasks = await task_repo.get_by_chat_id(
            message.chat.id, limit=5, thread_id=thread_id
        )

        # Find recent init_session task that's processing
        init_task = None
        for task in recent_tasks:
            if task["task_type"] == "init_session" and task["status"] in [
                "pending",
                "processing",
            ]:
                init_task = task
                break

        if not init_task:
            # No pending init_session, inform user
            await message.reply(
                "ℹ️ This looks like a Claude login link.\n\n"
                "If you want to initialize a session, please run /init_session <email> first."
            )
            return

        # Create task to process login link
        if not message.from_user:
            await message.reply("❌ Unable to identify user.")
            return

        payload = {"login_url": login_url}

        task = await task_repo.create(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            task_type="process_login_link",
            payload=payload,
            thread_id=thread_id,
        )

        await message.reply("🔄 Processing login link...")

        logger.info(
            f"Created process_login_link task {task['id']} for chat {message.chat.id}/{thread_id}"
        )

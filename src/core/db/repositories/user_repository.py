"""Repository for User model database operations.

Pattern from statements/ - repository accepts session, doesn't manage transactions.
"""

import logging
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.db.models import User
from core.exceptions import DatabaseError, UserNotFoundError

logger = logging.getLogger(__name__)


def _row_to_dict(user: User) -> dict:
    """Convert User model to dict for backward compatibility."""
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "language_code": user.language_code,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


class UserRepository:
    """Repository pattern for User model operations.

    Pattern from statements/ - accepts session, uses flush() not commit().
    Transaction management is handled by caller (use case or test).
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session injection.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session

    async def get_by_id(self, user_id: int) -> dict | None:
        """Get user by Telegram user_id.

        Args:
            user_id: Telegram user_id

        Returns:
            User data as dict or None if not found

        Raises:
            DatabaseError: If database query fails
        """
        try:
            stmt = sa.select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()
            return _row_to_dict(user) if user else None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            raise DatabaseError(f"Failed to get user: {e}") from e

    async def create(
        self,
        user_id: int,
        username: str | None,
        first_name: str,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> dict:
        """Create a new user record.

        Args:
            user_id: Telegram user_id
            username: User username (optional)
            first_name: User first name
            last_name: User last name (optional)
            language_code: User language code (optional)

        Returns:
            Created user data as dict

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            user = User(
                id=user_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.session.add(user)
            await self.session.flush()  # Not commit - transaction managed by caller
            logger.info(f"Created user: {user_id} ({first_name})")
            return _row_to_dict(user)
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            raise DatabaseError(f"Failed to create user: {e}") from e

    async def update(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> dict:
        """Update user information.

        Args:
            user_id: Telegram user_id
            username: New username (optional)
            first_name: New first name (optional)
            last_name: New last name (optional)
            language_code: New language code (optional)

        Returns:
            Updated user data as dict

        Raises:
            UserNotFoundError: If user doesn't exist
            DatabaseError: If database operation fails
        """
        try:
            # Get existing user
            stmt = sa.select(User).where(User.id == user_id)
            result = await self.session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                raise UserNotFoundError(f"User {user_id} not found")

            # Update fields if provided
            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name
            if last_name is not None:
                user.last_name = last_name
            if language_code is not None:
                user.language_code = language_code

            user.updated_at = datetime.utcnow()

            await self.session.flush()
            logger.info(f"Updated user: {user_id}")
            return _row_to_dict(user)
        except UserNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update user {user_id}: {e}")
            raise DatabaseError(f"Failed to update user: {e}") from e

"""Custom SQLAlchemy dialect for asyncpg.

Pattern from intern-contest-cabinet project - critical for proper event loop handling
in async environments and savepoint operations.
"""

import json
import uuid

import asyncpg
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql.asyncpg


class CustomAsyncpgDialect(sqlalchemy.dialects.postgresql.asyncpg.PGDialect_asyncpg):
    """Custom asyncpg dialect for proper event loop handling.

    This dialect patches JSONB handling to work with both str and bytes.
    Critical for proper event loop handling and savepoint operations in async environments.

    Pattern from intern-contest-cabinet/app/db/dialect.py
    """

    supports_statement_cache = True

    async def setup_asyncpg_jsonb_codec(self, conn: asyncpg.Connection) -> None:
        """Set up JSONB codec for asyncpg.

        This occurs for all new connections and
        can be overridden by third party dialects.
        """
        asyncpg_connection = conn._connection
        deserializer = self._json_deserializer or json.loads

        def _jsonb_encoder(str_or_bytes: str | bytes) -> bytes:
            # \x01 is the prefix for jsonb used by PostgreSQL.
            # asyncpg requires it when format='binary'
            if isinstance(str_or_bytes, str):
                value = str_or_bytes.encode()
            else:
                value = str_or_bytes
            return b"\x01" + value

        def _jsonb_decoder(
            bin_value: bytes,
        ) -> dict | list | str | int | float | bool | None:
            # the byte is the \x01 prefix for jsonb used by PostgreSQL.
            # asyncpg returns it when format='binary'
            return deserializer(bin_value[1:].decode())  # type: ignore[no-any-return]

        await asyncpg_connection.set_type_codec(
            "jsonb",
            encoder=_jsonb_encoder,
            decoder=_jsonb_decoder,
            schema="pg_catalog",
            format="binary",
        )


class CConnection(asyncpg.Connection):
    """Custom asyncpg connection class.

    Pattern from intern-contest-cabinet/app/db/dialect.py for proper event loop handling
    and savepoint operations.
    """

    def _get_unique_id(self, prefix: str) -> str:
        return f"__asyncpg_{prefix}_{uuid.uuid4()}__"


# Register custom dialect globally
# Pattern from intern-contest-cabinet - critical for proper event loop handling
sa.dialects.registry.register(
    "postgresql.asyncpg",
    "bot.db.dialect",
    "CustomAsyncpgDialect",
)

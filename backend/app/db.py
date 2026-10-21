import os
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

SQLITE_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS transcripts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'mock',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'mock',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        ok INTEGER NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
]

PG_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS transcripts (
        id BIGSERIAL PRIMARY KEY,
        content TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'mock',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id BIGSERIAL PRIMARY KEY,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        conversation_id BIGINT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        provider TEXT NOT NULL DEFAULT 'mock',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_events (
        id BIGSERIAL PRIMARY KEY,
        action TEXT NOT NULL,
        ok INTEGER NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
]


def database_url() -> str:
    return os.getenv("DATABASE_URL", "sqlite:///./speech.db")


def make_engine():
    url = database_url()
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        if ":memory:" in url or url.rstrip("/").endswith("sqlite://"):
            return create_engine(
                "sqlite://",
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    return create_engine(url, pool_pre_ping=True)


def is_sqlite(engine) -> bool:
    return engine.dialect.name == "sqlite"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_schema(engine) -> None:
    statements = SQLITE_SCHEMA if is_sqlite(engine) else PG_SCHEMA
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))


def ping(engine) -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True


def insert_transcript(engine, content: str, provider: str) -> int:
    now = _now()
    with engine.begin() as conn:
        if is_sqlite(engine):
            result = conn.execute(
                text(
                    "INSERT INTO transcripts(content, provider, created_at) "
                    "VALUES (:content, :provider, :created_at)"
                ),
                {"content": content, "provider": provider, "created_at": now},
            )
            return int(result.lastrowid)
        return int(
            conn.execute(
                text(
                    "INSERT INTO transcripts(content, provider) "
                    "VALUES (:content, :provider) RETURNING id"
                ),
                {"content": content, "provider": provider},
            ).scalar_one()
        )


def list_transcripts(engine, limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, content, provider, created_at FROM transcripts "
                "ORDER BY id DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        return [_row_item(row) for row in rows]


def delete_transcript(engine, record_id: int) -> bool:
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM transcripts WHERE id = :id"), {"id": record_id}
        )
        return result.rowcount > 0


def create_conversation(engine) -> int:
    now = _now()
    with engine.begin() as conn:
        if is_sqlite(engine):
            result = conn.execute(
                text("INSERT INTO conversations(created_at) VALUES (:created_at)"),
                {"created_at": now},
            )
            return int(result.lastrowid)
        return int(
            conn.execute(
                text("INSERT INTO conversations DEFAULT VALUES RETURNING id")
            ).scalar_one()
        )


def list_conversations(engine, limit: int = 20) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT c.id, c.created_at, "
                "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS n "
                "FROM conversations c ORDER BY c.id DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        items = []
        for row in rows:
            created = row.created_at
            if hasattr(created, "isoformat"):
                created = created.isoformat()
            items.append({"id": row.id, "created_at": created, "messages": int(row.n)})
        return items


def delete_conversation(engine, conversation_id: int) -> bool:
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM messages WHERE conversation_id = :id"),
            {"id": conversation_id},
        )
        result = conn.execute(
            text("DELETE FROM conversations WHERE id = :id"),
            {"id": conversation_id},
        )
        return result.rowcount > 0


def conversation_exists(engine, conversation_id: int) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM conversations WHERE id = :id"),
            {"id": conversation_id},
        ).first()
        return row is not None


def add_message(engine, conversation_id: int, role: str, content: str, provider: str) -> int:
    now = _now()
    with engine.begin() as conn:
        if is_sqlite(engine):
            result = conn.execute(
                text(
                    "INSERT INTO messages(conversation_id, role, content, provider, created_at) "
                    "VALUES (:cid, :role, :content, :provider, :created_at)"
                ),
                {
                    "cid": conversation_id,
                    "role": role,
                    "content": content,
                    "provider": provider,
                    "created_at": now,
                },
            )
            return int(result.lastrowid)
        return int(
            conn.execute(
                text(
                    "INSERT INTO messages(conversation_id, role, content, provider) "
                    "VALUES (:cid, :role, :content, :provider) RETURNING id"
                ),
                {
                    "cid": conversation_id,
                    "role": role,
                    "content": content,
                    "provider": provider,
                },
            ).scalar_one()
        )


def list_messages(engine, conversation_id: int, limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, conversation_id, role, content, provider, created_at "
                "FROM messages WHERE conversation_id = :cid "
                "ORDER BY id ASC LIMIT :limit"
            ),
            {"cid": conversation_id, "limit": limit},
        )
        items = []
        for row in rows:
            created = row.created_at
            if hasattr(created, "isoformat"):
                created = created.isoformat()
            items.append(
                {
                    "id": row.id,
                    "conversation_id": row.conversation_id,
                    "role": row.role,
                    "content": row.content,
                    "provider": row.provider,
                    "created_at": created,
                }
            )
        return items


def add_audit(engine, action: str, ok: bool, detail: str = "") -> None:
    now = _now()
    safe = (detail or "")[:300]
    with engine.begin() as conn:
        if is_sqlite(engine):
            conn.execute(
                text(
                    "INSERT INTO audit_events(action, ok, detail, created_at) "
                    "VALUES (:action, :ok, :detail, :created_at)"
                ),
                {"action": action, "ok": int(ok), "detail": safe, "created_at": now},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO audit_events(action, ok, detail) "
                    "VALUES (:action, :ok, :detail)"
                ),
                {"action": action, "ok": int(ok), "detail": safe},
            )


def list_audit(engine, limit: int = 50) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, action, ok, detail, created_at FROM audit_events "
                "ORDER BY id DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        items = []
        for row in rows:
            created = row.created_at
            if hasattr(created, "isoformat"):
                created = created.isoformat()
            items.append(
                {
                    "id": row.id,
                    "action": row.action,
                    "ok": bool(row.ok),
                    "detail": row.detail,
                    "created_at": created,
                }
            )
        return items


def prune_older_than(engine, hours: int) -> int:
    if hours <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_value = cutoff.isoformat() if is_sqlite(engine) else cutoff
    deleted = 0
    with engine.begin() as conn:
        for table in ("transcripts", "messages", "audit_events", "conversations"):
            if table == "conversations":
                result = conn.execute(
                    text(
                        "DELETE FROM conversations WHERE created_at < :cutoff "
                        "AND id NOT IN (SELECT conversation_id FROM messages)"
                    ),
                    {"cutoff": cutoff_value},
                )
            else:
                result = conn.execute(
                    text(f"DELETE FROM {table} WHERE created_at < :cutoff"),
                    {"cutoff": cutoff_value},
                )
            deleted += int(result.rowcount or 0)
    return deleted


def _row_item(row) -> dict:
    created = row.created_at
    if hasattr(created, "isoformat"):
        created = created.isoformat()
    return {
        "id": row.id,
        "content": row.content,
        "provider": row.provider,
        "created_at": created,
    }

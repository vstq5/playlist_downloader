from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Float, JSON, Text, Boolean, DateTime
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
import logging
import json
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from sqlalchemy import inspect, text
from sqlalchemy import func
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _to_iso_z(dt: datetime) -> str:
    # The DB stores naive UTC datetimes; serialize with an explicit UTC designator
    # so browsers don't treat the string as local time.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")

# --- Models ---
class Base(DeclarativeBase):
    pass

class Task(Base):
    __tablename__ = "tasks"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Timestamps for lifecycle guards / UI
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Owner ID for Device Isolation
    owner_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    # JSON Blobs for complex structures (Playlist info, options)
    playlist_info: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    options: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)

    # Path to the generated ZIP artifact.
    # Historical note: the underlying DB column is named "s3_key" from an earlier
    # storage approach; we keep the column name for compatibility.
    zip_path: Mapped[Optional[str]] = mapped_column("s3_key", String, nullable=True)
    
    # Legacy fields mapped to JSON or separate columns if needed
    # For MVP, we store the heavy playlist object in JSON to avoid huge schema refactor
    # but strictly typed columns for status/progress queries.



# --- Database Manager ---
class DatabaseManager:
    def __init__(self):
        # Render Free Tier often limits connections (e.g. 20-50).
        # We set conservative pool limits to be safe.
        
        url = settings.DATABASE_URL
        if url and url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url and url.startswith("postgresql://") and "asyncpg" not in url:
             url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        connect_args: dict[str, Any] = {}

        # Managed Postgres providers (including Render) may require SSL.
        # They often append `?sslmode=require`, but not always.
        # asyncpg does not support `sslmode` in the DSN query string; it expects an `ssl` kwarg.
        # We strip ssl/sslmode query params and set connect_args["ssl"] when appropriate.
        if url and url.startswith("postgresql+"):
            parsed = urlparse(url)
            query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))

            sslmode = (query_items.pop("sslmode", "") or "").lower()
            ssl_flag = (query_items.pop("ssl", "") or "").lower()

            hostname = (parsed.hostname or "").lower()
            is_render_host = (hostname.endswith("render.com") or hostname.endswith("render.com."))

            enable_ssl = False
            if sslmode:
                enable_ssl = sslmode != "disable"
            elif ssl_flag:
                enable_ssl = ssl_flag in {"1", "true", "yes", "require", "required"}
            elif is_render_host:
                enable_ssl = True

            if enable_ssl:
                connect_args["ssl"] = True

            rebuilt_query = urlencode(query_items)
            url = urlunparse(parsed._replace(query=rebuilt_query))

        engine_kwargs = {
            "echo": False,
        }

        # SQLite (aiosqlite) does not support the same pooling knobs as Postgres.
        if url.startswith("postgresql+"):
            engine_kwargs.update({"pool_size": 5, "max_overflow": 10})

        self.engine = create_async_engine(url, connect_args=connect_args, **engine_kwargs)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            # Lightweight schema migration for existing databases.
            # SQLAlchemy's create_all() does not add new columns to an existing table.
            def _get_task_columns(sync_conn) -> set[str]:
                try:
                    insp = inspect(sync_conn)
                    return {c["name"] for c in insp.get_columns("tasks")}
                except Exception:
                    return set()

            existing_cols = await conn.run_sync(_get_task_columns)
            if existing_cols:
                required_cols: list[tuple[str, str, str | None]] = [
                    ("owner_id", "VARCHAR", None),
                    ("status", "VARCHAR", None),
                    ("progress", "DOUBLE PRECISION", None),
                    ("message", "VARCHAR", None),
                    ("created_at", "TIMESTAMP", None),
                    ("updated_at", "TIMESTAMP", "UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL"),
                    ("status_updated_at", "TIMESTAMP", "UPDATE tasks SET status_updated_at = created_at WHERE status_updated_at IS NULL"),
                    ("playlist_info", "JSON", None),
                    ("options", "JSON", None),
                    ("s3_key", "VARCHAR", None),
                ]

                missing = [name for (name, _ddl, _backfill) in required_cols if name not in existing_cols]
                if missing:
                    logger.info("Schema Update: tasks table missing columns: %s", ", ".join(missing))

                for col_name, ddl_type, backfill_sql in required_cols:
                    if col_name in existing_cols:
                        continue
                    try:
                        await conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col_name} {ddl_type}"))
                        logger.info("Schema Update: Added tasks.%s", col_name)
                    except Exception as e:
                        # If multiple instances race, or provider doesn't like the type keyword,
                        # we log and continue (the app may still work if column already exists).
                        logger.error("Schema Update Failed adding %s: %s", col_name, e)
                        continue

                    if backfill_sql:
                        try:
                            await conn.execute(text(backfill_sql))
                        except Exception:
                            pass

                # Ensure index for owner_id for performance/tenant isolation.
                try:
                    await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tasks_owner_id ON tasks (owner_id)"))
                except Exception:
                    pass
            else:
                # Table was likely just created; nothing to migrate.
                logger.info("Schema Update: tasks table created fresh")
            
        logger.info("PostgreSQL Tables initialized.")

    async def create_task(self, task_id: str, url: str, options: Optional[dict] = None, owner_id: Optional[str] = None):
        async with self.async_session() as session:
            task = Task(
                id=task_id, 
                status="pending", 
                message="Queued", 
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                status_updated_at=datetime.utcnow(),
                options=options or {},
                owner_id=owner_id # Save specific owner
            )
            # Initial playlist info shell
            task.playlist_info = {"url": url} 
            session.add(task)
            await session.commit()

    async def save_full_task_state(self, task_id: str, full_state_dict: dict):
        """
        Syncs the in-memory dict state to Postgres.
        """
        async with self.async_session() as session:
            task = await session.get(Task, task_id)
            if not task:
                task = Task(id=task_id)
                session.add(task)

            new_status = full_state_dict.get("status")
            if new_status and new_status != task.status:
                task.status_updated_at = datetime.utcnow()

            task.status = new_status or task.status
            task.progress = full_state_dict.get("progress", task.progress or 0)
            task.message = full_state_dict.get("message")
            task.playlist_info = full_state_dict.get("playlist")
            task.options = full_state_dict.get("options")
            task.zip_path = full_state_dict.get("zip_path")
            task.updated_at = datetime.utcnow()
            
            await session.commit()

    async def cleanup_interrupted_tasks(self):
        """
         Efficiently marks 'preparing', 'downloading', 'zipping' tasks as error
         via a single SQL update, avoiding memory overhead.
        """
        from sqlalchemy import update
        async with self.async_session() as session:
            stmt = (
                update(Task)
                .where(Task.status.in_(['preparing', 'downloading', 'zipping']))
                .values(status='error', message='Interrupted by server restart')
            )
            await session.execute(stmt)
            await session.commit()

    async def get_all_tasks(self, limit: int = 50, owner_id: Optional[str] = None):
        from sqlalchemy import select, desc
        async with self.async_session() as session:
            # Optimize: Only get recent tasks to prevent O(N) payload growth
            stmt = select(Task).order_by(desc(Task.created_at)).limit(limit)
            
            # Strict owner filter when provided
            if owner_id:
                stmt = stmt.where(Task.owner_id == owner_id)
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            # Reconstruct Dict format for Server compatibility
            data = {}
            for t in tasks:
                playlist_info = t.playlist_info or {}
                data[t.id] = {
                    "id": t.id,
                    "owner_id": t.owner_id,
                    "status": t.status,
                    "progress": t.progress,
                    "message": t.message,
                    "created_at": _to_iso_z(t.created_at),
                    "updated_at": _to_iso_z(t.updated_at or t.created_at),
                    "status_updated_at": _to_iso_z(t.status_updated_at or t.created_at),
                    "playlist": playlist_info,
                    "options": t.options,
                    "zip_path": t.zip_path,
                    # Convenience fields for UI
                    "title": playlist_info.get("title") or playlist_info.get("url") or "",
                    "provider": playlist_info.get("provider") or "",
                    "thumbnail": playlist_info.get("thumbnail") or playlist_info.get("cover_url"),
                    "track_count": playlist_info.get("track_count")
                }
            return data

    async def get_recent_tasks(self, limit: int = 10, owner_id: Optional[str] = None):
        # Re-using logic, or keeping distinct if the interface differs significantly
        # accessing get_all_tasks internally or keeping separate for lightweight history
        from sqlalchemy import select, desc
        async with self.async_session() as session:
            stmt = select(Task).where(Task.status == 'completed')
            
            # Privacy Filter
            if owner_id:
                stmt = stmt.where(Task.owner_id == owner_id)
            
            stmt = stmt.order_by(desc(Task.created_at)).limit(limit)
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            history = []
            for t in tasks:
                 history.append({
                     "task_id": t.id,
                     "title": t.playlist_info.get("title", "Unknown") if t.playlist_info else "Unknown",
                     "provider": t.playlist_info.get("provider", "unknown") if t.playlist_info else "unknown",
                     "track_count": t.playlist_info.get("track_count", 0) if t.playlist_info else 0,
                     "zip_path": t.zip_path,
                     "timestamp": _to_iso_z(t.created_at)
                 })
            return history

    async def get_task(self, task_id: str) -> Optional[Dict]:
        async with self.async_session() as session:
            t = await session.get(Task, task_id)
            if not t: return None
            playlist_info = t.playlist_info or {}
            return {
                "id": t.id,
                "owner_id": t.owner_id,
                "status": t.status,
                "progress": t.progress,
                "message": t.message,
                "created_at": _to_iso_z(t.created_at),
                "updated_at": _to_iso_z(t.updated_at or t.created_at),
                "status_updated_at": _to_iso_z(t.status_updated_at or t.created_at),
                "playlist": playlist_info,
                "options": t.options,
                "zip_path": t.zip_path,
                # Convenience fields for UI
                "title": playlist_info.get("title") or playlist_info.get("url") or "",
                "provider": playlist_info.get("provider") or "",
                "thumbnail": playlist_info.get("thumbnail") or playlist_info.get("cover_url"),
                "track_count": playlist_info.get("track_count")
            }

    async def delete_task(self, task_id: str, owner_id: Optional[str] = None):
         async with self.async_session() as session:
             task = await session.get(Task, task_id)
             if task:
                 # Security Check: Only delete if owner matches (strict)
                 if owner_id is None or task.owner_id != owner_id:
                     return False
                 
                 await session.delete(task)
                 await session.commit()
                 return True
             return False

    async def get_task_for_owner(self, task_id: str, owner_id: str) -> Optional[Dict]:
        task = await self.get_task(task_id)
        if not task:
            return None
        # Strict check: deny legacy/unowned tasks too
        async with self.async_session() as session:
            t = await session.get(Task, task_id)
            if not t or t.owner_id != owner_id:
                return None
        return task

    async def request_cancel(self, task_id: str, owner_id: str) -> bool:
        async with self.async_session() as session:
            task = await session.get(Task, task_id)
            if not task or task.owner_id != owner_id:
                return False
            options = task.options or {}
            options["cancel_requested"] = True
            task.options = options
            task.updated_at = datetime.utcnow()
            await session.commit()
            return True

    async def get_task_owner_id(self, task_id: str) -> Optional[str]:
        async with self.async_session() as session:
            task = await session.get(Task, task_id)
            if not task:
                return None
            return task.owner_id

    async def count_tasks_for_owner(self, *, owner_id: str, statuses: list[str]) -> int:
        from sqlalchemy import select

        async with self.async_session() as session:
            stmt = select(func.count()).select_from(Task).where(Task.owner_id == owner_id)
            if statuses:
                stmt = stmt.where(Task.status.in_(statuses))
            result = await session.execute(stmt)
            count_val = result.scalar_one()
            return int(count_val or 0)

db = DatabaseManager()

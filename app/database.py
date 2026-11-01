from pathlib import Path
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=0,
    pool_timeout=10,
    connect_args={"connect_timeout": 5},
    isolation_level="READ COMMITTED",
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations():
    # Optional privileged migration connection is never used for retrieval.
    migration_url = os.environ.get("MIGRATION_DATABASE_URL")
    migration_engine = create_engine(migration_url, connect_args={"connect_timeout": 5}) if migration_url else engine
    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"
    try:
        with migration_engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)"))
            # Serialize migration runners only, never retrieval transactions.
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("LOCK TABLE schema_migrations IN EXCLUSIVE MODE"))
            applied = set(conn.execute(text("SELECT name FROM schema_migrations")).scalars())
            for sql_file in sorted(migrations_dir.glob("*.sql")):
                if sql_file.name not in applied:
                    conn.exec_driver_sql(sql_file.read_text(encoding="utf-8"))
                    conn.execute(text("INSERT INTO schema_migrations(name) VALUES (:name)"), {"name": sql_file.name})
    finally:
        if migration_engine is not engine:
            migration_engine.dispose()

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker


# SQLite does not enforce foreign keys/cascades by default.
# We enable PRAGMA foreign_keys dynamically for SQLite connections.
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass
    finally:
        cursor.close()


DB_PATH = os.getenv("DB_PATH")
if not DB_PATH:
    DB_PATH = "backend/data/monitor.db" if Path("backend").exists() else "data/monitor.db"
db_file = Path(DB_PATH)
if db_file.parent:
    db_file.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_file}"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
# Register event listener ONLY on the SQLite engine instance
event.listen(engine, "connect", set_sqlite_pragma)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


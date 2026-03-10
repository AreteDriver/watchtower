"""Migrate existing Cycle 4 database to Cycle 5 schema.

Adds cycle columns to existing tables and creates new C5 tables.
Safe to run multiple times — all operations use IF NOT EXISTS / try-except.
"""

import sqlite3
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.core.config import settings
from backend.db.database import SCHEMA


def migrate() -> None:
    db_path = Path(settings.DB_PATH)
    if not db_path.exists():
        print(f"No database at {db_path} — fresh init will handle schema.")
        return

    conn = sqlite3.connect(str(db_path))

    # Add cycle column to existing tables
    alter_statements = [
        "ALTER TABLE killmails ADD COLUMN cycle INTEGER DEFAULT 5",
        "ALTER TABLE gate_events ADD COLUMN cycle INTEGER DEFAULT 5",
    ]
    for stmt in alter_statements:
        try:
            conn.execute(stmt)
            table = stmt.split("TABLE ")[1].split(" ADD")[0]
            print(f"  Added cycle column to {table}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                pass  # Already migrated
            else:
                raise

    # Run full schema to create new tables + indexes
    conn.executescript(SCHEMA)
    print("  C5 tables and indexes created.")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()

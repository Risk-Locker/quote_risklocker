"""Purge all rows from correction_memory table."""
from __future__ import annotations

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from sqlalchemy import text


def main():
    print("Purging correction_memory table...")
    db = SessionLocal()
    try:
        res = db.execute(text("DELETE FROM correction_memory;"))
        db.commit()
        rowcount = getattr(res, "rowcount", 0)
        print(f"Successfully purged {rowcount} rows from correction_memory.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

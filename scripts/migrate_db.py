#!/usr/bin/env python3
"""
Database migration script.

Creates all required tables in the database.

Usage:
    python scripts/migrate_db.py

Environment:
    DATABASE_URL: PostgreSQL connection string
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import close_db, init_db, is_db_configured


async def main() -> None:
    """Run database migrations."""
    print("🚀 Running database migration...")

    if not is_db_configured():
        print("❌ DATABASE_URL not configured. Set it in .env file.")
        print("\nExample:")
        print('  DATABASE_URL="postgresql://user:pass@host/dbname?sslmode=require"')
        sys.exit(1)

    try:
        await init_db()
        print("✅ Database tables created successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python
"""Add commands column to repo_configs table."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_session
from sqlalchemy import text


async def migrate():
    async with get_session() as session:
        await session.execute(text("""
            ALTER TABLE repo_configs 
            ADD COLUMN IF NOT EXISTS commands JSONB DEFAULT '{"fix": true}'::jsonb
        """))
        await session.commit()
        print("✅ Added commands column")


if __name__ == "__main__":
    asyncio.run(migrate())

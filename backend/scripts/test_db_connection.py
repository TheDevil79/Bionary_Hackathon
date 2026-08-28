"""
Lightweight diagnostic script to verify PostgreSQL & pgvector connectivity.

Usage:
    python -m scripts.test_db_connection
"""

import asyncio
import sys
import traceback
from sqlalchemy import text
from app.core.config import settings
from app.core.database import get_engine

async def main():
    print("=" * 60)
    print("EvidenceLens Database Connectivity Diagnostic")
    print("=" * 60)

    raw_url = settings.database_url
    if not raw_url:
        print("[FAIL] DATABASE_URL is not set in backend/.env or environment.")
        print("Please configure DATABASE_URL in backend/.env and re-run.")
        sys.exit(1)

    # Obfuscate password for safe display
    sanitized_url = settings.async_database_url
    if "@" in sanitized_url:
        prefix, host_part = sanitized_url.split("@", 1)
        if ":" in prefix:
            user_part = prefix.split(":", 2)[0] + ":" + prefix.split(":", 2)[1]
            sanitized_url = f"{user_part}:****@{host_part}"

    print(f"Connecting to: {sanitized_url}")

    engine = get_engine()
    if engine is None:
        print("[FAIL] Could not construct SQLAlchemy async engine.")
        sys.exit(1)

    try:
        async with engine.connect() as conn:
            # 1. Ping
            result = await conn.execute(text("SELECT 1;"))
            val = result.scalar()
            print(f"[OK] Basic ping successful (SELECT 1 -> {val})")

            # 2. Check PostgreSQL version
            version_res = await conn.execute(text("SELECT version();"))
            version_str = version_res.scalar()
            print(f"[OK] PostgreSQL Version: {version_str.split(',')[0]}")

            # 3. Check pgvector extension
            vec_res = await conn.execute(
                text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
            )
            vec_row = vec_res.first()
            if vec_row:
                print(f"[OK] pgvector extension detected: version {vec_row[1]}")
            else:
                print("[WARN] pgvector extension is NOT yet enabled in database.")
                print("       (Alembic will automatically enable it upon migration)")

        print("=" * 60)
        print("[SUCCESS] Database is fully reachable and operational.")
        print("=" * 60)
    except Exception as exc:
        print(f"[FAIL] Database connection failed: {exc}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

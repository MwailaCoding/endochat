"""Enable pgvector (vector extension) on the configured DATABASE_URL."""

import asyncio
import os

import asyncpg


async def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set in environment or .env")

    # Ensure SSL is required for Render external Postgres
    if "sslmode" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{sep}sslmode=require"

    print(f"Connecting to: {database_url}")
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        print("pgvector extension enabled successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())


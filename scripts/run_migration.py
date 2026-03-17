"""Run database migrations."""

import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


async def run_migration():
    """Execute all SQL migrations in scripts/migrations (sorted by filename)."""

    # Load .env so DATABASE_URL is available
    project_root = Path(__file__).resolve().parents[1]
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    # Prefer DATABASE_URL (Render / external DB); fallback to local default
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:2030@localhost:5432/endochat")

    # Ensure SSL when connecting to Render external Postgres
    if "render.com" in db_url and "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = f"{db_url}{sep}sslmode=require"

    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print(f"Migrations folder not found: {migrations_dir}")
        return False

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print(f"No migration files found in: {migrations_dir}")
        return False

    print(f"Connecting to database: {db_url}")

    try:
        conn = await asyncpg.connect(db_url)
        print("Connected successfully!")

        for migration_file in migration_files:
            print(f"Running migration: {migration_file.name}")
            sql = migration_file.read_text(encoding="utf-8")
            await conn.execute(sql)

        print("All migrations completed successfully!")

        await conn.close()
        return True
        
    except asyncpg.PostgresError as e:
        print(f"Database error: {e}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_migration())
    exit(0 if success else 1)

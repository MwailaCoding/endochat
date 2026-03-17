"""Run database migrations."""

import asyncio
import asyncpg
from pathlib import Path


async def run_migration():
    """Execute all SQL migrations in scripts/migrations (sorted by filename)."""

    # Database connection (keep existing default; can be refactored later to env/settings)
    db_url = "postgresql://postgres:2030@localhost:5432/endochat"

    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        print(f"Migrations folder not found: {migrations_dir}")
        return False

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print(f"No migration files found in: {migrations_dir}")
        return False

    print("Connecting to database...")

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

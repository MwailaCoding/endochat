"""Run database migrations."""

import asyncio
import asyncpg
from pathlib import Path


async def run_migration():
    """Execute the enhanced features migration."""
    
    # Database connection
    db_url = "postgresql://postgres:2030@localhost:5432/endochat"
    
    # Read migration file
    migration_file = Path(__file__).parent / "migrations" / "002_enhanced_features.sql"
    
    if not migration_file.exists():
        print(f"Migration file not found: {migration_file}")
        return False
    
    sql = migration_file.read_text(encoding="utf-8")
    
    print(f"Connecting to database...")
    
    try:
        conn = await asyncpg.connect(db_url)
        print("Connected successfully!")
        
        print("Running migration: 002_enhanced_features.sql")
        
        # Execute the migration
        await conn.execute(sql)
        
        print("Migration completed successfully!")
        
        # Verify tables were created
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN (
                'shared_cards', 'support_groups', 'group_reviews', 'group_joins',
                'stories', 'story_supports', 'story_messages',
                'candles', 'candle_messages'
            )
            ORDER BY table_name
        """)
        
        print(f"\nCreated tables:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        # Verify functions were created
        functions = await conn.fetch("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'public'
            AND routine_name IN ('haversine_distance', 'update_updated_at_column')
        """)
        
        print(f"\nCreated functions:")
        for func in functions:
            print(f"  - {func['routine_name']}")
        
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

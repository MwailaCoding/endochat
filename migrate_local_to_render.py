import os
import asyncio
import asyncpg


LOCAL_DATABASE_URL = os.getenv(
    "LOCAL_DATABASE_URL",
    "postgresql://postgres:2030@localhost:5432/endochat",
)

RENDER_DATABASE_URL = os.getenv(
    "RENDER_DATABASE_URL",
    "postgresql://endochat_user:hKA9CFaDGrPZsWNg2vH0MNWrd3ciIGyH@dpg-d6pvvj9j16oc73boc2ig-a.oregon-postgres.render.com/endochat",
)


# Tables that must be created before others (FK / dependency order)
TABLE_ORDER = (
    "support_groups",
    "group_joins",
    "group_reviews",
    "stories",
    "story_supports",
    "story_messages",
    "candles",
    "candle_messages",
)


async def get_public_tables(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
        ORDER BY tablename
        """
    )
    names = [r["tablename"] for r in rows]
    # Sort so dependency order is respected (support_groups before group_joins, etc.)
    order_map = {t: i for i, t in enumerate(TABLE_ORDER)}
    return sorted(names, key=lambda t: (order_map.get(t, len(TABLE_ORDER)), t))


async def table_exists(conn: asyncpg.Connection, table: str) -> bool:
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM pg_tables
        WHERE schemaname = 'public'
          AND tablename = $1
        """,
        table,
    )
    return row is not None


def build_column_type(col: asyncpg.Record) -> str:
    data_type = col["data_type"]
    char_len = col["character_maximum_length"]
    num_prec = col["numeric_precision"]
    num_scale = col["numeric_scale"]
    udt_name = col.get("udt_name")

    if data_type == "character varying" and char_len:
        return f"VARCHAR({char_len})"
    if data_type == "character" and char_len:
        return f"CHAR({char_len})"
    if data_type == "numeric":
        if num_prec and num_scale is not None:
            return f"NUMERIC({num_prec},{num_scale})"
        if num_prec:
            return f"NUMERIC({num_prec})"
        return "NUMERIC"
    if data_type == "timestamp without time zone":
        return "TIMESTAMP"
    if data_type == "timestamp with time zone":
        return "TIMESTAMPTZ"

    # Array types (information_schema reports data_type = 'ARRAY')
    if data_type == "ARRAY":
        # udt_name is usually like '_text', '_int4', etc.
        base = None
        if isinstance(udt_name, str) and udt_name.startswith("_"):
            base = udt_name[1:].upper()

        # Common mappings
        mapping = {
            "TEXT": "TEXT",
            "INT4": "INTEGER",
            "INT8": "BIGINT",
            "UUID": "UUID",
        }
        if base in mapping:
            return f"{mapping[base]}[]"
        if base:
            return f"{base}[]"
        # Fallback if we can't infer: TEXT[]
        return "TEXT[]"

    # Fallback – use the raw type name uppercased
    return data_type.upper()


async def create_table_if_missing(
    src: asyncpg.Connection,
    dst: asyncpg.Connection,
    table: str,
) -> None:
    if await table_exists(dst, table):
        return

    print(f"Creating table {table} on Render...")

    cols = await src.fetch(
        """
        SELECT
            column_name,
            data_type,
            udt_name,
            is_nullable,
            column_default,
            character_maximum_length,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = $1
        ORDER BY ordinal_position
        """,
        table,
    )

    if not cols:
        raise RuntimeError(f"No column metadata found for table {table}")

    col_defs: list[str] = []
    for col in cols:
        col_name = col["column_name"]
        col_type = build_column_type(col)
        nullable = col["is_nullable"] == "YES"
        default = col["column_default"]

        parts = [f'"{col_name}"', col_type]
        if default is not None:
            parts.append(f"DEFAULT {default}")
        if not nullable:
            parts.append("NOT NULL")

        col_defs.append(" ".join(parts))

    pk_rows = await src.fetch(
        """
        SELECT a.attname AS column_name
        FROM   pg_index i
        JOIN   pg_attribute a
          ON   a.attrelid = i.indrelid
         AND   a.attnum = ANY(i.indkey)
        WHERE  i.indrelid = $1::regclass
          AND  i.indisprimary
        """,
        table,
    )

    if pk_rows:
        pk_cols = ", ".join(f'"{r["column_name"]}"' for r in pk_rows)
        col_defs.append(f"PRIMARY KEY ({pk_cols})")

    ddl = f'CREATE TABLE "{table}" (\n  ' + ",\n  ".join(col_defs) + "\n);"
    await dst.execute(ddl)
    print(f"Table {table} created.")


async def copy_table(src: asyncpg.Connection, dst: asyncpg.Connection, table: str) -> None:
    print(f"\n=== Copying table: {table} ===")

    # Ensure table exists on destination
    await create_table_if_missing(src, dst, table)

    # Always start with a clean target table so the script is safely re-runnable
    await dst.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE')

    rows = await src.fetch(f'SELECT * FROM "{table}"')
    if not rows:
        print("No rows to copy (target table truncated).")
        return

    col_names = list(rows[0].keys())
    col_list = ", ".join(f'"{c}"' for c in col_names)
    placeholders = ", ".join(f"${i}" for i in range(1, len(col_names) + 1))
    sql = f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders})'

    values = [tuple(r[c] for c in col_names) for r in rows]
    await dst.executemany(sql, values)

    print(f"Inserted {len(rows)} rows into {table} on Render.")


async def main() -> None:
    print("Connecting to local and Render...")
    src = await asyncpg.connect(LOCAL_DATABASE_URL)
    dst = await asyncpg.connect(RENDER_DATABASE_URL)

    try:
        print("Connected. Discovering tables...")
        tables = await get_public_tables(src)
        print(f"Found tables: {tables}")

        for table in tables:
            await copy_table(src, dst, table)

        print("\n✅ Migration completed: local -> Render.")
    finally:
        await src.close()
        await dst.close()
        print("Connections closed.")


if __name__ == "__main__":
    asyncio.run(main())



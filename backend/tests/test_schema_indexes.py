from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

FOREIGN_KEYS_QUERY = text(
    """
    SELECT con.conrelid::regclass::text AS table_name,
           con.conname AS constraint_name,
           con.conrelid AS table_oid,
           con.conkey::int[] AS column_numbers,
           ARRAY(
               SELECT att.attname::text
               FROM unnest(con.conkey) WITH ORDINALITY AS key(attnum, position)
               JOIN pg_attribute AS att ON att.attrelid = con.conrelid AND att.attnum = key.attnum
               ORDER BY key.position
           ) AS column_names
    FROM pg_constraint AS con
    JOIN pg_namespace AS ns ON ns.oid = con.connamespace
    WHERE con.contype = 'f' AND ns.nspname = current_schema()
    ORDER BY table_name, constraint_name
    """
)

INDEXES_QUERY = text(
    """
    SELECT idx.indrelid AS table_oid, idx.indkey::int[] AS column_numbers
    FROM pg_index AS idx
    JOIN pg_class AS tbl ON tbl.oid = idx.indrelid
    JOIN pg_namespace AS ns ON ns.oid = tbl.relnamespace
    WHERE ns.nspname = current_schema()
    """
)


def _leads_with(index_columns: list[int], fk_columns: list[int]) -> bool:
    # A multi-column FK is served by any index whose leading columns are exactly the FK columns, in any order.
    return sorted(index_columns[: len(fk_columns)]) == sorted(fk_columns)


async def test_every_foreign_key_has_an_index_leading_with_its_columns(db_session: AsyncSession) -> None:
    foreign_keys = (await db_session.execute(FOREIGN_KEYS_QUERY)).all()
    indexes = (await db_session.execute(INDEXES_QUERY)).all()
    assert foreign_keys, "expected the schema to define foreign keys"

    unindexed = [
        f"{fk.table_name}({', '.join(fk.column_names)}) [{fk.constraint_name}]"
        for fk in foreign_keys
        if not any(
            index.table_oid == fk.table_oid and _leads_with(list(index.column_numbers), list(fk.column_numbers))
            for index in indexes
        )
    ]

    assert unindexed == [], "foreign keys without a supporting index:\n" + "\n".join(unindexed)

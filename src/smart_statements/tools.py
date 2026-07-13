import sqlite3

from pyprojroot import here

DB_PATH = here() / "db" / "transactions.db"


def get_schema(table: str | None = None) -> str | None:
    """Return the SQLite schema for a given table name, or for all tables."""
    if not DB_PATH.exists():
        return None

    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.cursor()

        if table:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall()]
        if not tables:
            return None

        schema_parts = []
        for table_name in tables:
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            table_sql = cursor.fetchone()
            if table_sql and table_sql[0]:
                schema_parts.append(table_sql[0])

        return "\n\n".join(schema_parts)


if __name__ == "__main__":
    print(get_schema())

import re
import sqlite3
from pathlib import Path

import pandas as pd
from pyprojroot import here

ROOT_DIR = here()
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
DB_PATH = ROOT_DIR / "db" / "transactions.db"
TABLE_NAME = "transactions"


def sanitize_identifier(value: str) -> str:
    """Create a SQLite-safe identifier from a column name."""
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", value).strip("_")
    if not cleaned:
        cleaned = "data"
    if cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned


def import_csv_to_db(csv_path: Path, connection: sqlite3.Connection) -> None:
    dataframe = pd.read_csv(csv_path)
    dataframe = dataframe.copy()
    dataframe.insert(0, "source_file", csv_path.name)

    for column in dataframe.columns:
        if str(column).lower() == "date":
            dataframe[column] = pd.to_datetime(dataframe[column], errors="coerce")

    columns = [sanitize_identifier(str(column)) for column in dataframe.columns]
    column_definitions = []
    for original_name, sanitized_name in zip(dataframe.columns, columns):
        if str(original_name).lower() == "date":
            column_definitions.append(f'"{sanitized_name}" TIMESTAMP')
        else:
            column_definitions.append(f'"{sanitized_name}" TEXT')

    connection.execute(
        f'CREATE TABLE IF NOT EXISTS "{TABLE_NAME}" ({", ".join(column_definitions)})'
    )

    for row in dataframe.itertuples(index=False, name=None):
        values = []
        for index, value in enumerate(row):
            if pd.isna(value):
                values.append(None)
            elif str(dataframe.columns[index]).lower() == "date" and hasattr(
                value, "to_pydatetime"
            ):
                values.append(value.to_pydatetime().isoformat())
            else:
                values.append(value)

        placeholders = ", ".join(["?"] * len(values))
        column_names = ", ".join(f'"{name}"' for name in columns)
        connection.execute(
            f'INSERT INTO "{TABLE_NAME}" ({column_names}) VALUES ({placeholders})',
            values,
        )

    print(f"[OK] {csv_path.name} -> {TABLE_NAME}")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        DB_PATH.unlink()

    csv_files = sorted(PROCESSED_DIR.glob("*.csv"))
    if not csv_files:
        print("No CSV files found in data/processed.")
        return

    print(f"Found {len(csv_files)} file(s) in {PROCESSED_DIR.relative_to(ROOT_DIR)}")

    with sqlite3.connect(DB_PATH) as connection:
        for csv_path in csv_files:
            import_csv_to_db(csv_path, connection)
        connection.commit()

    print(f"Created database: {DB_PATH.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[2]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
OUTPUT_PATH = ROOT / "knowledge" / "schema_snapshot.json"


def load_db_config() -> dict[str, object]:
    with SECRETS_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    return data["connections"]["postgresql"]


def fetch_rows(cur, sql: str, params: tuple[object, ...] = ()) -> list[dict[str, object]]:
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def main() -> None:
    db = load_db_config()
    schema = str(db.get("schema", "public"))

    conn = psycopg2.connect(
        host=db["host"],
        port=int(db.get("port", 5432)),
        dbname=db["dbname"],
        user=db["user"],
        password=db["password"],
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            tables = fetch_rows(
                cur,
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """,
                (schema,),
            )

            row_counts: dict[str, int] = {}
            columns_by_table: dict[str, list[dict[str, object]]] = {}
            primary_keys_by_table: dict[str, list[str]] = {}

            for table_row in tables:
                table_name = str(table_row["table_name"])
                cur.execute(f'SELECT COUNT(*) AS total FROM "{schema}"."{table_name}"')
                row_counts[table_name] = int(cur.fetchone()["total"])

                columns_by_table[table_name] = fetch_rows(
                    cur,
                    """
                    SELECT
                        column_name,
                        ordinal_position,
                        data_type,
                        udt_name,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_schema = %s
                      AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table_name),
                )

                pk_rows = fetch_rows(
                    cur,
                    """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                     AND tc.table_name = kcu.table_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = %s
                      AND tc.table_name = %s
                    ORDER BY kcu.ordinal_position
                    """,
                    (schema, table_name),
                )
                primary_keys_by_table[table_name] = [
                    str(row["column_name"]) for row in pk_rows
                ]

            foreign_keys = fetch_rows(
                cur,
                """
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    ccu.column_name AS foreign_column_name,
                    tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                ORDER BY tc.table_name, kcu.column_name
                """,
                (schema,),
            )

            payload = {
                "schema": schema,
                "tables": [str(row["table_name"]) for row in tables],
                "row_counts": row_counts,
                "primary_keys": primary_keys_by_table,
                "columns": columns_by_table,
                "foreign_keys": foreign_keys,
            }

        OUTPUT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote schema snapshot to {OUTPUT_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import psycopg2
import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_secrets() -> dict[str, Any]:
    with open(ROOT / ".streamlit" / "secrets.toml", "rb") as fh:
        return tomllib.load(fh)


def load_config() -> dict[str, Any]:
    with open(ROOT / "config" / "config.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_query(config: dict[str, Any], dotted_key: str, schema: str) -> str:
    value: Any = config
    for key in dotted_key.split("."):
        value = value[key]
    if not isinstance(value, str):
        raise TypeError(f"Expected SQL string for {dotted_key}")
    return value.strip().format(schema=schema)


def main() -> int:
    secrets = load_secrets()
    config = load_config()
    conn_info = secrets["connections"]["postgresql"]
    schema = conn_info.get("schema", "public")

    conn = psycopg2.connect(
        host=conn_info["host"],
        port=int(conn_info.get("port", 5432)),
        dbname=conn_info["dbname"],
        user=conn_info["user"],
        password=conn_info["password"],
        connect_timeout=10,
    )
    try:
        checks = {
            "stock.count_filtered": (
                get_query(config, "stock.count_filtered", schema),
                ("ALL", "ALL", "ALL", "ALL", "ALL", "ALL", "", "%%", "%%", "%%", "%%"),
            ),
            "stock.fetch_page": (
                get_query(config, "stock.fetch_page", schema),
                ("ALL", "ALL", "ALL", "ALL", "ALL", "ALL", "", "%%", "%%", "%%", "%%", 50, 0),
            ),
            "sale.count_filtered": (
                get_query(config, "sale.count_filtered", schema),
                ("", "%%", "%%", "%%"),
            ),
            "sale.fetch_page": (
                get_query(config, "sale.fetch_page", schema),
                ("", "%%", "%%", "%%", 50, 0),
            ),
            "purchase.count_filtered": (
                get_query(config, "purchase.count_filtered", schema),
                ("", "%%", "%%", "%%", "%%"),
            ),
            "purchase.fetch_page": (
                get_query(config, "purchase.fetch_page", schema),
                ("", "%%", "%%", "%%", "%%", 50, 0),
            ),
            "booking.count_filtered": (
                get_query(config, "booking.count_filtered", schema),
                ("", "%%", "%%", "%%", "%%"),
            ),
            "booking.fetch_page": (
                get_query(config, "booking.fetch_page", schema),
                ("", "%%", "%%", "%%", "%%", 50, 0),
            ),
            "customer.count_filtered": (
                get_query(config, "customer.count_filtered", schema),
                ("", "%%", "%%", "%%", "%%"),
            ),
            "customer.fetch_page": (
                get_query(config, "customer.fetch_page", schema),
                ("", "%%", "%%", "%%", "%%", 50, 0),
            ),
            "salesman.count_filtered": (
                get_query(config, "salesman.count_filtered", schema),
                ("", "%%", "%%", "%%", "%%", "%%"),
            ),
            "salesman.fetch_page": (
                get_query(config, "salesman.fetch_page", schema),
                ("", "%%", "%%", "%%", "%%", "%%", 50, 0),
            ),
            "stock.fetch_barcode_export_filtered": (
                get_query(config, "stock.fetch_barcode_export_filtered", schema),
                ("ALL", "ALL", "ALL", "ALL", None, None, "ALL", "ALL", "ALL"),
            ),
            "booking.fetch_by_id_for_update": (
                get_query(config, "booking.fetch_by_id_for_update", schema),
                ("BOOK_DOES_NOT_EXIST",),
            ),
            "stock.fetch_by_book_id_for_update": (
                get_query(config, "stock.fetch_by_book_id_for_update", schema),
                ("BOOK_DOES_NOT_EXIST",),
            ),
        }

        results: dict[str, str] = {}
        with conn.cursor() as cur:
            for key, (sql, params) in checks.items():
                cur.execute(sql, params)
                if cur.description:
                    cur.fetchall()
                results[key] = "ok"
            conn.rollback()

        print(json.dumps(results, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

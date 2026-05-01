from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class SqlTemplate:
    template_id: str
    pattern: re.Pattern[str]
    build_sql: Callable[[str], str]
    is_aggregate: bool = False


def _time_filter(question: str, field: str) -> str:
    q = question.lower()
    if "this year" in q:
        return f"{field} >= date_trunc('year', current_date)"
    if "this month" in q:
        return f"{field} >= date_trunc('month', current_date)"
    if "today" in q:
        return f"{field}::date = current_date"
    if "yesterday" in q:
        return f"{field}::date = current_date - interval '1 day'"
    return ""


def _build_stock_count(status: str) -> Callable[[str], str]:
    def _builder(schema: str) -> str:
        return (
            f"SELECT COUNT(*) AS count_{status.lower().replace(' ', '_')} "
            f"FROM {schema}.stock WHERE stk_status = '{status}'"
        )
    return _builder


_TEMPLATES = [
    SqlTemplate(
        "stock_count_in_stock",
        re.compile(r"\b(how many|count|total).*\b(in stock|inventory)\b"),
        _build_stock_count("IN STOCK"),
        is_aggregate=True,
    ),
    SqlTemplate(
        "stock_count_booked",
        re.compile(r"\b(how many|count|total).*\bbooked\b"),
        _build_stock_count("BOOKED"),
        is_aggregate=True,
    ),
    SqlTemplate(
        "stock_count_sold",
        re.compile(r"\b(how many|count|total).*\bsold\b"),
        _build_stock_count("SOLD"),
        is_aggregate=True,
    ),
    SqlTemplate(
        "top_selling_types",
        re.compile(r"\btop\b.*\b(selling|sold)\b.*\b(types|type)\b"),
        lambda s: (
            f"SELECT stk_type, COUNT(*) AS sold_count "
            f"FROM {s}.stock WHERE stk_status = 'SOLD' "
            f"GROUP BY stk_type ORDER BY sold_count DESC LIMIT 5"
        ),
        is_aggregate=True,
    ),
    SqlTemplate(
        "pending_bookings",
        re.compile(r"\b(pending|open|booked)\b.*\bbooking\b|\bshow\b.*\bbooking\b"),
        lambda s: (
            f"SELECT book_id, book_cust_id, book_date, book_status, "
            f"book_price, book_remaining "
            f"FROM {s}.booking WHERE book_status = 'BOOKED' "
            f"ORDER BY book_date DESC LIMIT 100"
        ),
        is_aggregate=False,
    ),
    SqlTemplate(
        "list_customers",
        re.compile(r"\b(list|show|all)\b.*\bcustomers?\b"),
        lambda s: (
            f"SELECT cust_id, cust_name, cust_phone_number, cust_email_address "
            f"FROM {s}.customer ORDER BY cust_name ASC LIMIT 100"
        ),
        is_aggregate=False,
    ),
    SqlTemplate(
        "total_sales_revenue",
        re.compile(r"\b(total|sum)\b.*\b(sales|revenue)\b"),
        lambda s: "",
        is_aggregate=True,
    ),
    SqlTemplate(
        "total_bookings_value",
        re.compile(r"\b(total|sum)\b.*\bbooking(s)?\b.*\b(value|amount|price)\b"),
        lambda s: (
            f"SELECT COALESCE(SUM(book_price), 0) AS total_booking_value "
            f"FROM {s}.booking"
        ),
        is_aggregate=True,
    ),
]


def match_sql_template(question: str, db_schema: str) -> Optional[dict[str, object]]:
    q = question.strip()
    if not q:
        return None
    for tpl in _TEMPLATES:
        if tpl.pattern.search(q.lower()):
            if tpl.template_id == "total_sales_revenue":
                time_clause = _time_filter(q, "sale_sold_date")
                where = f" WHERE {time_clause}" if time_clause else ""
                sql = (
                    f"SELECT COALESCE(SUM(sale_price), 0) AS total_sales_revenue "
                    f"FROM {db_schema}.sale{where}"
                )
            else:
                sql = tpl.build_sql(db_schema)
            return {
                "template_id": tpl.template_id,
                "sql": sql,
                "reasoning": f"Matched template '{tpl.template_id}'.",
                "is_aggregate": tpl.is_aggregate,
            }
    return None

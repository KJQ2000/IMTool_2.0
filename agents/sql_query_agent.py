"""
agents/sql_query_agent.py
──────────────────────────
SQL Query Agent — generates, executes, and retries SQL queries.

Uses RAG on the Bilingual README to inject relevant table schema.
Executes queries via DatabaseManager.execute_readonly_query() (read-only).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
import streamlit as st
from config.prompt_config import render_prompt
from utils.rag import retrieve_relevant_chunks
from utils.logging_utils import get_logger

logger = get_logger(__name__)

_client: OpenAI | None = None
_DATABASE_REFERENCE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "database_reference.md"
_SQL_EXAMPLES_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "sql_query_examples.txt"
_MAX_RETRIES = int(os.getenv("MAX_SQL_RETRIES", "3"))

_KNOWN_TABLES = [
    "booking", "book_payment", "category_pattern_mapping",
    "customer", "purchase", "sale", "salesman", "stock",
]


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        try:
            api_key = st.secrets["openai"]["api_key"]
        except (KeyError, FileNotFoundError):
            api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OpenAI API key not found.")
        _client = OpenAI(api_key=api_key)
    return _client


def _build_system_prompt(schema_context: str, sql_examples: str, db_schema: str) -> str:
    schema_note = (
        f'- ALWAYS prefix every table name with the schema name: '
        f'"{db_schema}.<table_name>" (e.g. {db_schema}.stock, {db_schema}.sale).\n'
        f'- Never reference a table without the "{db_schema}." prefix.'
    )
    return render_prompt(
        "sql_query_agent.system_template",
        values={
            "DB_SCHEMA": db_schema,
            "SCHEMA_CONTEXT": schema_context,
            "SQL_EXAMPLES": sql_examples,
            "SCHEMA_NOTE": schema_note,
        },
    )


def _extract_sql(raw: str) -> str:
    try:
        data = json.loads(raw)
        return data.get("sql", "").strip()
    except json.JSONDecodeError:
        match = re.search(r"(WITH\s+.+?SELECT\s+.+?;|SELECT\s+.+?;)", raw, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""


def _sanitise_sql(sql: str) -> str:
    sql = sql.strip().rstrip(";").strip()
    upper = sql.upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT"]
    for kw in forbidden:
        if re.search(rf"\b{kw}\b", upper):
            raise ValueError(f"Forbidden SQL operation: {kw}")
    return sql


def _apply_schema_prefix(sql: str, db_schema: str) -> str:
    if not db_schema:
        return sql
        
    # Temporarily hide string literals to prevent replacing words inside quotes
    literals = []
    def literal_replacer(match):
        literals.append(match.group(0))
        return f"__LITERAL_{len(literals)-1}__"
        
    sql_no_literals = re.sub(r"'[^']*'", literal_replacer, sql)
    
    for table in _KNOWN_TABLES:
        pattern = rf"(?<![\w.]){re.escape(table)}(?!\w)"
        sql_no_literals = re.sub(pattern, f"{db_schema}.{table}", sql_no_literals, flags=re.IGNORECASE)
        
    for i, lit in enumerate(literals):
        sql_no_literals = sql_no_literals.replace(f"__LITERAL_{i}__", lit)
        
    return sql_no_literals


def run(question: str, chat_history: str = "", previous_feedback: str | None = None) -> dict[str, Any]:
    """Generate and execute a SQL query for the given question.

    Uses the read-only connection from DatabaseManager for safety.
    """
    logger.info("[SQLQueryAgent] Generating SQL for: %s", question)
    t0 = time.perf_counter()

    try:
        model = st.secrets["openai"]["model"]
    except (KeyError, FileNotFoundError):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    logger.debug("[SQLQueryAgent] Model=%s", model)

    try:
        db_schema = st.secrets["connections"]["postgresql"]["schema"]
    except (KeyError, FileNotFoundError):
        db_schema = os.getenv("DB_SCHEMA", "konghin")

    client = _get_client()
    try:
        schema_context = _DATABASE_REFERENCE_PATH.read_text(encoding="utf-8")
    except Exception:
        schema_context = "Schema reference not found."
    sql_examples = retrieve_relevant_chunks(question, _SQL_EXAMPLES_PATH, top_k=5)

    # Import here to avoid circular deps
    from database_manager import DatabaseManager
    db = DatabaseManager.get_instance()

    attempts = 0
    last_error: str | None = None
    generated_sql = ""

    for attempt in range(1, _MAX_RETRIES + 1):
        attempts = attempt
        logger.info("[SQLQueryAgent] Attempt %d/%d", attempt, _MAX_RETRIES)

        user_msg = f"Question: {question}"
        if chat_history:
            user_msg = f"Previous Conversation:\n{chat_history}\n\n{user_msg}"
        if previous_feedback:
            user_msg += f"\n\nAdditional guidance: {previous_feedback}"
        if attempt > 1 and last_error:
            user_msg += f"\n\nPrevious error: {last_error}. Please fix the query."

        messages = [
            {"role": "system", "content": _build_system_prompt(schema_context, sql_examples, db_schema)},
            {"role": "user", "content": user_msg},
        ]

        try:
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=0.1,
                max_tokens=512, response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            generated_sql = _extract_sql(raw)

            if not generated_sql:
                last_error = "LLM did not return valid SQL."
                logger.warning("[SQLQueryAgent] Attempt %d returned no SQL.", attempt)
                continue

            generated_sql = _sanitise_sql(generated_sql)
            generated_sql = _apply_schema_prefix(generated_sql, db_schema)
            logger.info("[SQLQueryAgent] SQL: %s", generated_sql)

            # Execute via read-only connection
            rows, columns = db.execute_readonly_query(generated_sql)

            if rows:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                logger.info(
                    "[SQLQueryAgent] Success attempt=%d rows=%d elapsed_ms=%d",
                    attempts,
                    len(rows),
                    elapsed_ms,
                )
                return {
                    "sql": generated_sql, "results": rows,
                    "columns": columns, "attempts": attempts, "error": None,
                }
            else:
                last_error = "Query returned 0 rows."
                logger.warning("[SQLQueryAgent] Attempt %d returned 0 rows.", attempt)

        except ValueError as exc:
            last_error = str(exc)
            logger.error("[SQLQueryAgent] Safety error: %s", exc)
        except Exception as exc:
            last_error = str(exc)
            logger.error("[SQLQueryAgent] Execution error: %s", exc)

    logger.error(
        "[SQLQueryAgent] Failed after %d attempt(s): %s",
        attempts,
        last_error or "No results after max retries.",
    )
    return {
        "sql": generated_sql, "results": [], "columns": [],
        "attempts": attempts, "error": last_error or "No results after max retries.",
    }

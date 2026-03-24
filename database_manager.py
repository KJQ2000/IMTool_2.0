"""
database_manager.py
───────────────────
ACID-Compliant Database Connection Manager.

Architectural Highlights:
  • Connection pooling via psycopg2.pool.ThreadedConnectionPool
  • Explicit transaction boundaries via context manager
  • autocommit=False by default — every mutation requires explicit commit
  • Separate read-only connection for the AI agent (principle of least privilege)
  • All queries referenced by config.yaml keys (no raw SQL in app code)
  • Comprehensive error handling with full stack trace logging

Usage:
    from database_manager import DatabaseManager
    db = DatabaseManager.get_instance()

    # Atomic transaction (auto-commit or rollback)
    with db.transaction() as cur:
        cur.execute(query, params)

    # Read-only query
    rows = db.fetch_all("stock.fetch_all")
"""

from __future__ import annotations

import math
import re
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool
import streamlit as st

from config_loader import get_query, get_sequence_name, get_prefix
from logging_config import get_logger

logger = get_logger(__name__)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_UNSET = object()
_FORBIDDEN_READONLY_KEYWORDS = {
    "ALTER",
    "CALL",
    "COPY",
    "CREATE",
    "DELETE",
    "DO",
    "DROP",
    "GRANT",
    "INSERT",
    "REINDEX",
    "TRUNCATE",
    "UPDATE",
    "VACUUM",
}


class ConcurrencyConflictError(RuntimeError):
    """Raised when a row changed after the user loaded it."""


class DatabaseManager:
    """Enterprise-grade database manager with ACID compliance.

    Uses Streamlit's ``@st.cache_resource`` to maintain a singleton instance
    across reruns, preventing connection pool exhaustion.
    """

    _instance: DatabaseManager | None = None

    def __init__(self) -> None:
        """Initialize the connection pool from Streamlit secrets."""
        try:
            db_secrets = st.secrets["connections"]["postgresql"]
            self._schema = db_secrets.get("schema", "konghin")
            self._pool_wait_timeout_s = float(db_secrets.get("pool_wait_timeout_s", 5))
            pool_minconn = int(db_secrets.get("minconn", 2))
            pool_maxconn = int(db_secrets.get("maxconn", 20))

            self._pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=pool_minconn,
                maxconn=pool_maxconn,
                host=db_secrets["host"],
                port=int(db_secrets.get("port", 5432)),
                dbname=db_secrets["dbname"],
                user=db_secrets["user"],
                password=db_secrets["password"],
                connect_timeout=10,
            )
            logger.info(
                "Database connection pool established: %s@%s:%s/%s",
                db_secrets["user"],
                db_secrets["host"],
                db_secrets.get("port", 5432),
                db_secrets["dbname"],
            )
        except Exception as e:
            logger.critical("Failed to establish database connection pool.", exc_info=True)
            raise

        # Read-only connection for AI agent (separate credentials)
        self._ro_pool: psycopg2.pool.ThreadedConnectionPool | None = None
        try:
            ro_secrets = st.secrets["connections"]["postgresql_readonly"]
            ro_minconn = int(ro_secrets.get("minconn", 1))
            ro_maxconn = int(ro_secrets.get("maxconn", 10))
            self._ro_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=ro_minconn,
                maxconn=ro_maxconn,
                host=ro_secrets["host"],
                port=int(ro_secrets.get("port", 5432)),
                dbname=ro_secrets["dbname"],
                user=ro_secrets["user"],
                password=ro_secrets["password"],
                connect_timeout=10,
            )
            logger.info("Read-only connection pool established for AI agent.")
        except (KeyError, FileNotFoundError):
            logger.warning(
                "No [connections.postgresql_readonly] found in secrets. "
                "AI agent will use the primary connection pool."
            )
        except Exception as e:
            logger.warning("Failed to create readonly pool: %s", e)

    @staticmethod
    @st.cache_resource(show_spinner=False)
    def get_instance() -> DatabaseManager:
        """Return the singleton DatabaseManager instance (cached across Streamlit reruns)."""
        return DatabaseManager()

    @property
    def schema(self) -> str:
        return self._schema

    @staticmethod
    def _require_identifier(identifier: str, label: str) -> str:
        """Validate a dynamic SQL identifier before interpolation."""
        candidate = str(identifier or "").strip()
        if not _IDENTIFIER_RE.fullmatch(candidate):
            raise ValueError(f"Invalid {label}: {identifier!r}")
        return candidate

    def _qualified_table_name(self, table: str) -> str:
        schema = self._require_identifier(self._schema, "schema")
        table_name = self._require_identifier(table, "table")
        return f"{schema}.{table_name}"

    def _validate_columns(self, columns: list[str]) -> list[str]:
        return [self._require_identifier(column, "column") for column in columns]

    @staticmethod
    def _normalise_readonly_sql(sql: str) -> str:
        """Reject comments and multiple statements before read-only execution."""
        candidate = str(sql or "").strip()
        if not candidate:
            raise ValueError("SQL query is empty.")
        if "--" in candidate or "/*" in candidate or "*/" in candidate:
            raise ValueError("SQL comments are not permitted.")

        trimmed = candidate.rstrip(";").strip()
        if ";" in trimmed:
            raise ValueError("Multiple SQL statements are not permitted.")

        sql_upper = trimmed.upper()
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            raise ValueError("Only SELECT / WITH queries are permitted for the AI agent.")

        for keyword in sorted(_FORBIDDEN_READONLY_KEYWORDS):
            if re.search(rf"\b{keyword}\b", sql_upper):
                raise ValueError(f"Forbidden SQL operation detected: {keyword}")

        return trimmed

    # ──────────────────────────────────────────────────────────
    # Connection Management
    # ──────────────────────────────────────────────────────────

    def _borrow_conn(
        self,
        pool: psycopg2.pool.ThreadedConnectionPool,
        *,
        autocommit: bool,
        pool_label: str,
    ) -> psycopg2.extensions.connection:
        """Borrow a connection, briefly waiting if the pool is saturated."""
        deadline = time.perf_counter() + self._pool_wait_timeout_s
        while True:
            try:
                conn = pool.getconn()
                conn.autocommit = autocommit
                return conn
            except psycopg2.pool.PoolError:
                if time.perf_counter() >= deadline:
                    raise RuntimeError(
                        f"{pool_label} connection pool exhausted after waiting "
                        f"{self._pool_wait_timeout_s:.1f}s."
                    )
                time.sleep(0.05)

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Get a connection from the pool with autocommit disabled."""
        return self._borrow_conn(self._pool, autocommit=False, pool_label="Primary")

    def _put_conn(self, conn: psycopg2.extensions.connection) -> None:
        """Return a connection to the pool."""
        self._pool.putconn(conn)

    def get_readonly_connection(self) -> psycopg2.extensions.connection:
        """Get a read-only connection for the AI agent.

        Falls back to the primary pool if no readonly pool is configured.
        The connection has autocommit=True since it's read-only.
        """
        pool = self._ro_pool or self._pool
        label = "Readonly" if self._ro_pool else "Primary"
        return self._borrow_conn(pool, autocommit=True, pool_label=label)

    def return_readonly_connection(self, conn: psycopg2.extensions.connection) -> None:
        """Return a read-only connection to its pool."""
        pool = self._ro_pool or self._pool
        pool.putconn(conn)

    # ──────────────────────────────────────────────────────────
    # Transaction Context Manager (Core ACID Enforcement)
    # ──────────────────────────────────────────────────────────

    @contextmanager
    def transaction(self) -> Generator[psycopg2.extensions.cursor, None, None]:
        """Context manager that enforces strict ACID transaction boundaries.

        Mathematical guarantee:
            Transaction State =
                Committed   if ∀ Query_i returns Success
                Rolled Back if ∃ Query_i returns Exception

        Usage:
            with db.transaction() as cur:
                cur.execute(queries['insert_sale'], (t_id, code, qty))
                cur.execute(queries['decrement_stock'], (qty, code))
            # Auto-committed here if no exceptions

        On exception:
            # Auto-rolled-back, full traceback logged at ERROR level
        """
        conn = self._get_conn()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        t0 = time.perf_counter()
        try:
            logger.debug("Transaction started.")
            yield cursor
            conn.commit()
            logger.info(
                "Transaction committed successfully in %d ms.",
                int((time.perf_counter() - t0) * 1000),
            )
        except psycopg2.IntegrityError as e:
            conn.rollback()
            logger.error(
                "Transaction rolled back due to integrity violation: %s",
                e.pgerror,
                exc_info=True,
            )
            raise
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(
                "Transaction rolled back due to database error: %s - %s",
                e.pgcode,
                e.pgerror,
                exc_info=True,
            )
            raise
        except Exception as e:
            conn.rollback()
            logger.error(
                "Transaction rolled back due to unexpected error.",
                exc_info=True,
            )
            raise
        finally:
            cursor.close()
            self._put_conn(conn)

    # ──────────────────────────────────────────────────────────
    # Query Execution Helpers
    # ──────────────────────────────────────────────────────────

    def fetch_all(
        self, query_key: str, params: tuple | None = None
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return all rows as list of dicts.

        Parameters
        ----------
        query_key:
            Dot-separated config.yaml key, e.g. "stock.fetch_all".
        params:
            Optional parameterized values.
        """
        sql = get_query(query_key, schema=self._schema)
        conn = self._get_conn()
        t0 = time.perf_counter()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
                conn.commit()  # Release any implicit locks from SELECT
                results = [dict(row) for row in rows]
                logger.debug(
                    "fetch_all success key=%s rows=%d duration_ms=%d",
                    query_key,
                    len(results),
                    int((time.perf_counter() - t0) * 1000),
                )
                return results
        except Exception as e:
            conn.rollback()
            logger.error("fetch_all failed for '%s': %s", query_key, e, exc_info=True)
            return []
        finally:
            self._put_conn(conn)

    def fetch_one(
        self, query_key: str, params: tuple | None = None
    ) -> dict[str, Any] | None:
        """Execute a SELECT query and return the first row as a dict."""
        sql = get_query(query_key, schema=self._schema)
        conn = self._get_conn()
        t0 = time.perf_counter()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                conn.commit()
                result = dict(row) if row else None
                logger.debug(
                    "fetch_one success key=%s found=%s duration_ms=%d",
                    query_key,
                    bool(result),
                    int((time.perf_counter() - t0) * 1000),
                )
                return result
        except Exception as e:
            conn.rollback()
            logger.error("fetch_one failed for '%s': %s", query_key, e, exc_info=True)
            return None
        finally:
            self._put_conn(conn)

    def fetch_scalar(
        self, query_key: str, params: tuple | None = None
    ) -> Any:
        """Execute a query and return the first column of the first row."""
        sql = get_query(query_key, schema=self._schema)
        conn = self._get_conn()
        t0 = time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                conn.commit()
                result = row[0] if row else None
                logger.debug(
                    "fetch_scalar success key=%s has_value=%s duration_ms=%d",
                    query_key,
                    result is not None,
                    int((time.perf_counter() - t0) * 1000),
                )
                return result
        except Exception as e:
            conn.rollback()
            logger.error("fetch_scalar failed for '%s': %s", query_key, e, exc_info=True)
            return None
        finally:
            self._put_conn(conn)

    # ──────────────────────────────────────────────────────────
    # Sequence Operations
    # ──────────────────────────────────────────────────────────

    def get_nextval(self, table: str) -> int | None:
        """Get the next value from a sequence for the given table."""
        schema = self._require_identifier(self._schema, "schema")
        seq_name = self._require_identifier(get_sequence_name(table), "sequence")
        sql = f"SELECT nextval('{schema}.{seq_name}')"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                result = cur.fetchone()[0]
                conn.commit()
                logger.info("Next value of sequence %s: %s", seq_name, result)
                return result
        except Exception as e:
            conn.rollback()
            logger.error("get_nextval failed for %s: %s", seq_name, e, exc_info=True)
            return None
        finally:
            self._put_conn(conn)

    def get_currval(self, table: str, conn=None, cur=None) -> int | None:
        """Get the current value of a sequence (must follow a nextval call in same session).

        If called within a transaction context, pass the cursor to use the same connection.
        """
        schema = self._require_identifier(self._schema, "schema")
        seq_name = self._require_identifier(get_sequence_name(table), "sequence")
        sql = f"SELECT currval('{schema}.{seq_name}')"
        if cur is not None:
            try:
                cur.execute(sql)
                row = cur.fetchone()
                # RealDictCursor returns dicts — handle both dict and tuple
                result = row["currval"] if isinstance(row, dict) else row[0]
                logger.info("Current value of sequence %s: %s", seq_name, result)
                return result
            except Exception as e:
                logger.error("get_currval failed for %s: %s", seq_name, e, exc_info=True)
                return None
        else:
            conn_local = self._get_conn()
            try:
                with conn_local.cursor() as c:
                    c.execute(sql)
                    result = c.fetchone()[0]
                    conn_local.commit()
                    return result
            except Exception as e:
                conn_local.rollback()
                logger.error("get_currval failed: %s", e, exc_info=True)
                return None
            finally:
                self._put_conn(conn_local)

    def generate_pk(self, table: str, cur=None) -> str:
        """Generate a primary key for the given table.

        Format: PREFIX_SEQVAL (e.g., STK_100001, SALE_200005)
        If a cursor is provided, nextval is called within the same transaction.
        """
        prefix = get_prefix(table)
        schema = self._require_identifier(self._schema, "schema")
        seq_name = self._require_identifier(get_sequence_name(table), "sequence")
        sql = f"SELECT nextval('{schema}.{seq_name}')"

        if cur is not None:
            cur.execute(sql)
            row = cur.fetchone()
            # RealDictCursor returns dicts — handle both dict and tuple
            seq = row["nextval"] if isinstance(row, dict) else row[0]
        else:
            seq = self.get_nextval(table)

        if seq is None:
            raise RuntimeError(f"Failed to generate PK: nextval returned None for {table}")

        pk = f"{prefix}_{seq}"
        logger.info("Generated PK for %s: %s", table, pk)
        return pk

    # ──────────────────────────────────────────────────────────
    # Dynamic INSERT / UPDATE Builders
    # ──────────────────────────────────────────────────────────

    def build_insert(
        self, table: str, columns: list[str], values: list[Any], cur
    ) -> str:
        """Build and execute a parameterized INSERT with auto-generated PK.

        This is used for dynamic inserts where columns are determined at runtime
        (e.g., from form submissions or batch imports).

        Returns the generated primary key.
        """
        pk = self.generate_pk(table, cur=cur)
        prefix = get_prefix(table).lower()
        id_col = self._require_identifier(f"{prefix}_id", "column")

        # Prepend PK column
        all_columns = [id_col] + self._validate_columns(columns)
        all_values = [pk] + values

        # Filter out empty-string values
        filtered = [
            (col, val) for col, val in zip(all_columns, all_values) if val != ""
        ]
        if not filtered:
            raise ValueError("No non-empty values to insert.")

        cols, vals = zip(*filtered)
        col_str = ", ".join(cols)
        placeholder_str = ", ".join(["%s"] * len(vals))

        sql = f"INSERT INTO {self._qualified_table_name(table)} ({col_str}) VALUES ({placeholder_str})"
        cur.execute(sql, list(vals))
        logger.info("Inserted into %s.%s: PK=%s", self._schema, table, pk)
        return pk

    def insert_row(
        self, table: str, columns: list[str], values: list[Any], cur
    ) -> None:
        """Insert a row with validated identifiers and parameterised values."""
        safe_columns = self._validate_columns(columns)
        placeholders = ", ".join(["%s"] * len(values))
        sql = (
            f"INSERT INTO {self._qualified_table_name(table)} "
            f"({', '.join(safe_columns)}) VALUES ({placeholders})"
        )
        cur.execute(sql, values)

    def build_update(
        self,
        table: str,
        columns: list[str],
        values: list[Any],
        where_id: str,
        cur,
        *,
        expected_last_update: Any = _UNSET,
    ) -> int:
        """Build and execute a parameterized UPDATE with auto-timestamp for last_update.

        Parameters
        ----------
        table: Target table name.
        columns: Column names to update.
        values: Corresponding values.
        where_id: The primary key value for the WHERE clause.
        cur: Active cursor within a transaction.
        expected_last_update:
            Original last-update value seen by the caller. When provided, the
            update only succeeds if the row is unchanged since it was loaded.
        """
        prefix = get_prefix(table).lower()
        id_col = self._require_identifier(f"{prefix}_id", "column")
        last_update_col = self._require_identifier(f"{prefix}_last_update", "column")

        # Add last_update timestamp
        columns = self._validate_columns(list(columns)) + [last_update_col]
        values = list(values) + [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]

        # Handle None/empty values
        set_parts = []
        exec_values = []
        for col, val in zip(columns, values):
            if val in ("None", "") or val is None:
                set_parts.append(f"{col} = NULL")
            else:
                set_parts.append(f"{col} = %s")
                exec_values.append(val)

        set_clause = ", ".join(set_parts)
        sql = f"UPDATE {self._qualified_table_name(table)} SET {set_clause} WHERE {id_col} = %s"
        exec_values.append(where_id)
        use_concurrency_check = expected_last_update is not _UNSET
        if use_concurrency_check:
            sql += f" AND {last_update_col} IS NOT DISTINCT FROM %s"
            exec_values.append(expected_last_update)

        cur.execute(sql, exec_values)
        if use_concurrency_check and cur.rowcount == 0:
            raise ConcurrencyConflictError(
                f"{table.upper()} {where_id} was modified by another user. "
                "Reload the latest data before saving again."
            )
        logger.info("Updated %s.%s WHERE %s = %s", self._schema, table, id_col, where_id)
        return cur.rowcount

    def build_delete(self, table: str, where_id: str, cur) -> None:
        """Execute a parameterized DELETE by primary key."""
        prefix = get_prefix(table).lower()
        id_col = self._require_identifier(f"{prefix}_id", "column")
        sql = f"DELETE FROM {self._qualified_table_name(table)} WHERE {id_col} = %s"
        cur.execute(sql, (where_id,))
        logger.info("Deleted from %s.%s WHERE %s = %s", self._schema, table, id_col, where_id)

    # ──────────────────────────────────────────────────────────
    # Read-only Query Execution (for AI Agent)
    # ──────────────────────────────────────────────────────────

    def execute_readonly_query(
        self, sql: str, params: tuple | None = None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Execute a read-only query for the AI agent.

        SECURITY: Only SELECT/WITH queries are permitted.
        Uses the read-only connection pool.

        Returns
        -------
        (rows, columns):
            rows as list of dicts, column names as list of strings.

        Raises
        ------
        ValueError: If the query is not a SELECT statement.
        """
        safe_sql = self._normalise_readonly_sql(sql)

        conn = self.get_readonly_connection()
        t0 = time.perf_counter()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(safe_sql, params)
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows_as_dicts = [dict(row) for row in rows]
                logger.info(
                    "AI readonly query returned %d rows (%d columns) in %d ms.",
                    len(rows_as_dicts),
                    len(columns),
                    int((time.perf_counter() - t0) * 1000),
                )
                return rows_as_dicts, columns
        except Exception as e:
            logger.error("AI readonly query failed: %s", e, exc_info=True)
            raise
        finally:
            self.return_readonly_connection(conn)

    # ──────────────────────────────────────────────────────────
    # Barcode Generation
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def generate_barcode_string(gold_cost, labor_cost, stk_id_num: str) -> str:
        """Generate a barcode string using the legacy encoding algorithm.

        Example: JE9100981154 for STK_101154 with gold_cost=590.13, labor=98

        The barcode format: PREFIX + GP_CODE + LABOR_CODE + STK_SUFFIX
        - PREFIX: chr(64 + first_2_digits_of_stk_id_num) → e.g. 10 → 'J'
        - GP_CODE: first digit of ceil(gold_cost) → letter + remaining digits
                   e.g. 591 → chr(64+5)+'91' = 'E91'
        - LABOR_CODE: zero-padded to 4 digits (plain, no encryption)
                   e.g. 98 → '0098'
        - STK_SUFFIX: last 4 digits of the stk_id number
                   e.g. 101154 → '1154'

        This is designed for future barcode scanner integration.
        The stk_id can be reconstructed: PREFIX decodes the first 2 digits,
        SUFFIX provides the last 4, giving the full stk_id number.
        """
        # ── Gold Cost Encryption ──
        # Round up (ceil), then first digit → letter, remaining as-is
        gp = int(math.ceil(float(gold_cost)))
        gp_str = str(gp)
        gp_first_digit = int(gp_str[0])
        gp_code = chr(64 + gp_first_digit) + gp_str[1:]

        # ── Labor Code ── (plain zero-padded to 4 digits)
        labor = int(round(float(labor_cost)))
        labor_code = f"{labor:04}"

        # ── Prefix & Suffix from stk_id number ──
        stk_num = str(stk_id_num)
        prefix = chr(64 + int(stk_num[:2]) % 26)
        suffix = stk_num[-4:]

        return f"{prefix}{gp_code}{labor_code}{suffix}"

    # ──────────────────────────────────────────────────────────
    # Connection Health Check
    # ──────────────────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Return True if the database is reachable."""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            logger.warning("Database connection test failed: %s", e)
            return False
        finally:
            self._put_conn(conn)

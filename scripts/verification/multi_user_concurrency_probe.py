from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import tomllib
from pathlib import Path
from typing import Any

import bcrypt
import psycopg2
import psycopg2.extras
import psycopg2.pool
import yaml


ROOT = Path(__file__).resolve().parents[2]
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"
CONFIG_PATH = ROOT / "config" / "config.yaml"


def load_secrets() -> dict[str, Any]:
    with open(SECRETS_PATH, "rb") as fh:
        return tomllib.load(fh)


def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def get_query(config: dict[str, Any], dotted_key: str, schema: str) -> str:
    value: Any = config
    for key in dotted_key.split("."):
        value = value[key]
    if not isinstance(value, str):
        raise TypeError(f"Config entry {dotted_key!r} is not a string query.")
    return value.strip().format(schema=schema)


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * p)))
    return ordered[index]


def latency_summary(latencies_ms: list[float]) -> dict[str, float]:
    if not latencies_ms:
        return {
            "avg_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "p50_ms": 0.0,
            "p95_ms": 0.0,
        }
    return {
        "avg_ms": round(statistics.fmean(latencies_ms), 2),
        "min_ms": round(min(latencies_ms), 2),
        "max_ms": round(max(latencies_ms), 2),
        "p50_ms": round(percentile(latencies_ms, 0.50), 2),
        "p95_ms": round(percentile(latencies_ms, 0.95), 2),
    }


class AppMirrorPool:
    def __init__(self, conn_info: dict[str, Any]) -> None:
        self.pool_wait_timeout_s = float(conn_info.get("pool_wait_timeout_s", 5))
        self.minconn = int(conn_info.get("minconn", 2))
        self.maxconn = int(conn_info.get("maxconn", 20))
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=self.minconn,
            maxconn=self.maxconn,
            host=conn_info["host"],
            port=int(conn_info.get("port", 5432)),
            dbname=conn_info["dbname"],
            user=conn_info["user"],
            password=conn_info["password"],
            connect_timeout=10,
        )

    def acquire(self) -> psycopg2.extensions.connection:
        deadline = time.perf_counter() + self.pool_wait_timeout_s
        while True:
            try:
                conn = self.pool.getconn()
                conn.autocommit = False
                return conn
            except psycopg2.pool.PoolError:
                if time.perf_counter() >= deadline:
                    raise RuntimeError(
                        f"Primary connection pool exhausted after waiting "
                        f"{self.pool_wait_timeout_s:.1f}s."
                    )
                time.sleep(0.05)

    def release(self, conn: psycopg2.extensions.connection) -> None:
        self.pool.putconn(conn)

    def fetch_one(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> dict[str, Any] | None:
        conn = self.acquire()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    def fetch_all(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        conn = self.acquire()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
            conn.commit()
            return [dict(row) for row in rows]
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    def fetch_scalar(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> Any:
        conn = self.acquire()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self.release(conn)

    def close(self) -> None:
        self.pool.closeall()


def run_parallel(
    concurrency: int,
    operation,
    *,
    iterations_per_thread: int = 1,
) -> dict[str, Any]:
    barrier = threading.Barrier(concurrency)
    lock = threading.Lock()
    latencies_ms: list[float] = []
    errors: list[str] = []
    extra: list[Any] = []
    started_at = time.perf_counter()

    def worker(thread_idx: int) -> None:
        try:
            barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            with lock:
                errors.append("barrier_broken")
            return

        for _ in range(iterations_per_thread):
            t0 = time.perf_counter()
            try:
                result = operation(thread_idx)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                with lock:
                    latencies_ms.append(elapsed_ms)
                    if result is not None:
                        extra.append(result)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    wall_ms = (time.perf_counter() - started_at) * 1000
    return {
        "concurrency": concurrency,
        "iterations_per_thread": iterations_per_thread,
        "requests": concurrency * iterations_per_thread,
        "successes": len(latencies_ms),
        "errors": len(errors),
        "error_samples": errors[:5],
        "wall_ms": round(wall_ms, 2),
        "latency": latency_summary(latencies_ms),
        "result_samples": extra[:5],
    }


def collect_dataset_snapshot(pool: AppMirrorPool, schema: str) -> dict[str, Any]:
    tables = ["users", "customer", "stock", "sale", "booking", "purchase"]
    snapshot = {}
    for table in tables:
        sql = f"SELECT COUNT(*) FROM {schema}.{table}"
        snapshot[table] = int(pool.fetch_scalar(sql))
    snapshot["stock_in_stock"] = int(
        pool.fetch_scalar(f"SELECT COUNT(*) FROM {schema}.stock WHERE stk_status = %s", ("IN STOCK",))
    )
    snapshot["bcrypt_users"] = int(
        pool.fetch_scalar(
            f"SELECT COUNT(*) FROM {schema}.users "
            "WHERE usr_password LIKE '$2a$%' OR usr_password LIKE '$2b$%' OR usr_password LIKE '$2y$%'"
        )
    )
    return snapshot


def choose_login_user(pool: AppMirrorPool, schema: str) -> dict[str, Any] | None:
    sql = (
        f"SELECT usr_id, usr_email, usr_password FROM {schema}.users "
        "WHERE usr_password LIKE '$2a$%' OR usr_password LIKE '$2b$%' OR usr_password LIKE '$2y$%' "
        "ORDER BY usr_id LIMIT 1"
    )
    user = pool.fetch_one(sql)
    if user:
        user["password_mode"] = "bcrypt"
        return user

    fallback_sql = f"SELECT usr_id, usr_email, usr_password FROM {schema}.users ORDER BY usr_id LIMIT 1"
    user = pool.fetch_one(fallback_sql)
    if user:
        user["password_mode"] = "plaintext_or_unknown"
    return user


def choose_customer_row(pool: AppMirrorPool, schema: str) -> dict[str, Any] | None:
    return pool.fetch_one(
        f"SELECT cust_id, cust_address, cust_last_update FROM {schema}.customer ORDER BY cust_id LIMIT 1"
    )


def auth_like_login_test(
    pool: AppMirrorPool,
    schema: str,
    email: str,
    config: dict[str, Any],
    concurrency_levels: list[int],
) -> list[dict[str, Any]]:
    sql = get_query(config, "auth.verify_credentials", schema)

    def op(_: int) -> dict[str, Any]:
        row = pool.fetch_one(sql, (email,))
        if not row:
            raise RuntimeError("login_user_missing")
        stored_password = str(row.get("usr_password", ""))
        if stored_password.startswith(("$2a$", "$2b$", "$2y$")):
            bcrypt.checkpw(b"not-the-real-password", stored_password.encode("utf-8"))
        else:
            _ = stored_password == "not-the-real-password"
        return {"email_found": bool(row)}

    return [run_parallel(level, op, iterations_per_thread=2) for level in concurrency_levels]


def fetch_page_load_test(
    pool: AppMirrorPool,
    schema: str,
    config: dict[str, Any],
    concurrency_levels: list[int],
) -> list[dict[str, Any]]:
    sql = get_query(config, "stock.fetch_page", schema)
    params = (
        "ALL",
        "ALL",
        "ALL",
        "ALL",
        "ALL",
        "ALL",
        "",
        "%%",
        "%%",
        "%%",
        "%%",
        50,
        0,
    )

    def op(_: int) -> dict[str, Any]:
        rows = pool.fetch_all(sql, params)
        return {"rows": len(rows)}

    return [run_parallel(level, op, iterations_per_thread=1) for level in concurrency_levels]


def pool_exhaustion_test(
    pool: AppMirrorPool,
    concurrency_levels: list[int],
    hold_seconds: float,
) -> list[dict[str, Any]]:
    def make_op():
        def op(_: int) -> None:
            conn = pool.acquire()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_sleep(%s)", (hold_seconds,))
                conn.commit()
                return None
            except Exception:
                conn.rollback()
                raise
            finally:
                pool.release(conn)

        return op

    return [run_parallel(level, make_op()) for level in concurrency_levels]


def lost_update_test(pool: AppMirrorPool, schema: str, customer_row: dict[str, Any]) -> dict[str, Any]:
    customer_id = customer_row["cust_id"]
    original_address = customer_row.get("cust_address")
    original_last_update = customer_row.get("cust_last_update")
    original_value = "" if original_address is None else str(original_address)
    update_sql = (
        f"UPDATE {schema}.customer "
        "SET cust_address = %s, cust_last_update = CURRENT_TIMESTAMP "
        "WHERE cust_id = %s AND cust_last_update IS NOT DISTINCT FROM %s"
    )
    restore_sql = (
        f"UPDATE {schema}.customer "
        "SET cust_address = %s, cust_last_update = %s "
        "WHERE cust_id = %s"
    )

    token_a = f"{original_value} [CONCURRENCY_TEST_A]"
    token_b = f"{original_value} [CONCURRENCY_TEST_B]"
    stage_event = threading.Event()
    outcomes: dict[str, Any] = {}
    errors: list[str] = []
    lock = threading.Lock()

    def writer_a() -> None:
        conn = pool.acquire()
        started = time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute(update_sql, (token_a, customer_id, original_last_update))
                if cur.rowcount == 0:
                    raise RuntimeError("writer_a_conflict")
                stage_event.set()
                time.sleep(1.5)
            conn.commit()
            with lock:
                outcomes["writer_a_ms"] = round((time.perf_counter() - started) * 1000, 2)
        except Exception as exc:
            conn.rollback()
            with lock:
                errors.append(f"writer_a: {exc}")
        finally:
            pool.release(conn)

    def writer_b() -> None:
        if not stage_event.wait(timeout=10):
            with lock:
                errors.append("writer_b: timeout_waiting_for_writer_a")
            return

        conn = pool.acquire()
        started = time.perf_counter()
        try:
            with conn.cursor() as cur:
                cur.execute(update_sql, (token_b, customer_id, original_last_update))
                if cur.rowcount == 0:
                    conn.rollback()
                    with lock:
                        outcomes["writer_b_conflict"] = True
                    return
            conn.commit()
            with lock:
                outcomes["writer_b_conflict"] = False
                outcomes["writer_b_ms"] = round((time.perf_counter() - started) * 1000, 2)
        except Exception as exc:
            conn.rollback()
            with lock:
                errors.append(f"writer_b: {exc}")
        finally:
            pool.release(conn)

    thread_a = threading.Thread(target=writer_a, daemon=True)
    thread_b = threading.Thread(target=writer_b, daemon=True)
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    final_row = pool.fetch_one(
        f"SELECT cust_id, cust_address, cust_last_update FROM {schema}.customer WHERE cust_id = %s",
        (customer_id,),
    )
    final_value = final_row.get("cust_address") if final_row else None

    restore_conn = pool.acquire()
    restored = False
    try:
        with restore_conn.cursor() as cur:
            cur.execute(restore_sql, (original_address, original_last_update, customer_id))
        restore_conn.commit()
        restored = True
    except Exception as exc:
        restore_conn.rollback()
        errors.append(f"restore: {exc}")
    finally:
        pool.release(restore_conn)

    return {
        "customer_id": customer_id,
        "token_a_committed": final_value == token_a,
        "token_b_committed": final_value == token_b,
        "final_value": final_value,
        "restored_original_value": restored,
        "errors": errors,
        **outcomes,
    }


def build_report() -> dict[str, Any]:
    secrets = load_secrets()
    config = load_config()
    conn_info = secrets["connections"]["postgresql"]
    schema = conn_info.get("schema", "public")
    pool = AppMirrorPool(conn_info)
    concurrency_levels = sorted({1, 5, 10, pool.maxconn, pool.maxconn + 5})
    try:
        dataset = collect_dataset_snapshot(pool, schema)
        login_user = choose_login_user(pool, schema)
        customer_row = choose_customer_row(pool, schema)

        report: dict[str, Any] = {
            "tested_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "database": {
                "host": conn_info["host"],
                "port": int(conn_info.get("port", 5432)),
                "dbname": conn_info["dbname"],
                "schema": schema,
                "pool_minconn": pool.minconn,
                "pool_maxconn": pool.maxconn,
                "pool_wait_timeout_s": pool.pool_wait_timeout_s,
            },
            "dataset_snapshot": dataset,
            "auth_login_probe": None,
            "stock_page_probe": None,
            "pool_exhaustion_probe": None,
            "lost_update_probe": None,
        }

        if login_user:
            report["auth_login_probe"] = {
                "selected_user": {
                    "usr_id": login_user["usr_id"],
                    "usr_email": login_user["usr_email"],
                    "password_mode": login_user["password_mode"],
                },
                "runs": auth_like_login_test(
                    pool,
                    schema,
                    str(login_user["usr_email"]),
                    config,
                    concurrency_levels,
                ),
            }
        else:
            report["auth_login_probe"] = {"skipped": "no_users_found"}

        report["stock_page_probe"] = {
            "runs": fetch_page_load_test(pool, schema, config, concurrency_levels),
        }

        report["pool_exhaustion_probe"] = {
            "hold_seconds": 2.0,
            "runs": pool_exhaustion_test(pool, sorted({5, 10, pool.maxconn, pool.maxconn + 5}), 2.0),
        }

        if customer_row:
            report["lost_update_probe"] = lost_update_test(pool, schema, customer_row)
        else:
            report["lost_update_probe"] = {"skipped": "no_customer_rows_found"}

        return report
    finally:
        pool.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe IMTool multi-user behavior.")
    parser.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to save the JSON report.",
    )
    args = parser.parse_args()

    report = build_report()
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

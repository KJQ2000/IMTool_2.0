# Multi-User Assessment and Solution Plan

Date: 2026-03-24

Raw probe output: `docs/audit/05_multi_user_test_results.json`

## Executive Answer

- Light usage with a few users should be fine on the current codebase.
- Around 10 simultaneous database-heavy actions, the system still works on the current dataset, but response time rises noticeably.
- Above 10 overlapping database actions, the app can fail because the primary PostgreSQL pool is capped at 10 connections (`database_manager.py:80`).
- Concurrent edits to the same record are **not conflict-safe** in the generic CRUD flows. The later save can overwrite the earlier save without warning because updates only filter by primary key (`utils/editable_table.py:112`, `utils/editable_table.py:166`, `database_manager.py:492`, `database_manager.py:521`).
- App-level caching is minimal. The code caches the `DatabaseManager` singleton (`database_manager.py:123`), config loading (`config_loader.py:33`), the AI page session cache (`pages/11_🤖_Agentic_Intelligence.py:25`), and one custom stock table query (`pages/12_🧩_Custom_Stock_Table.py:68`). The main CRUD pages are not data-cached.
- Multi-user multi-tasking is only partially supported today:
  - Different users working on different rows will usually be fine while concurrent demand stays within the pool and the dataset stays modest.
  - Different users editing the same row can silently overwrite each other.
  - Sales creation is safer than the generic edit path because it locks the stock row first and checks the current status before writing (`config.yaml:68`, `pages/04_💰_Sales.py:294`, `pages/04_💰_Sales.py:310`).

## What Was Tested

Tests were run against the current local PostgreSQL database and mirrored the current app architecture:

- PostgreSQL `ThreadedConnectionPool(minconn=2, maxconn=10)`
- Real `auth.verify_credentials` query from `config.yaml`
- Real `stock.fetch_all` query from `config.yaml`
- Controlled concurrent update test on the same customer row, with the original value restored after the test

Dataset snapshot at test time:

- Users: 1
- Customers: 6
- Stock: 752
- In-stock items: 712
- Sales: 19
- Bookings: 26
- Purchases: 1033

## Measured Results

### 1. Login-like concurrency

- At 10 concurrent login-like requests, all 20 requests succeeded, with average latency about 174 ms.
- At 15 concurrent login-like requests, only 23 of 30 requests succeeded and 7 failed with `connection pool exhausted`.
- Important note: the current DB snapshot has 0 bcrypt users, so current login cost is lower than it should be in a hardened production setup.

### 2. Heavy page read concurrency (`stock.fetch_all`)

- At 1 concurrent fetch, the full stock load took about 11 ms.
- At 5 concurrent fetches, average latency rose to about 132 ms.
- At 10 concurrent fetches, average latency rose to about 356 ms.
- At 15 concurrent fetches, only 10 of 15 succeeded and 5 failed with `connection pool exhausted`.

This matters because several pages still fetch whole tables directly:

- Stocks view: `pages/03_📦_Stocks.py:44`
- Sales view: `pages/04_💰_Sales.py:48`
- Bookings view: `pages/06_📖_Bookings.py:52`
- Customers view: `pages/07_👥_Customers.py:22`
- Purchases view: `pages/05_📋_Purchases.py:23`
- Salesmen view: `pages/08_🤝_Salesmen.py:22`

The stock base query itself is unbounded: `config.yaml:60`.

### 3. Hard connection ceiling

- A controlled pool-hold test with 15 concurrent requests produced 10 successes and 5 failures.
- This confirms the current `maxconn=10` setting behaves as a real concurrency ceiling, not just a theoretical one.

### 4. Same-row amendment correctness

- Two concurrent updates were run against the same customer row.
- Both transactions committed successfully.
- Final database value matched the second writer's token, not the first writer's token.
- The original row value was restored after the test.

Conclusion: current generic CRUD updates are serialized by PostgreSQL row locking, but there is no conflict detection. The result is "last write wins," not "user warned of concurrent change."

## Bottlenecks Mapped to Code

### B-01. Connection pool limit is too low for overlap spikes

- Primary pool is `maxconn=10`: `database_manager.py:80`
- Read-only AI pool is `maxconn=5`: `database_manager.py:105`

Impact:

- More than 10 overlapping DB operations can throw errors.
- This becomes more likely when queries get slower as the data grows.

### B-02. Full-table reads on rerun-heavy Streamlit pages

- Stock fetch-all query: `config.yaml:60`
- Full-table usage in CRUD pages:
  - `pages/03_📦_Stocks.py:44`
  - `pages/04_💰_Sales.py:48`
  - `pages/05_📋_Purchases.py:23`
  - `pages/06_📖_Bookings.py:52`
  - `pages/07_👥_Customers.py:22`
  - `pages/08_🤝_Salesmen.py:22`

Impact:

- More concurrent users means more repeated full loads.
- Latency and connection occupancy rise together.

### B-03. Client-side filtering/editing

- Filtering starts from `filtered_df = df.copy()`: `utils/editable_table.py:88`
- Filtering is done in pandas/string contains logic: `utils/editable_table.py:89`
- The filtered dataframe is then fully rendered via `st.data_editor`: `utils/editable_table.py:100`

Impact:

- CPU and memory cost grows inside the Streamlit process.
- This scales poorly compared with server-side SQL filtering and pagination.

### B-04. No optimistic concurrency protection on generic edits

- Generic save entrypoint: `utils/editable_table.py:112`
- Generic save loop calls `db.build_update(...)`: `utils/editable_table.py:166`
- Update SQL only matches by primary key: `database_manager.py:521`

Impact:

- If user A and user B edit the same row, user B can overwrite user A without warning.
- The system "captures" both transactions technically, but not correctly from a business-conflict perspective.

### B-05. Minimal data caching on operational pages

- Cached resource: `database_manager.py:123`
- Cached config: `config_loader.py:33`
- Session-only AI cache: `pages/11_🤖_Agentic_Intelligence.py:25`
- One cached custom table query: `pages/12_🧩_Custom_Stock_Table.py:68`

Impact:

- Most operational pages hit the database again on every rerun.
- Frequent widget interaction multiplies DB traffic.

## Good News / Existing Safe Pattern

The sales creation path is better protected than the generic CRUD path:

- It locks stock rows with `FOR UPDATE`: `config.yaml:68`
- It checks the locked row's latest status before writing: `pages/04_💰_Sales.py:305`, `pages/04_💰_Sales.py:310`

This pattern is the right direction for workflows where inventory availability must stay correct.

## Proposed Solution Plan

### Phase 1. Protect correctness first

1. Add optimistic concurrency control to all generic edit/save flows.
   - Include the original `*_last_update` value in the row payload.
   - Change updates to `WHERE id = %s AND last_update = %s`.
   - If `rowcount == 0`, show "Record was modified by another user. Please reload."

2. Add conflict logging into the audit trail.
   - Log user, table, row id, attempted columns, original timestamp, and conflict outcome.

Reason:

- Preventing silent overwrite is the highest-risk issue because it can corrupt business history even with a small number of users.

### Phase 2. Reduce database pressure

1. Replace full-table `fetch_all` list pages with paginated, server-side filtered queries.
2. Start with Stocks, Sales, Bookings, Customers, Purchases, and Salesmen.
3. Only fetch visible rows plus a lightweight count query for pagination.

Reason:

- This lowers both latency and connection hold time, which directly improves multi-user behavior.

### Phase 3. Add safe caching

1. Add `st.cache_data(ttl=30-60)` for read-mostly lookup lists such as customers, salesmen, and in-stock dropdown data.
2. Clear the relevant cache after create/edit/delete actions.
3. Avoid caching highly volatile ledger-like views without explicit invalidation.

Reason:

- This reduces repeated queries caused by Streamlit reruns without risking stale writes when paired with proper cache invalidation.

### Phase 4. Raise concurrency capacity

1. Increase the DB pool from 10 to a higher tested number such as 20 or 30.
2. If usage keeps growing, place PgBouncer in front of PostgreSQL.
3. Add pool/latency monitoring before and after the change.

Reason:

- Increasing the pool alone is not enough, but it becomes effective after Phase 2 reduces wasteful query volume.

### Phase 5. Keep and expand stress testing

1. Keep `scripts/verification/multi_user_concurrency_probe.py` as a repeatable regression test.
2. Re-run it after each concurrency/scalability change.
3. Add one future test for concurrent edits to different rows and one for the sales booking workflow.

## Recommended Fix Order

1. Optimistic concurrency on generic updates
2. SQL pagination/filtering for list pages
3. Targeted caching with invalidation
4. Pool-size increase and monitoring
5. Additional multi-user regression tests

## Final Verdict

- Will 10 users cause delay?
  - Yes, some delay is already visible on heavier full-table pages, but the current dataset still remains usable around 10 concurrent read actions.

- Will concurrent amendments be captured correctly?
  - Not always. Same-row edits are vulnerable to silent overwrite in the generic CRUD flows.

- Will the system cache?
  - Only lightly. There is no broad operational data cache for the main CRUD pages today.

- Will the system support multi-user multi-tasking?
  - Partially yes for light-to-moderate use, but not robustly enough yet for conflict-safe multi-user editing or for bursts above 10 overlapping database operations.

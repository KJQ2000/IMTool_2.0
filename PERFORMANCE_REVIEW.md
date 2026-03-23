# Performance Review

## Highest Impact

### 1. Dashboard counts were loading full datasets just to compute `len(...)`

- Location: `app.py`
- Impact: unnecessary network I/O and row materialisation on every dashboard load.
- Change made: replaced full-row fetches with scalar count queries using `stock.count_by_status` and `customer.count_all`.

### 2. Dashboard pattern lookup bypassed the shared query layer

- Location: `pages/01_🏠_Dashboard.py`
- Impact: more code, direct connection handling, and inconsistent data-access patterns.
- Change made: moved the distinct-pattern query into `config.yaml` and reused `DatabaseManager.fetch_all(...)`.

## Medium Impact

### 3. Full-table fetches remain common in CRUD pages

- Locations:
- `pages/03_📦_Stocks.py`
- `pages/04_💰_Sales.py`
- `pages/05_📋_Purchases.py`
- `pages/06_📖_Bookings.py`
- `pages/07_👥_Customers.py`
- `pages/08_🤝_Salesmen.py`
- Impact: reruns can become expensive as row counts grow.
- Recommendation: add server-side filters, limit queries, pagination, or focused summary queries instead of loading entire tables.

### 4. Custom stock table is intentionally heavy

- Location: `pages/12_🧩_Custom_Stock_Table.py`, `config.yaml` key `stock.fetch_custom_table`
- Impact: wide joined query plus client-side pandas filtering/searching can become slow on large datasets.
- Recommendation: move search, filter, and pagination into SQL for larger deployments.

### 5. Stock filtering is mostly done in Python

- Location: `pages/03_📦_Stocks.py`
- Impact: fetch-all-then-filter scales poorly.
- Recommendation: add query variants for combined status/type/pattern filters or switch to a SQL-backed search form.

## Low Impact

### 6. AI pipeline is synchronous and sequential

- Location: `pages/11_🤖_Agentic_Intelligence.py`, `agents/`
- Impact: multi-step latency is expected because each request can call several models in series.
- Current mitigation: per-session cache exists in `st.session_state.ai_cache`.
- Recommendation: consider response caching with explicit invalidation and tighter query-generation retries if latency becomes a problem.

## Suggested Next Refactor Order

1. Add SQL-backed filters/pagination to stocks, sales, bookings, customers, and purchases.
2. Split the custom stock table into a lighter default report plus an advanced mode.
3. Add aggregate queries for other dashboard widgets rather than fetching full result sets.
4. Introduce a small service layer for repeated CRUD list/query logic.

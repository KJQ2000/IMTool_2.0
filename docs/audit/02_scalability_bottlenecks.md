# 🚀 Scalability & Performance Bottlenecks

| # | Bottleneck | Trigger Point | Location | Impact |
|---|---|---|---|---|
| B-01 | Unbounded `fetch_all` queries | > 5,000 rows | All pages (`db.fetch_all("stock.fetch_all")`) | UI freeze, excessive RAM usage |
| B-02 | Client-side dataframe filtering | > 10,000 rows | `utils/editable_table.py` (`filtered_df = df.copy()`) | High CPU load in Streamlit process |
| B-03 | ThreadedConnectionPool limit | > 10 concurrent requests | `database_manager.py` (`maxconn=10`) | HTTP 500 / Worker timeout |
| B-04 | Sync execution without caching | High usage | `stock.fetch_all` | Slow initial page load times |

---

## B-01 & B-02 — Large Data Handling (Unbounded Fetches)

**Problem:** Currently, the app loads the *entire* database table into memory, then filters it on the Streamlit server before sending it to the client's browser.
```python
# ❌ Current Approach
all_stocks = db.fetch_all("stock.fetch_all")
df = pd.DataFrame(all_stocks)
filtered_df = df[df['stk_status'] == filter_val]
st.data_editor(filtered_df)
```
If the database grows to 50,000 rows, this will consume hundreds of megabytes of RAM per session and potentially crash the Streamlit server.

**Fix: Server-Side Processing (Pagination & Filtering)**
Move the filtering to the SQL layer, and only fetch items the user actually sees.

1. **SQL Updates (`config.yaml`)**:
```yaml
stock:
  fetch_filtered: >
    SELECT * FROM {schema}.stock
    WHERE (stk_status = %(status)s OR %(status)s IS NULL)
    AND (stk_type = %(type)s OR %(type)s IS NULL)
    ORDER BY stk_created_at DESC
    LIMIT %(limit)s OFFSET %(offset)s
```

2. **Python Updates (`03_📦_Stocks.py`)**:
```python
# Pass UI filter values to the database layer
results = db.fetch_all("stock.fetch_filtered", {
    "status": st.session_state.get('sf', None),
    "type": st.session_state.get('tf', None),
    "limit": 100,  # Max rows per page
    "offset": (page_number - 1) * 100
})
```

---

## B-03 — Connection Pool Exhaustion

**Problem:** `DatabaseManager` limits the connection pool to 10. `st.data_editor` edits are saved row-by-row inside `save_table_changes()`. If 15 tab users click "Save" on large edits simultaneously, connections will queue, leading to psycopg2 timeouts.

**Fix:** 
1. Use `maxconn=50` or `100` if the database server supports it.
2. Implement **Batch `executemany`** instead of looping `build_update()`.
```python
# ❌ Current
for row_id, cols, vals in changed_rows:
    db.build_update(...)

# ✅ Fix
# Use psycopg2.extras.execute_values for an atomic, lightning-fast batch update.
```

---

## B-04 — Streamlit Re-renders

**Problem:** Streamlit re-runs the entire file from top to bottom on *every interactive widget click*.
For example, clicking the "Type" filter drop-down causes `DatabaseManager.fetch_all("stock.fetch_all")` to run again.

**Fix:** Use `@st.cache_data(ttl=60)` for fetching the raw data, dropping the cache only on "Save".
```python
@st.cache_data(ttl=300)
def get_cached_stocks():
    return db.fetch_all("stock.fetch_all")

# Use cached data
all_stocks = get_cached_stocks()

if st.button("Save Changes"):
    save_table_changes(...)
    get_cached_stocks.clear()  # Clear cache only on mutation
```

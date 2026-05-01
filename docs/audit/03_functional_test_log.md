# 🧪 Functional Test Log

| # | Action / Workflow | Expected Result | Actual Result / Status |
|---|---|---|---|
| F-01 | Create Stock with `labor` = -50 | Validation error | ❌ Fails. DB allows negative labor costs. UI inputs sometimes restrict it, but not strictly. |
| F-02 | Create Sale without customer | Validation error | ✅ Passes. UI blocks submission if `cust_map` is empty. |
| F-03 | Filter Stocks -> Edit a row -> Save | Correct row updates | ✅ Passes. `save_table_changes()` maps mutations by primary key (`stk_id`), immune to display/filter index shifting. |
| F-04 | Close Booking with no payment | Sale generated, Remaining = 0 | ✅ Passes. `remaining` is fetched, and if > 0, a payment is forced. |
| F-05 | Close Booking (Crash Simulation) | Transaction rolled back | ✅ Passes. Entire flow wrapped in `db.transaction()` context manager. Atomic rollback on exception. |
| F-06 | Barcode Generation on high sequence IDs | Accurate encoding | ❌ Fails (Edge Case). `seq_num % 26` logic will recycle prefixes, leading to overlapping codes after 2.6M items. |
| F-07 | Edit Booking (add more items) | Prices recalculate correctly | ✅ Passes. The recalculation loops over all items and sums the grand total exactly. |
| F-08 | Try to access page without login | Redirected to Auth/Login | ✅ Passes. `require_auth()` is properly located at the top of every `pages/` script. |

---

## Technical Notes on Test F-01 (Input Validation)
While Streamlit's `st.number_input(min_value=0.0)` prevents UI manipulation, there is no database-level constraint preventing negative prices or weights.
**Recommendation:** Add a Postgres `CHECK` constraint:
```sql
ALTER TABLE konghin.stock ADD CONSTRAINT chk_stk_weight_positive CHECK (stk_weight > 0);
ALTER TABLE konghin.stock ADD CONSTRAINT chk_stk_labor_positive CHECK (stk_labor_cost >= 0);
```

## Technical Notes on Test F-03 (Editable Table Safety)
The implementation of `render_filterable_editor` passes the filter test because it isolates the `original_df` and compares against the `edited_df` row-by-row mapping via the explicit `id_column`. A user filtering by "RING" and editing row index `3` will correctly update `STK_100003` rather than whatever row `3` was in the unfiltered dataframe.

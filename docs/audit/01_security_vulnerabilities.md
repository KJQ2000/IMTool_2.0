# 🔐 Security & Vulnerability Audit

| # | Vulnerability | Severity | Location | Status |
|---|---|---|---|---|
| V-01 | Float arithmetic for money (gold × weight + labor) — rounding drift over thousands of records | **HIGH** | All price calculations | ⚠️ Unfixed |
| V-02 | `remaining` computed from stale in-memory `booking.book_remaining` instead of re-querying DB inside transaction | **HIGH** | `06_📖_Bookings.py` Add Payment | ⚠️ Unfixed |
| V-03 | No optimistic locking on `st.data_editor` save — concurrent edits silently overwrite each other | **HIGH** | `utils/editable_table.py` | ⚠️ Unfixed |
| V-04 | `db.fetch_scalar("book_payment.sum_payments")` called **outside** the Close Booking transaction — window condition allows paying double | **MEDIUM** | `06_📖_Bookings.py` tab_close | ⚠️ Unfixed |
| V-05 | Auth: pages missing `require_auth()` check if developer adds a new page and forgets the call | **MEDIUM** | All `pages/` files | ✅ Currently OK |
| V-06 | `str(orig_val) != str(edit_val)` comparison for change detection — date/float formatting differences trigger false positives | **MEDIUM** | `utils/editable_table.py` L153 | ⚠️ Unfixed |
| V-07 | Delete operations have no soft-delete / audit trail — once deleted, data is unrecoverable | **MEDIUM** | All pages delete buttons | ⚠️ By design |
| V-08 | `build_update` sets NULL for empty strings — legitimate empty fields (e.g. `stk_remark`) will be wiped by editable table | **LOW** | `database_manager.py` L514 | ⚠️ Unfixed |
| V-09 | Pool max 10 connections — if 10 users are all loading large `fetch_all` concurrently, new connections block indefinitely | **LOW** | `database_manager.py` L81 | ⚠️ Design limit |
| V-10 | Barcode prefix uses `% 26` — STK IDs starting with digits > 26 (e.g. 27xxxx) wrap silently, producing duplicate prefixes | **LOW** | `database_manager.py` L615 | ⚠️ Unfixed |

---

## V-01 — Float Money Arithmetic

**Problem:** Python `float` accumulates error:
```python
0.1 + 0.2  # → 0.30000000000000004
```
In gold pricing, `weight * gold_price + labor` computes cents-level drift that compounds.

**Fix:** Use `decimal.Decimal` for all price calculations.

```python
# ✅ Fix: Replace all price math with Decimal
from decimal import Decimal, ROUND_HALF_UP

def calc_line_price(weight: float, gold: float, labor: float) -> Decimal:
    w = Decimal(str(weight))
    g = Decimal(str(gold))
    l = Decimal(str(labor))
    return (w * g + l).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
```
Apply to: Create Booking, Close Booking, Edit Booking, Create Sale.

---

## V-02 — Stale Remaining During Add Payment

**Problem:** The `book_remaining` read from `fetch_one()` is **before** the transaction. If two tabs pay simultaneously, both read the old remaining and one overpays.

```python
# ❌ Current (stale read outside transaction)
booking = db.fetch_one("booking.fetch_by_id", (pay_book_id,))
...
new_rem = float(booking.get("book_remaining", 0)) - p_amt
cur.execute(update_remaining_sql, (new_rem, pay_book_id))
```

```python
# ✅ Fix: Re-read remaining inside transaction with FOR UPDATE lock
with db.transaction() as cur:
    lock_sql = get_query("booking.fetch_by_id_for_update", schema=db.schema)
    cur.execute(lock_sql, (pay_book_id,))
    row = cur.fetchone()
    fresh_remaining = float(row["book_remaining"] or 0)
    if p_amt > fresh_remaining + 0.01:
        raise ValueError(f"Payment RM{p_amt} exceeds remaining RM{fresh_remaining}")
    new_rem = fresh_remaining - p_amt
    ...
```

Also add to `config.yaml`:
```yaml
booking:
  fetch_by_id_for_update: >
    SELECT * FROM {schema}.booking WHERE book_id = %s FOR UPDATE
```

---

## V-03 — Race Condition in Editable Table Save

**Problem:** `st.data_editor` does **not** know about changes another user made between page load and save click. Last writer wins.

**Fix:** Add a `version` integer or `last_update` timestamp to the WHERE clause on update:

```python
# In save_table_changes():
# Use optimistic locking: check last_update matches before updating
update_sql = f"""
    UPDATE {table} SET {set_clause}
    WHERE {id_col} = %s
    AND {prefix}_last_update = %s  -- optimistic lock
"""
if cur.rowcount == 0:
    raise ValueError(f"Row {row_id} was modified by another user. Please refresh.")
```

---

## V-04 — Window Condition in Close Booking

**Problem:** `fetch_scalar("book_payment.sum_payments")` is called **outside** the `db.transaction()` block that writes the final payment. Between that read and the write, another payment could come in.

**Fix:** Move the total-paid query **inside** the same transaction:
```python
with db.transaction() as cur:
    # Re-compute remaining INSIDE transaction with lock
    cur.execute(lock_sql, (close_book_id,))
    fresh_booking = cur.fetchone()
    remaining = float(fresh_booking["book_remaining"] or 0)
    if remaining > 0:
        ...  # insert final payment
```

---

## V-06 — False Positives in Change Detection

**Problem:** `str(Decimal("100.10")) != str(100.10)` will trigger an unnecessary DB update for every numeric row.

**Fix:**
```python
def _values_equal(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return float(a) == float(b)
    except (ValueError, TypeError):
        return str(a).strip() == str(b).strip()
```

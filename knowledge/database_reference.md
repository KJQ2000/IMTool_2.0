# Database Reference

Prepared from the live local PostgreSQL database on March 24, 2026 using the
current `konghin` schema plus application-level workflow interpretation.

## Snapshot summary

- Schema: `konghin`
- Live tables discovered: 10
- Physical foreign key constraints discovered: 0
- Important implication: relationships are enforced mainly by application code
  and query logic, not by database-level FK constraints

## Key conventions

### ID prefixes and sequence-backed keys

- `users` -> `USR`
- `booking` -> `BOOK`
- `customer` -> `CUST`
- `stock` -> `STK`
- `sale` -> `SALE`
- `salesman` -> `SLM`
- `purchase` -> `PUR`
- `book_payment` -> `BP`
- `category_pattern_mapping` -> `CPAT`

### Timestamp conventions

Most operational tables contain:

- `*_created_at`
- `*_last_update`

The `*_last_update` column is important because shared CRUD editing now uses it
for optimistic concurrency checks.

## Logical relationship map

The live schema has no physical FK constraints, but the application uses these
logical joins:

- `purchase.pur_slm_id` -> `salesman.slm_id`
- `stock.stk_pur_id` -> `purchase.pur_id`
- `stock.stk_sale_id` -> `sale.sale_id`
- `stock.stk_book_id` -> `booking.book_id`
- `sale.sale_cust_id` -> `customer.cust_id`
- `booking.book_cust_id` -> `customer.cust_id`
- `book_payment.bp_book_id` -> `booking.book_id`

Operationally, a useful mental model is:

`salesman -> purchase -> stock -> sale -> customer`

and

`stock -> booking -> book_payment`

with booking also linking to `customer`.

## Table reference

### `users`

- Primary key: `usr_id`
- Purpose: staff login identities
- Main columns:
  - `usr_email`
  - `usr_password`
  - `usr_username`
  - `usr_created_at`
  - `usr_last_update`
- Notes:
  - Used only for internal staff authentication
  - No self-service registration path exists in the app

### `customer`

- Primary key: `cust_id`
- Purpose: customer master data for sales and bookings
- Main columns:
  - `cust_name`
  - `cust_email_address`
  - `cust_phone_number`
  - `cust_address`
  - `cust_buyer_id`
  - `cust_sst_reg_no`
  - `cust_tin`
  - `cust_created_at`
  - `cust_last_update`
- Linked from:
  - `sale.sale_cust_id`
  - `booking.book_cust_id`

### `salesman`

- Primary key: `slm_id`
- Purpose: supplier or salesman master data
- Main columns:
  - `slm_name`
  - `slm_company_name`
  - `slm_phone_number`
  - `slm_email_address`
  - `slm_supplier_id`
  - `slm_tin`
  - `slm_reg_no`
  - `slm_msic`
  - `slm_desc`
  - `slm_address`
- Linked from:
  - `purchase.pur_slm_id`

### `purchase`

- Primary key: `pur_id`
- Purpose: incoming stock source record and cost basis
- Main columns:
  - `pur_code`
  - `pur_slm_id`
  - `pur_date`
  - `pur_billing_date`
  - `pur_method`
  - `pur_gold_cost`
  - `pur_gold_cost_999`
  - `pur_labor_cost`
  - `pur_weight`
  - `pur_invoice_no`
  - `pur_official_invoice`
  - `pur_total_trade_in_amt`
  - `pur_total_cash_amt`
  - `pur_total_amt`
  - `pur_payment_status`
  - `pur_created_at`
  - `pur_last_update`
- Linked to stock through:
  - `stock.stk_pur_id`
- Business role:
  - Provides cost information for manual stock creation and batch import

### `stock`

- Primary key: `stk_id`
- Purpose: central inventory table
- Main columns:
  - Identity and classification:
    - `stk_id`
    - `stk_type`
    - `stk_pattern`
    - `stk_gold_type`
    - `stk_tag`
    - `stk_remark`
  - Original inventory data:
    - `stk_weight`
    - `stk_size`
    - `stk_length`
    - `stk_width`
    - `stk_labor_cost`
    - `stk_gold_cost`
    - `stk_pur_id`
    - `stk_pur_date`
  - Barcode and print state:
    - `stk_barcode`
    - `stk_printed`
  - Sale state:
    - `stk_sale_id`
    - `stk_weight_sell`
    - `stk_labor_sell`
    - `stk_gold_sell`
    - `stk_sell_date`
    - `stk_profit`
  - Booking state:
    - `stk_book_id`
    - `stk_weight_book`
    - `stk_labor_book`
    - `stk_gold_book`
    - `stk_book_price`
  - Status and timestamps:
    - `stk_status`
    - `stk_returned`
    - `stk_created_at`
    - `stk_last_update`
- Business role:
  - This is the main operational truth for whether an item is in stock, booked,
    or sold

### `sale`

- Primary key: `sale_id`
- Purpose: sale header record
- Main columns:
  - `sale_receipt_no`
  - `sale_cust_id`
  - `sale_sold_date`
  - `sale_labor_sell`
  - `sale_gold_sell`
  - `sale_price`
  - `sale_weight`
  - `sale_official_receipt`
  - `sale_created_at`
  - `sale_last_update`
- Linked to:
  - customer via `sale_cust_id`
  - stock via `stock.stk_sale_id`
- Important behavior:
  - One sale can represent multiple stock items
  - The header stores aggregate values while each stock row stores its own sell
    pricing and profit details

### `booking`

- Primary key: `book_id`
- Purpose: booking header record
- Main columns:
  - `book_cust_id`
  - `book_receipt_no`
  - `book_date`
  - `book_gold_price`
  - `book_labor_price`
  - `book_weight`
  - `book_price`
  - `book_remaining`
  - `book_status`
  - `book_created_at`
  - `book_last_update`
- Linked to:
  - customer via `book_cust_id`
  - stock via `stock.stk_book_id`
  - payments via `book_payment.bp_book_id`
- Important behavior:
  - One booking can contain multiple stock items
  - Header values are aggregates; item-level booking pricing lives on `stock`

### `book_payment`

- Primary key: `bp_id`
- Purpose: payment ledger entries for a booking
- Main columns:
  - `bp_payment`
  - `bp_payment_date`
  - `bp_book_id`
  - `bp_status`
  - `bp_created_at`
  - `bp_last_update`
- Linked to:
  - `booking.book_id`
- Important behavior:
  - Used to compute total paid and remaining balance for a booking

### `category_pattern_mapping`

- Primary key: `cpat_id`
- Purpose: maps stock category/type to display pattern and optional image
- Main columns:
  - `cpat_category`
  - `cpat_pattern`
  - `cpat_image_path`
  - `cpat_created_at`
  - `cpat_last_update`
- Business role:
  - Drives the pattern dashboard and visual pattern management page

### `metadata`

- Primary key: `metadata_key`
- Purpose: generic key/value storage
- Main columns:
  - `metadata_key`
  - `metadata_value`
- Note:
  - Present in the live schema but not a prominent part of the current app flow

## Common status values

These come from code paths and UI options, not from database enum constraints.

### Stock status

- `IN STOCK`
- `BOOKED`
- `SOLD`
- `CANCELLED` appears in editing UI

### Booking status

- `BOOKED`
- `COMPLETED`
- `CANCELLED`

### Purchase payment status

- `NOT_PAID`
- `IN_PAYMENT`
- `PAID`
- `CANCELLED`

### Book payment status

- `PAID` is the main status used by the booking flows

## Important calculations

### Sale total

Per item:

`sell revenue = sell weight * gold sell price + labor sell`

Sale header totals are aggregated across selected stock rows.

### Booking total

Per item:

`booking line total = booking weight * booking gold price + booking labor`

Booking header totals are aggregated across selected stock rows.

### Booking remaining balance

`book_remaining = book_price - sum(book_payment.bp_payment)`

### Stock profit

The sale and booking-close flows calculate profit as:

`profit = revenue - original gold cost - original labor cost`

where original gold cost is based on the stock's original weight and original
gold cost basis.

## Operational database notes

- There are no physical foreign keys, so bad IDs are possible if writes bypass
  the application.
- Critical sale and booking operations use row locking to protect correctness.
- Generic CRUD editing relies on `*_last_update` optimistic concurrency checks.
- The denormalized reporting query `stock.fetch_custom_table` is intentionally
  heavy but useful for custom analysis.

## RAG grounding notes

If future RAG needs table-level retrieval, the highest-value tables are:

- `stock`
- `sale`
- `booking`
- `book_payment`
- `purchase`
- `customer`

Those six tables cover most business questions around inventory state, revenue,
bookings, deposits, and customer history.

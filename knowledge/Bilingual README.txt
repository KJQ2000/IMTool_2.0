====== SQL AGENT RULES ======
This file is schema grounding for the SQL agent in IMTool Improved. The active
PostgreSQL schema is konghin. Use fully qualified table names such as
konghin.stock, konghin.sale, konghin.booking, konghin.book_payment,
konghin.purchase, konghin.customer, konghin.salesman, konghin.users, and
konghin.category_pattern_mapping. The SQL agent should generate read-only
queries only. There are no physical foreign keys in the live schema, so joins
must use the logical relationship rules described below.

====== TABLE: konghin.stock ======
Purpose: central inventory table.
Primary key: stk_id.
Important columns:
- stk_id
- stk_type
- stk_pattern
- stk_weight
- stk_size
- stk_length
- stk_width
- stk_gold_type
- stk_gold_cost
- stk_labor_cost
- stk_status
- stk_pur_id
- stk_pur_date
- stk_sale_id
- stk_book_id
- stk_weight_sell
- stk_labor_sell
- stk_gold_sell
- stk_sell_date
- stk_profit
- stk_weight_book
- stk_labor_book
- stk_gold_book
- stk_book_price
- stk_barcode
- stk_printed
- stk_tag
- stk_remark
- stk_created_at
- stk_last_update
Business meaning: one row is one jewellery stock item. The stock table holds
original cost, current status, barcode, and any later booking or sale pricing.

====== TABLE: konghin.purchase ======
Purpose: purchase header and cost source for stock intake.
Primary key: pur_id.
Important columns:
- pur_id
- pur_code
- pur_slm_id
- pur_date
- pur_billing_date
- pur_method
- pur_gold_cost
- pur_gold_cost_999
- pur_labor_cost
- pur_weight
- pur_invoice_no
- pur_official_invoice
- pur_total_trade_in_amt
- pur_total_cash_amt
- pur_total_amt
- pur_payment_status
- pur_created_at
- pur_last_update
Common join: stock.stk_pur_id = purchase.pur_id.
Business meaning: purchase records provide cost basis for manually created or
batch-imported stock.

====== TABLE: konghin.sale ======
Purpose: sale header table.
Primary key: sale_id.
Important columns:
- sale_id
- sale_receipt_no
- sale_cust_id
- sale_sold_date
- sale_labor_sell
- sale_gold_sell
- sale_price
- sale_weight
- sale_official_receipt
- sale_created_at
- sale_last_update
Common joins:
- stock.stk_sale_id = sale.sale_id
- sale.sale_cust_id = customer.cust_id
Business meaning: one sale header can represent multiple stock items. Header
totals are aggregated, while each stock row stores its own final sale pricing.

====== TABLE: konghin.booking ======
Purpose: booking header table.
Primary key: book_id.
Important columns:
- book_id
- book_cust_id
- book_receipt_no
- book_date
- book_gold_price
- book_labor_price
- book_weight
- book_price
- book_remaining
- book_status
- book_created_at
- book_last_update
Common joins:
- stock.stk_book_id = booking.book_id
- booking.book_cust_id = customer.cust_id
- book_payment.bp_book_id = booking.book_id
Business meaning: one booking can represent multiple stock items. Header values
are aggregates. Item-level booking pricing lives on the stock rows.

====== TABLE: konghin.book_payment ======
Purpose: payment ledger for bookings.
Primary key: bp_id.
Important columns:
- bp_id
- bp_payment
- bp_payment_date
- bp_book_id
- bp_status
- bp_created_at
- bp_last_update
Common join: book_payment.bp_book_id = booking.book_id.
Business meaning: used to track deposits and later payments against a booking.

====== TABLE: konghin.customer ======
Purpose: customer master data.
Primary key: cust_id.
Important columns:
- cust_id
- cust_name
- cust_email_address
- cust_phone_number
- cust_address
- cust_buyer_id
- cust_sst_reg_no
- cust_tin
- cust_created_at
- cust_last_update
Common joins:
- sale.sale_cust_id = customer.cust_id
- booking.book_cust_id = customer.cust_id

====== TABLE: konghin.salesman ======
Purpose: supplier or salesman master data.
Primary key: slm_id.
Important columns:
- slm_id
- slm_name
- slm_company_name
- slm_phone_number
- slm_email_address
- slm_supplier_id
- slm_tin
- slm_reg_no
- slm_msic
- slm_desc
- slm_address
- slm_created_at
- slm_last_update
Common join: purchase.pur_slm_id = salesman.slm_id.

====== TABLE: konghin.category_pattern_mapping ======
Purpose: pattern/category metadata with optional image path.
Primary key: cpat_id.
Important columns:
- cpat_id
- cpat_category
- cpat_pattern
- cpat_image_path
- cpat_created_at
- cpat_last_update
Typical use: pattern dashboard and pattern management page.

====== TABLE: konghin.users ======
Purpose: staff login accounts.
Primary key: usr_id.
Important columns:
- usr_id
- usr_email
- usr_password
- usr_username
- usr_created_at
- usr_last_update
Use carefully: this table should rarely be queried for business reporting.

====== TABLE: konghin.metadata ======
Purpose: generic key-value storage.
Primary key: metadata_key.
Important columns:
- metadata_key
- metadata_value
Current app usage is limited compared with the main business tables.

====== LOGICAL JOINS ======
Use these join paths when building SQL:
- stock.stk_pur_id = purchase.pur_id
- purchase.pur_slm_id = salesman.slm_id
- stock.stk_sale_id = sale.sale_id
- sale.sale_cust_id = customer.cust_id
- stock.stk_book_id = booking.book_id
- booking.book_cust_id = customer.cust_id
- book_payment.bp_book_id = booking.book_id
The custom stock reporting page also uses these paths to denormalize purchase,
salesman, sale, booking, and customer data into one stock-centric result.

====== COMMON STATUS VALUES ======
Stock status values commonly used in the app:
- IN STOCK
- BOOKED
- SOLD
- CANCELLED appears in editing UI

Booking status values:
- BOOKED
- COMPLETED
- CANCELLED

Purchase payment status values:
- NOT_PAID
- IN_PAYMENT
- PAID
- CANCELLED

Book payment status:
- PAID is the normal booking payment status used by the flows

====== COMMON BUSINESS CALCULATIONS ======
Sale line revenue:
sell weight * gold sell price + labor sell

Booking line total:
booking weight * booking gold price + booking labor

Booking remaining:
booking.book_price - sum(book_payment.bp_payment)

Stock profit in sale and booking-close flows:
revenue - original gold cost - original labor cost

====== QUERYING GUIDANCE ======
For inventory state questions, start from konghin.stock.
For supplier cost or intake questions, join stock to purchase and salesman.
For completed sales reporting, join stock to sale and optionally customer.
For booking exposure, join booking to stock and book_payment.
For customer history, join customer to sale and booking.
If the question asks for counts by status, group by the relevant status column.
If the question asks for current availability, filter stock.stk_status = 'IN STOCK'.

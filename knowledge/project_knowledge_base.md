# IMTool Improved Project Knowledge Base

## Purpose

IMTool Improved is a Streamlit-based inventory and sales management system for
Chop Kong Hin. It is built for staff operations around jewellery inventory,
purchases, sales, bookings, customer data, supplier/salesman data, batch stock
import, barcode export, and an internal AI assistant.

The application is a staff-facing operational system, not a public e-commerce
site. The business context is a jewellery retailer handling 916/999 gold items,
pattern-based products, booking deposits, and later conversion of booked items
into completed sales.

## Core Stack

- Frontend and app shell: Streamlit multi-page app
- Database: PostgreSQL
- Database driver: `psycopg2`
- Data work: `pandas`, `numpy`, `openpyxl`
- Authentication: Streamlit session state plus password verification against
  PostgreSQL
- Security: `bcrypt` hashing support for staff passwords
- AI layer: OpenAI chat completions plus local TF-IDF retrieval
- Retrieval helper: `scikit-learn` TF-IDF with cosine similarity

## Main Runtime Components

### Application shell

- `app.py` is the entrypoint.
- It sets the premium UI theme, enforces login, shows database health, and
  renders dashboard metrics.

### Authentication

- `auth_controller.py` owns login, logout, and per-page access gating.
- Every page calls `require_auth()`.
- There is no self-service sign-up.
- Staff accounts must be provisioned by IT administrators.
- Legacy plain-text passwords can still be migrated to bcrypt after a
  successful login, but bcrypt is the intended steady-state model.

### Database access

- `database_manager.py` is the central ACID-aware data access layer.
- SQL is not hard-coded throughout the app. Queries are stored in
  `config/config.yaml` and looked up by key through `config_loader.py`.
- Connection pooling is provided by `ThreadedConnectionPool`.
- The AI query path uses a read-only execution helper that rejects write SQL.

### Page modules

- `pages/01_..._Dashboard.py`
  Pattern dashboard. Lets staff browse pattern mappings by stock type and jump
  into filtered stock records.

- `pages/02_..._Pattern_Management.py`
  Maintains category-to-pattern mappings and optional pattern images stored
  under `system_files/pattern_images/`.

- `pages/03_..._Stocks.py`
  Main stock CRUD page with filters, pagination, editing, stock creation, and
  barcode export for Niimbot label printing.

- `pages/04_..._Sales.py`
  Creates multi-item sales. Each sale can contain multiple stock rows, and each
  stock row receives its own sell pricing and profit calculation.

- `pages/05_..._Purchases.py`
  Purchase CRUD page for incoming inventory source records, payment status, and
  gold/labor cost reference values.

- `pages/06_..._Bookings.py`
  Creates and manages bookings. A booking can contain multiple stock items,
  accepts deposits/payments, and can later be closed atomically into a sale.

- `pages/07_..._Customers.py`
  Customer CRUD page for retail and invoice/customer master data.

- `pages/08_..._Salesmen.py`
  Supplier or salesman master data page.

- `pages/09_..._Batch_Import.py`
  CSV/Excel stock import. Pulls purchase cost context from `pur_code`, auto
  generates `stk_id` and barcode, and archives uploaded files into `staging/`.

- `pages/10_..._Barcode.py`
  Manual barcode lookup and algorithm test page.

- `pages/11_..._Agentic_Intelligence.py`
  Internal AI assistant page with a four-stage pipeline for general/policy and
  database questions.

- `pages/12_..._Custom_Stock_Table.py`
  Reporting page that joins stock with purchase, sale, booking, salesman, and
  customer context in one denormalized view.

## Data Flow and Business Workflow

### Purchase to stock flow

1. Staff creates a purchase record with supplier/salesman and cost data.
2. Stock can then be created manually or imported in batch against a purchase.
3. Each stock row stores its original cost basis and purchase link.

### Stock lifecycle

The stock table is the operational center of the system.

Typical lifecycle:

1. `IN STOCK`
2. `BOOKED`
3. `SOLD`

There is also UI support for `CANCELLED` in stock editing, but the main sales
and booking flows depend on `IN STOCK` availability checks before mutating
stock rows.

### Sale flow

1. Staff selects one or more `IN STOCK` items.
2. Staff enters sell weight, gold sell price, and labor sell per item.
3. On confirmation, the page locks each stock row with `FOR UPDATE`.
4. The app verifies every selected stock is still `IN STOCK`.
5. A `sale` row is created.
6. Each linked `stock` row is updated to `SOLD` with sale linkage and profit.

This flow is designed to avoid two users selling the same item at the same
time.

### Booking flow

1. Staff selects one or more `IN STOCK` items.
2. Staff enters per-item booking pricing plus an optional initial deposit.
3. On confirmation, the page locks stock rows with `FOR UPDATE`.
4. A `booking` row is created with aggregate totals and remaining balance.
5. Optional deposit is written into `book_payment`.
6. Stock rows are updated to `BOOKED`.

Closing a booking is the key compound workflow:

1. Lock the booking row.
2. Lock all linked booked stock rows.
3. Add final payment for any remaining balance.
4. Mark the booking as `COMPLETED`.
5. Create a `sale` row using the booking pricing.
6. Convert all linked stock rows from `BOOKED` to `SOLD`.

This is intentionally atomic so partial closure should not occur.

## Database design conventions

- Schema name: `konghin`
- Primary keys use prefixed business IDs such as `STK_...`, `SALE_...`,
  `BOOK_...`, `CUST_...`
- Sequence names are configured centrally in `config/config.yaml`
- Most mutable business tables carry both `*_created_at` and `*_last_update`
- Generic edit screens use optimistic concurrency via `expected_last_update`

## Integrity and concurrency patterns

The codebase now has two important correctness layers:

- Optimistic concurrency for generic CRUD edits
  Shared editor saves only succeed if the row's `*_last_update` still matches
  what the user originally loaded.

- Pessimistic row locking for critical transactional flows
  Sales and bookings use `SELECT ... FOR UPDATE` before changing the same stock
  rows.

Together, those two patterns reduce silent overwrite risk for concurrent users.

## Caching and performance behavior

- `DatabaseManager.get_instance()` is cached as a singleton resource.
- Shared read helpers in `utils/query_cache.py` cache frequent lookup and list
  queries.
- Cache is explicitly cleared after successful writes.
- Main CRUD pages now use SQL pagination and filtered counts instead of loading
  full tables first.

## Current AI / RAG Architecture

The current internal AI flow is a four-stage pipeline:

1. Question Understanding Agent
   Classifies the question as either:
   - general/policy
   - database

2. SQL Query Agent
   Generates read-only SQL using schema grounding from the legacy-named
   `knowledge/Bilingual README.txt`

3. Data Evaluation Agent
   Checks whether the SQL result actually answers the question

4. Summary Agent
   Produces the final user-facing answer using both database output and general
   knowledge from `knowledge/knowledge.txt`

Important current limits:

- Retrieval is file-based TF-IDF, not a vector database
- Knowledge is curated manually
- Policy context is section retrieval, not authoritative live website sync
- The AI page is synchronous, so each question waits for the full pipeline

## Security and governance notes

- No public sign-up flow exists
- All SQL for the AI agent is intended to be read-only
- Password provisioning should be handled by IT admins only
- Business-critical writes are expected to happen inside explicit transactions

## Recommended use of this documentation

This knowledge base should be used for:

- Staff onboarding
- Future RAG document ingestion
- SQL-agent grounding
- Policy-answer evaluation
- Schema change reviews

When the database schema or business workflow changes, update both the markdown
documents and the two retrieval-oriented text files so the current AI layer and
future RAG work from the same business truth.

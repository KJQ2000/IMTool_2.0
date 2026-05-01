# Repository Audit

## Scope

Audit date: 2026-03-23

Reviewed areas:

- repo structure and runtime artifacts
- authentication and session handling
- database access patterns and SQL safety
- AI agent pipeline and read-only query flow
- file upload, archive, and local image handling
- maintainability and performance hotspots

## Concise Summary

The repository is small enough to reason about fully, but it mixes source code and runtime artifacts in the same tree. The biggest risks were concentrated in authentication, HTML rendering of dynamic content, permissive SQL handling for the AI pipeline, and a booking workflow whose transaction scope was too loose. Those high-confidence fixes were implemented directly.

## Findings First

1. Legacy plain-text passwords were still accepted during login, and committed logs showed that this path was active in practice.
Status: mitigated in code by auto-migrating successful legacy logins to bcrypt, but existing database records still need review.

2. Dynamic content was rendered into HTML with `unsafe_allow_html=True` in several places.
Status: mitigated by escaping dynamic values before rendering in the sidebar, dashboard cards, barcode page, pattern management placeholders, and AI answer rendering.

3. Read-only AI SQL execution depended on string checks that did not explicitly reject comments or multiple statements.
Status: mitigated by normalising read-only SQL before execution and rejecting comments and multi-statement input.

4. Several write paths used interpolated identifiers or ad hoc SQL outside the central query registry.
Status: improved by validating identifiers in `DatabaseManager`, adding `insert_row`, and moving more booking/dashboard operations back into `config.yaml`.

5. The booking creation flow had a transaction-scoping bug that could let part of the workflow escape the transaction context.
Status: fixed so booking insert, optional deposit insert, and stock updates occur under one transaction.

6. Runtime artifacts are committed or colocated with source.
Status: not deleted, but documented and further ignored via `.gitignore`.

## Improvements Made

- Added safe HTML helpers in `utils/html_utils.py`.
- Added repo-local file resolution and filename sanitising helpers in `utils/path_utils.py`.
- Auto-migrate legacy plain-text passwords to bcrypt on successful login.
- Added identifier validation and safer insert/query helpers in `database_manager.py`.
- Fixed `get_currval()` to use `currval(...)` instead of `nextval(...)`.
- Hardened read-only SQL handling for the agent pipeline.
- Replaced dashboard full-row count fetches with scalar count queries.
- Removed direct low-level connection handling from the dashboard pattern query.
- Fixed booking transaction scope and moved payment delete/update SQL into config.
- Sanitised archived batch import filenames.
- Improved `.gitignore` so runtime files are less likely to accumulate in source control.
- Added repo documentation and cleanup guidance.

## Validation

- No `tests/` directory or Python test files were found.
- Syntax validation passed with `compileall -q` across `app.py`, root modules, `utils/`, `agents/`, and `pages/`.

## Remaining Risks

- Existing log files still contain operational history, SQL text, and user identifiers.
- Plain-text passwords remain a risk until every legacy user has been migrated or reset.
- Several CRUD pages still fetch full tables and filter in memory.
- The custom stock table page performs a very wide joined query and client-side filtering.
- The repo is not currently a Git repository, which reduces auditability for future changes.

# Security Review

## Highest Severity

### 1. Legacy plain-text password compatibility

- Location: `auth_controller.py`, `config.yaml`, `logs/app.log`
- Risk: accounts with unhashed passwords remain valid; compromise of the users table would expose immediately usable credentials.
- Evidence: login code had a direct plain-text fallback, and committed logs showed successful legacy-password authentication events.
- Change made: successful legacy logins now trigger automatic bcrypt migration via `auth.update_password_hash`.
- Follow-up: force password resets or verify that all remaining `usr_password` values are bcrypt hashes.

### 2. Dynamic HTML rendering of model and database content

- Location: `app.py`, `pages/01_🏠_Dashboard.py`, `pages/02_🎨_Pattern_Management.py`, `pages/10_🏷️_Barcode.py`, `pages/11_🤖_Agentic_Intelligence.py`
- Risk: HTML/markup injection in the Streamlit UI via user, database, or model-controlled values.
- Change made: added `utils/html_utils.py` and escaped dynamic content before rendering inside `unsafe_allow_html=True` blocks.
- Residual risk: static HTML blocks still use `unsafe_allow_html=True`, which is acceptable as long as dynamic fields continue to be escaped first.

### 3. Read-only agent SQL safety gaps

- Location: `database_manager.py`, `agents/sql_query_agent.py`
- Risk: comment-based bypasses or multiple statements could weaken the "read-only" guarantee.
- Change made: `DatabaseManager._normalise_readonly_sql()` now rejects comments, empty input, and multiple statements before execution.
- Residual risk: the agent still depends on prompt quality and schema context; keep the read-only database role in place.

## Medium Severity

### 4. Dynamic SQL identifiers without validation

- Location: `database_manager.py`, previously ad hoc insert/update paths in pages
- Risk: interpolated schema/table/column names are safe only if their sources stay trusted forever.
- Change made: added identifier validation and `insert_row()`; updated stock add/import flows to use it.

### 5. Local image paths loaded from database values

- Location: `pages/01_🏠_Dashboard.py`, `pages/02_🎨_Pattern_Management.py`
- Risk: database-driven file paths could point outside the intended asset area.
- Change made: repo-local paths are now resolved through `resolve_repo_local_file(...)`, and new uploads are stored as relative repo paths.

### 6. Unsanitised archived upload filenames

- Location: `pages/09_📥_Batch_Import.py`
- Risk: user-controlled filenames were written to disk in archive folders as-is.
- Change made: archive names now go through `sanitize_uploaded_filename(...)`.

## Low Severity / Hygiene

### 7. Committed runtime logs and caches

- Location: `logs/`, `__pycache__/`
- Risk: operational leakage, unnecessary repo noise, and accidental disclosure of emails or SQL text.
- Change made: `.gitignore` was tightened, but no files were removed in this run.

### 8. Missing repository-level test coverage

- Location: whole repo
- Risk: regressions are harder to catch, especially in transactional flows.
- Change made: none in code; documented as a material risk.

## Recommendations

- Confirm that all user passwords are now bcrypt hashes and remove the legacy fallback after migration is complete.
- Purge or archive committed log files outside the repo after review.
- Keep `.streamlit/secrets.toml`, `.env*`, `logs/`, and `staging/` out of version control.
- Add a small automated test suite for auth, booking creation, booking payments, and stock/sale state transitions.

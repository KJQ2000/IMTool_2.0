# IMTool Improved

Streamlit-based inventory and sales management system for a jewellery business. The app combines CRUD workflows for stock, purchases, sales, bookings, customers, and salesmen with an agentic AI page that can answer policy questions or generate read-only SQL against PostgreSQL.

## Main Areas

- `app.py`: app entrypoint, login gate, sidebar, and top-level dashboard metrics.
- `config/`: central query and prompt registries.
- `pages/`: Streamlit pages for operational workflows.
- `agents/`: OpenAI-powered question understanding, SQL generation, data evaluation, and summarisation steps.
- `utils/`: logging, RAG, safe HTML, and safe path helpers.
- `knowledge/`: text sources used by the RAG flow.
- `docs/`: audits, reviews, and structural guidance.
- `scripts/verification/`: repeatable verification and smoke-test scripts.
- `system_files/pattern_images/`: repo-local pattern image assets.
- `logs/`, `staging/`, `__pycache__/`: runtime/generated artifacts that should not be versioned.

## Runtime Requirements

- Python 3.11
- PostgreSQL credentials in `.streamlit/secrets.toml`
- OpenAI API credentials in `.streamlit/secrets.toml` or environment variables
- Packages from `requirements.txt`

Expected Streamlit secrets shape:

- `connections.postgresql`
- `connections.postgresql_readonly` (optional but recommended)
- `openai.api_key`
- `openai.model`

## Running

Install dependencies and run:

```bash
streamlit run app.py
```

## Audit Docs

- `docs/reviews/REPO_AUDIT.md`
- `docs/reviews/SECURITY_REVIEW.md`
- `docs/reviews/PERFORMANCE_REVIEW.md`
- `docs/guides/STRUCTURE_GUIDE.md`
- `docs/guides/DELETE_CANDIDATES.md`
- `docs/audit/`

## Validation

No automated test suite is currently present in the repository. Current verification helpers live in `scripts/verification/`. The latest audit changes were validated with:

```bash
C:\Windows\py.exe -3 -m compileall -q app.py auth_controller.py database_manager.py config_loader.py logging_config.py prompt_config.py utils agents pages
```

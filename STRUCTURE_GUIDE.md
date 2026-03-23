# Structure Guide

## Current Layout

- `app.py`: app shell, login gate, sidebar, and top-level metrics.
- `pages/`: operational Streamlit pages.
- `agents/`: AI agent pipeline stages.
- `utils/`: reusable helpers.
- `config.yaml`: database query registry.
- `prompts.yaml`: agent prompt registry.
- `knowledge/`: RAG source documents.
- `system_files/pattern_images/`: managed image assets.
- `logs/`, `staging/`, `__pycache__/`: runtime/generated output.

## What Works Well

- Queries are mostly centralised in `config.yaml`.
- The app is divided into clear business pages.
- The AI flow is separated from the CRUD flows.
- Logging and context helpers are already factored into `utils/`.

## Structural Pain Points

- Source and runtime artifacts live side by side.
- Many pages contain both UI logic and transactional business rules.
- Some pages still bypass the shared query layer or build SQL inline.
- There is no top-level `docs/` or `tests/` area.

## Recommended Target Structure

```text
IMTool Improved/
  app.py
  config/
    queries.yaml
    prompts.yaml
  pages/
  services/
    auth_service.py
    stock_service.py
    booking_service.py
    sale_service.py
  utils/
  knowledge/
  system_files/
    pattern_images/
  docs/
    REPO_AUDIT.md
    SECURITY_REVIEW.md
    PERFORMANCE_REVIEW.md
    STRUCTURE_GUIDE.md
    DELETE_CANDIDATES.md
  tests/
```

## Low-Risk Steps Already Taken

- Added shared safety helpers in `utils/`.
- Reduced direct SQL in page files.
- Tightened `.gitignore` for runtime artifacts.
- Added repository documentation.

## Low-Risk Next Steps

- Move `config.yaml` and `prompts.yaml` into a `config/` folder once import paths are updated.
- Introduce a `services/` layer for booking, sale, and stock workflows.
- Move audit Markdown into `docs/` after the team confirms the preferred docs layout.
- Keep runtime folders like `logs/` and `staging/` outside the source tree when possible.

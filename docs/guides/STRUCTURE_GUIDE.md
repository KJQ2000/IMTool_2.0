# Structure Guide

## Current Layout

- `app.py`: app shell, login gate, sidebar, and top-level metrics.
- `config/`: query and prompt registries.
- `pages/`: operational Streamlit pages.
- `agents/`: AI agent pipeline stages.
- `utils/`: reusable helpers.
- `knowledge/`: RAG source documents.
- `docs/`: audits, reviews, and maintenance guides.
- `scripts/verification/`: manual verification helpers.
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
- Automated tests are still missing even though the top-level `docs/` and `tests/` areas now exist.

## Recommended Target Structure

```text
IMTool Improved/
  app.py
  config/
    config.yaml
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
    audit/
    reviews/
    guides/
  tests/
```

## Low-Risk Steps Already Taken

- Added shared safety helpers in `utils/`.
- Reduced direct SQL in page files.
- Tightened `.gitignore` for runtime artifacts.
- Added repository documentation.

## Low-Risk Next Steps

- Keep `config/` as the single home for query and prompt registries.
- Introduce a `services/` layer for booking, sale, and stock workflows.
- Keep audits, reviews, and maintenance notes under `docs/`.
- Keep runtime folders like `logs/` and `staging/` outside the source tree when possible.

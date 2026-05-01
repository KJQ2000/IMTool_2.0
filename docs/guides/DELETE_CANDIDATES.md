# Delete Candidates

No files were deleted in this run.

## High-Confidence Candidates

### `__pycache__/` and nested `__pycache__/` directories

- Reason: generated Python bytecode
- Risk if removed: low
- Confidence: high
- Note: these are already covered by `.gitignore`

### `logs/app.log`

- Reason: runtime log artifact containing operational data and user identifiers
- Risk if removed: low to medium, depending on audit retention requirements
- Confidence: high
- Note: archive externally if the logs are still needed

### `logs/error.log`

- Reason: runtime error log artifact containing SQL errors and operational traces
- Risk if removed: low to medium, depending on incident-review needs
- Confidence: high

## Medium-Confidence Candidates

### `scripts/scratch/temp_parse.py`

- Reason: standalone scraping/HTML parsing utility not referenced anywhere else in the repo
- Risk if removed: medium, because it may be an ad hoc developer script
- Confidence: medium
- Recommendation: move to a `scripts/` folder if it is still useful, otherwise remove it later

### `staging/`

- Reason: runtime archive area for batch imports, not source code
- Risk if removed: medium, because operators may still rely on archived import files
- Confidence: medium
- Recommendation: keep the folder out of version control and rotate its contents operationally

## Keep

### `knowledge/`

- Reason: actively used by the AI/RAG pipeline

### `system_files/pattern_images/`

- Reason: active application assets referenced by pattern-management workflows

### `config/prompts.yaml`

- Reason: active prompt registry for the agent pipeline

### `config.yaml`

- Reason: active query registry for the application

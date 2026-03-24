# Knowledge Base

This folder now holds both human-readable project documentation and the text
assets that the current RAG flow already uses.

## Main files

- `knowledge.txt`
  Main general knowledge source for the current policy/general-answer RAG path.
  `agents/question_understanding.py` and `agents/summary_agent.py` read this
  file directly.

- `Bilingual README.txt`
  Legacy filename kept for compatibility. `agents/sql_query_agent.py` reads
  this file as schema context. It now contains a structured database guide for
  SQL grounding.

- `sql_query_examples.txt`
  Section-based question-to-SQL example library. The SQL agent retrieves the
  most relevant examples and includes them in its prompt as few-shot guidance.

- `project_knowledge_base.md`
  High-level system walkthrough: architecture, modules, workflows, security,
  and current AI behavior.

- `database_reference.md`
  Live-schema reference prepared from the PostgreSQL database plus application
  workflow interpretation.

- `company_policy_reference.md`
  Curated company/policy notes from the official Chop Kong Hin website with
  source links and practical RAG notes.

- `rag_seed_qa.json`
  Starter evaluation and training-style question/answer pairs for future RAG
  testing.

- `schema_snapshot.json`
  Machine-readable schema snapshot exported from the local PostgreSQL database.
  Generated on March 24, 2026 from the current development environment.

## Regeneration workflow

1. Run `scripts/verification/export_schema_snapshot.py` after schema changes.
2. Review `schema_snapshot.json` for new columns, tables, or counts.
3. Update the markdown docs if the business workflow changed.
4. Refresh `knowledge.txt` and `Bilingual README.txt` if the current RAG
   should immediately see the new information.
5. Add or adjust entries in `sql_query_examples.txt` when new SQL patterns are
   needed for the agent.
6. Add or adjust entries in `rag_seed_qa.json` for new policy or system cases.

## Current RAG note

The current retriever in `utils/rag.py` treats files containing repeated
`======` delimiters as section-based chunks. That is why both `knowledge.txt`
and `Bilingual README.txt` are written as standalone retrieval sections rather
than as one long narrative.

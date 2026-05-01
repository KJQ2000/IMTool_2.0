from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.rag import load_knowledge

KNOWLEDGE_DIR = ROOT / "knowledge"


def main() -> None:
    knowledge_path = KNOWLEDGE_DIR / "knowledge.txt"
    schema_path = KNOWLEDGE_DIR / "Bilingual README.txt"
    examples_path = KNOWLEDGE_DIR / "sql_query_examples.txt"
    qa_path = KNOWLEDGE_DIR / "rag_seed_qa.json"
    snapshot_path = KNOWLEDGE_DIR / "schema_snapshot.json"

    knowledge_chunks = load_knowledge(knowledge_path)
    schema_chunks = load_knowledge(schema_path)
    example_chunks = load_knowledge(examples_path)

    qa_data = json.loads(qa_path.read_text(encoding="utf-8"))
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    print(f"knowledge.txt chunks: {len(knowledge_chunks)}")
    print(f"Bilingual README.txt chunks: {len(schema_chunks)}")
    print(f"sql_query_examples.txt chunks: {len(example_chunks)}")
    print(f"rag_seed_qa.json items: {len(qa_data.get('items', []))}")
    print(f"schema_snapshot tables: {len(snapshot.get('tables', []))}")


if __name__ == "__main__":
    main()

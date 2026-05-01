from __future__ import annotations

import re
import tomllib
from pathlib import Path

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_PATH = ROOT / "knowledge" / "sql_query_examples.txt"
SECRETS_PATH = ROOT / ".streamlit" / "secrets.toml"


def load_db_config() -> dict[str, object]:
    with SECRETS_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    return data["connections"]["postgresql"]


def parse_examples(text: str) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    pattern = re.compile(
        r"={3,}\s*(.*?)\s*={3,}\s*(.*?)(?=\n={3,}\s*.*?\s*={3,}|\Z)",
        re.DOTALL,
    )

    for title, body in pattern.findall(text):
        lines = [line.rstrip() for line in body.splitlines()]

        try:
            question_idx = next(i for i, line in enumerate(lines) if line.strip() == "User question:")
            sql_idx = next(i for i, line in enumerate(lines) if line.strip() == "SQL:")
            reasoning_idx = next(i for i, line in enumerate(lines) if line.strip() == "Reasoning:")
        except StopIteration as exc:
            raise ValueError(f"Could not parse example section: {title}") from exc

        question = "\n".join(
            line for line in lines[question_idx + 1 : sql_idx] if line.strip()
        ).strip()
        sql = "\n".join(
            line for line in lines[sql_idx + 1 : reasoning_idx] if line.strip()
        ).strip()
        reasoning = "\n".join(
            line for line in lines[reasoning_idx + 1 :] if line.strip()
        ).strip()

        if not question or not sql:
            raise ValueError(f"Could not parse example section: {title}")

        examples.append(
            {
                "title": title,
                "question": question,
                "sql": sql,
                "reasoning": reasoning,
            }
        )

    return examples


def main() -> None:
    examples_text = EXAMPLES_PATH.read_text(encoding="utf-8")
    examples = parse_examples(examples_text)
    db = load_db_config()

    conn = psycopg2.connect(
        host=db["host"],
        port=int(db.get("port", 5432)),
        dbname=db["dbname"],
        user=db["user"],
        password=db["password"],
    )

    passed = 0
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for example in examples:
                cur.execute(example["sql"])
                if cur.description:
                    cur.fetchmany(3)
                passed += 1
                print(f"PASS: {example['title']}")
    finally:
        conn.close()

    print(f"Validated {passed} SQL example(s).")


if __name__ == "__main__":
    main()

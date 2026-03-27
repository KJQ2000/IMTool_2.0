from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agents.question_understanding as qu_agent
import agents.sql_query_agent as sql_agent
import agents.data_evaluation_agent as eval_agent
import agents.summary_agent as summary_agent


def _load_dataset(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Dataset must be a JSON list.")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="AI evaluation harness")
    parser.add_argument(
        "--dataset",
        default=str(Path("scripts") / "ai_eval_dataset.json"),
        help="Path to evaluation dataset JSON",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of cases")
    parser.add_argument("--skip-summary", action="store_true", help="Skip summary agent")
    parser.add_argument("--skip-eval", action="store_true", help="Skip data evaluation agent")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases = _load_dataset(dataset_path)
    if args.limit:
        cases = cases[: args.limit]

    total = len(cases)
    type_ok = 0
    sql_ok = 0
    template_ok = 0
    failures = 0

    print(f"Running {total} cases (dataset={dataset_path})")
    print(f"AI_FORCE_DB_ROUTER={os.getenv('AI_FORCE_DB_ROUTER', 'true')}")
    print(f"AI_USE_SQL_TEMPLATES={os.getenv('AI_USE_SQL_TEMPLATES', 'true')}")
    print(f"AI_REDACT_PII={os.getenv('AI_REDACT_PII', 'true')}")
    print("-" * 80)

    for case in cases:
        q = case["question"]
        expected_type = case.get("expected_type")
        expected_template = case.get("expect_template")
        start = time.time()
        try:
            qu = qu_agent.run(q)
            if expected_type and qu.get("type") == expected_type:
                type_ok += 1

            sql_r = None
            if qu.get("type") == "database":
                sql_r = sql_agent.run(qu.get("restructured_question") or q)
                if sql_r.get("error") is None:
                    sql_ok += 1
                if expected_template and sql_r.get("template_id") == expected_template:
                    template_ok += 1

                if not args.skip_eval and sql_r.get("error") is None:
                    eval_agent.run(
                        qu.get("restructured_question") or q,
                        sql_r.get("sql", ""),
                        sql_r.get("results", []),
                        sql_r.get("columns", []),
                    )
                if not args.skip_summary and sql_r.get("error") is None:
                    summary_agent.run(
                        q,
                        sql_r.get("results", []),
                        sql_r.get("columns", []),
                        sql=sql_r.get("sql"),
                        is_aggregate=bool(sql_r.get("is_aggregate")),
                    )

            elapsed = round(time.time() - start, 2)
            print(
                f"[{case['id']}] type={qu.get('type')} "
                f"sql_error={sql_r.get('error') if sql_r else 'n/a'} "
                f"template={sql_r.get('template_id') if sql_r else 'n/a'} "
                f"time={elapsed}s"
            )
        except Exception as exc:
            failures += 1
            print(f"[{case['id']}] ERROR: {exc}")

    print("-" * 80)
    if total:
        print(f"Classification accuracy: {type_ok}/{total}")
        print(f"SQL success rate: {sql_ok}/{total}")
        if any(c.get("expect_template") for c in cases):
            template_cases = len([c for c in cases if c.get("expect_template")])
            print(f"Template match rate: {template_ok}/{template_cases}")
    if failures:
        print(f"Failures: {failures}")


if __name__ == "__main__":
    main()

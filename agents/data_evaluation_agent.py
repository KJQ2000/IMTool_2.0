"""
agents/data_evaluation_agent.py
────────────────────────────────
Data Evaluation Agent — quality gate between SQL Agent and Summary Agent.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from openai import OpenAI
import streamlit as st

from prompt_config import get_prompt
from utils.logging_utils import get_logger

logger = get_logger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        try:
            api_key = st.secrets["openai"]["api_key"]
        except (KeyError, FileNotFoundError):
            api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OpenAI API key not found.")
        _client = OpenAI(api_key=api_key)
    return _client


def _format_results(results: list[dict], columns: list[str]) -> str:
    if not results:
        return "(No rows returned)"
    sample = results[:20]
    header = " | ".join(columns)
    rows_str = "\n".join(" | ".join(str(row.get(col, "")) for col in columns) for row in sample)
    suffix = f"\n... ({len(results) - 20} more rows)" if len(results) > 20 else ""
    return f"{header}\n{'-' * len(header)}\n{rows_str}{suffix}"


def run(question: str, sql: str, results: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    """Evaluate whether retrieved data adequately answers the question."""
    logger.info("[DataEvalAgent] Evaluating %d rows", len(results))
    t0 = time.perf_counter()

    try:
        model = st.secrets["openai"]["model"]
    except (KeyError, FileNotFoundError):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    logger.debug("[DataEvalAgent] Model=%s", model)

    system_prompt = get_prompt("data_evaluation_agent.system")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            f"User question: {question}\n\nSQL executed:\n{sql}\n\n"
            f"Database results:\n{_format_results(results, columns)}"
        )},
    ]

    response = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=0.1,
        max_tokens=512, response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[DataEvalAgent] JSON parse failed. Using deterministic fallback verdict.")
        result = {
            "verdict": "sufficient" if results else "insufficient",
            "feedback": "" if results else "Query returned no rows.",
            "reasoning": "JSON parse failed.",
        }

    result.setdefault("verdict", "sufficient")
    result.setdefault("feedback", "")
    result.setdefault("reasoning", "")

    logger.info(
        "[DataEvalAgent] Verdict=%s elapsed_ms=%d",
        result["verdict"],
        int((time.perf_counter() - t0) * 1000),
    )
    return result

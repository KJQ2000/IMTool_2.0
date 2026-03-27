"""
agents/summary_agent.py
────────────────────────
Summary Agent — final stage, synthesises database results with store knowledge.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
import streamlit as st
from config.prompt_config import get_prompt
from utils.rag import retrieve_relevant_chunks
from utils.logging_utils import get_logger

logger = get_logger(__name__)

_client: OpenAI | None = None
_KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "knowledge.txt"


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
        return "(No database records found)"
    sample = results[:50]
    header = " | ".join(columns)
    rows_str = "\n".join(" | ".join(str(row.get(col, "N/A")) for col in columns) for row in sample)
    suffix = f"\n... and {len(results) - 50} more rows" if len(results) > 50 else ""
    return f"{header}\n{'-' * max(len(header), 30)}\n{rows_str}{suffix}"


def run(question: str, results: list[dict[str, Any]], columns: list[str], chat_history: str = "") -> dict[str, Any]:
    """Generate the final user-facing answer."""
    logger.info("[SummaryAgent] Generating for: %s", question)
    t0 = time.perf_counter()

    try:
        model = st.secrets["openai"]["model"]
    except (KeyError, FileNotFoundError):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    logger.debug("[SummaryAgent] Model=%s results=%d", model, len(results))

    system_prompt = get_prompt("summary_agent.system")
    knowledge_context = retrieve_relevant_chunks(question, _KNOWLEDGE_PATH, top_k=4)
    db_text = _format_results(results, columns)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": (
            (f"Previous Conversation:\n{chat_history}\n\n" if chat_history else "") +
            f"User's question: {question}\n\n"
            f"--- Database Results ---\n{db_text}\n\n"
            f"--- Relevant Store Knowledge ---\n{knowledge_context}"
        )},
    ]

    response = _get_client().chat.completions.create(
        model=model, messages=messages, temperature=0.3, max_tokens=1024,
    )

    answer = response.choices[0].message.content.strip()
    logger.info(
        "[SummaryAgent] Answer generated (%d chars) elapsed_ms=%d.",
        len(answer),
        int((time.perf_counter() - t0) * 1000),
    )

    return {"answer": answer, "knowledge_context_used": knowledge_context}

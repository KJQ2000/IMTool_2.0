"""
agents/question_understanding.py
─────────────────────────────────
Question Understanding Agent — first agent in the pipeline.

Classifies user questions as general/policy or database-requiring.
For general questions, retrieves relevant policy sentences via RAG.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI
import streamlit as st
from config.prompt_config import get_prompt
from utils.ai_redaction import redact_text
from utils.ai_router import should_force_database
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
            raise ValueError("OpenAI API key not found in secrets or environment.")
        _client = OpenAI(api_key=api_key)
    return _client


def run(question: str, chat_history: str = "") -> dict[str, Any]:
    """Classify and optionally restructure the user's question."""
    logger.info("[QuestionUnderstandingAgent] Processing: %s", question)
    t0 = time.perf_counter()

    if should_force_database(question):
        logger.info("[QuestionUnderstandingAgent] Rule-based router forced database mode.")
        return {
            "type": "database",
            "answer": "",
            "restructured_question": question,
            "reasoning": "Rule-based router matched database intent.",
            "policy_sources": [],
        }

    try:
        model = st.secrets["openai"]["model"]
    except (KeyError, FileNotFoundError):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    logger.debug("[QuestionUnderstandingAgent] Model=%s", model)

    client = _get_client()
    system_prompt = get_prompt("question_understanding_agent.system")

    redacted_question = redact_text(question)
    redacted_history = redact_text(chat_history)

    messages = [
        {"role": "system", "content": system_prompt},
    ]
    if redacted_history:
        messages.append({"role": "user", "content": f"Previous Conversation:\n{redacted_history}"})
    messages.append({"role": "user", "content": f"User question: {redacted_question}"})

    response = client.chat.completions.create(
        model=model, messages=messages, temperature=0.1,
        max_tokens=512, response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()
    logger.debug("[QuestionUnderstandingAgent] Raw: %s", raw)

    try:
        result: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[QuestionUnderstandingAgent] JSON parse failed. Falling back to database mode.")
        result = {
            "type": "database", "answer": "",
            "restructured_question": question,
            "reasoning": "JSON parse failed; defaulting to database query.",
        }

    result.setdefault("type", "database")
    result.setdefault("answer", "")
    result.setdefault("restructured_question", question)
    result.setdefault("reasoning", "")
    result["policy_sources"] = []

    if result["type"] == "general":
        try:
            raw_ctx = retrieve_relevant_chunks(question, _KNOWLEDGE_PATH, top_k=5)
            chunks = [c.strip() for c in raw_ctx.split("\n\n---\n\n") if c.strip()]
            result["policy_sources"] = chunks
        except Exception as exc:
            logger.warning("[QuestionUnderstandingAgent] RAG failed: %s", exc)

    logger.info(
        "[QuestionUnderstandingAgent] Type=%s elapsed_ms=%d",
        result["type"],
        int((time.perf_counter() - t0) * 1000),
    )
    return result

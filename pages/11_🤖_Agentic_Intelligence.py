"""
pages/11_🤖_Agentic_Intelligence.py — Agentic RAG Chat Interface
"""
from __future__ import annotations
import hashlib
import os
import time
from typing import Any
import pandas as pd
import streamlit as st
from auth_controller import get_current_user, require_auth
from logging_config import get_logger
from utils.html_utils import format_multiline_html
from utils.logging_utils import log_context, new_trace_id, set_log_context

logger = get_logger(__name__)
require_auth()
set_log_context(user_email=get_current_user())

import agents.question_understanding as qu_agent
import agents.sql_query_agent as sql_agent
import agents.data_evaluation_agent as eval_agent
import agents.summary_agent as summary_agent

if "ai_cache" not in st.session_state:
    st.session_state.ai_cache: dict[str, Any] = {}
if "ai_history" not in st.session_state:
    st.session_state.ai_history: list[dict] = []

st.markdown(
    '<div style="background:linear-gradient(135deg,#FFFFFF 0%,#F4F6F9 100%);'
    'border-bottom:2px solid #D4AF37;box-shadow:0 4px 15px rgba(212,175,55,0.1);padding:2.5rem;margin-bottom:2.5rem;border-radius:0 0 16px 16px;">'
    '<div style="font-family:\'Cinzel\', serif;font-size:2.2rem;font-weight:600;color:#0B2545;transform:translateY(0);">🤖 Agentic Intelligence</div>'
    '<div style="color:#8D99AE;font-size:0.95rem;margin-top:0.3rem;letter-spacing:1px;text-transform:uppercase;">Natural language queries · 4-agent RAG pipeline · Read-only</div>'
    '</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("#### 💡 Try These")
    for s in ["How many items are in stock?", "What are the top selling stock types?",
              "Show pending bookings", "What is your refund policy?",
              "Total sales revenue this year?", "List all customers"]:
        if st.button(s, key=f"ai_{hashlib.md5(s.encode()).hexdigest()[:6]}", use_container_width=True):
            st.session_state["ai_q"] = s
            st.rerun()

active_q = st.session_state.pop("ai_q", None)
question = st.text_area("Ask about your business:", height=80, placeholder='e.g. "How many rings in stock?"', label_visibility="collapsed")

c1, c2 = st.columns([5, 1])
with c1:
    submit = st.button("✨ Ask", use_container_width=True)
with c2:
    if st.button("🗑️ Clear Cache", use_container_width=True):
        st.session_state.ai_cache = {}
        st.session_state.ai_history = []
        st.rerun()

if active_q:
    submit, question = True, active_q


def _cache_key(q): return hashlib.sha256(q.strip().lower().encode()).hexdigest()


def run_pipeline(q):
    key = _cache_key(q)
    trace_id = new_trace_id()

    with log_context(trace_id=trace_id, user_email=get_current_user()):
        if key in st.session_state.ai_cache:
            logger.info("AI cache hit for question hash=%s", key[:12])
            return {**st.session_state.ai_cache[key], "cached": True, "trace_id": trace_id}

        trace, t0 = [], time.time()
        logger.info("AI pipeline started question=%s", q)

        history_str = "\n".join([f"User: {h['q']}\nBot: {h.get('a', '')}" for h in st.session_state.ai_history[-5:]])

        with st.spinner("🔍 Analysing…"):
            qu = qu_agent.run(q, chat_history=history_str)
        trace.append({"agent": "Question Understanding", "output": qu})
        logger.info("Question classified as type=%s", qu.get("type"))

        if qu["type"] == "general":
            elapsed = round(time.time() - t0, 2)
            r = {
                "type": "general",
                "answer": qu["answer"],
                "policy_sources": qu.get("policy_sources", []),
                "trace": trace,
                "elapsed": elapsed,
                "cached": False,
                "trace_id": trace_id,
            }
            st.session_state.ai_cache[key] = {k: v for k, v in r.items() if k != "cached"}
            logger.info("AI pipeline completed type=general elapsed=%.2fs", elapsed)
            return r

        feedback, sql_r = None, {}
        for attempt in range(int(os.getenv("MAX_SQL_RETRIES", "3"))):
            with st.spinner(f"🛢️ SQL attempt {attempt + 1}…"):
                sql_r = sql_agent.run(
                    qu["restructured_question"],
                    chat_history=history_str,
                    previous_feedback=feedback,
                )
            trace.append({"agent": "SQL Query", "output": sql_r})
            logger.info(
                "SQL attempt=%d rows=%d error=%s",
                attempt + 1,
                len(sql_r.get("results", [])),
                sql_r.get("error"),
            )

            if sql_r["error"] and not sql_r["results"]:
                break

            with st.spinner("🔎 Evaluating…"):
                ev = eval_agent.run(
                    qu["restructured_question"],
                    sql_r["sql"],
                    sql_r["results"],
                    sql_r["columns"],
                )
            trace.append({"agent": "Data Eval", "output": ev})
            logger.info("Data evaluation verdict=%s", ev.get("verdict"))
            if ev["verdict"] == "sufficient":
                break
            feedback = ev["feedback"]

        with st.spinner("✍️ Summarising…"):
            sm = summary_agent.run(
                q,
                sql_r.get("results", []),
                sql_r.get("columns", []),
                chat_history=history_str,
            )
        trace.append({"agent": "Summary", "output": sm})

        elapsed = round(time.time() - t0, 2)
        r = {
            "type": "database",
            "answer": sm["answer"],
            "sql": sql_r.get("sql", ""),
            "results": sql_r.get("results", []),
            "columns": sql_r.get("columns", []),
            "sql_attempts": sql_r.get("attempts", 1),
            "trace": trace,
            "elapsed": elapsed,
            "cached": False,
            "trace_id": trace_id,
        }
        st.session_state.ai_cache[key] = {k: v for k, v in r.items() if k != "cached"}
        logger.info(
            "AI pipeline completed type=database elapsed=%.2fs rows=%d attempts=%d",
            elapsed,
            len(r["results"]),
            r["sql_attempts"],
        )
        return r


def render(r):
    if r.get("cached"):
        st.caption("⚡ Cached")
    if r.get("trace_id"):
        st.caption(f"Trace ID: {r['trace_id']}")
    safe_answer = format_multiline_html(r.get("answer", ""))
    st.markdown(f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;padding:2rem;box-shadow:0 4px 15px rgba(212,175,55,0.05);">'
                f'<h4 style="color:#0B2545;margin-top:0;margin-bottom:1rem;font-family:\'Cinzel\', serif;letter-spacing:1px;">💬 Answer</h4><div style="color:#2B2D42;font-size:1.05rem;line-height:1.6;">{safe_answer}</div></div>',
                unsafe_allow_html=True)
    st.caption(f"⏱ {r.get('elapsed', 0)}s")

    if r["type"] == "database":
        if r.get("sql"):
            st.code(r["sql"], language="sql")
        if r.get("results") and r.get("columns"):
            st.dataframe(pd.DataFrame(r["results"], columns=r["columns"]), use_container_width=True)
    else:
        for i, c in enumerate(r.get("policy_sources", []), 1):
            safe = c.replace("&", "&amp;").replace("<", "&lt;")
            st.markdown(f'<div style="background:#F4F6F9;border-left:4px solid #D4AF37;'
                        f'border-radius:6px;padding:0.9rem;margin-bottom:0.7rem;font-size:0.9rem;color:#2B2D42;border:1px solid #E2E8F0;">'
                        f'<b style="color:#0B2545;">📄 {i}</b><br>{safe}</div>', unsafe_allow_html=True)

    with st.expander("🔬 Trace"):
        for s in r.get("trace", []):
            st.markdown(f"**{s['agent']}**: {s.get('output', {}).get('reasoning', '')}")


if submit and question.strip():
    try:
        result = run_pipeline(question.strip())
        render(result)
        st.session_state.ai_history.append({"q": question.strip(), "a": result.get("answer", ""), "t": result.get("type"), "ts": time.strftime("%H:%M")})
    except Exception as e:
        st.error(f"❌ {e}")
        logger.error("AI pipeline error", exc_info=True)
elif submit:
    st.warning("Enter a question.")

if st.session_state.ai_history:
    with st.expander("🕑 History"):
        for h in reversed(st.session_state.ai_history[-20:]):
            st.markdown(f"`{h['ts']}` {'🗄️' if h['t'] == 'database' else '💡'} **{h['q']}**")

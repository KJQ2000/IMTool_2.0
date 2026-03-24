"""
utils/rag.py
────────────
Lightweight TF-IDF based Retrieval-Augmented Generation helper.

Uses scikit-learn's TfidfVectorizer with cosine similarity to rank
and return the most relevant text chunks from knowledge files.
No external vector database required.

Ported from DatabaseRAG/utils/rag.py with no functional changes.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ──────────────────────────────────────────────────────────
# Chunking
# ──────────────────────────────────────────────────────────

def _split_into_chunks(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def _split_by_section(text: str) -> List[str]:
    """Split text on section delimiters (e.g., ====== TITLE ======) keeping the header with the content."""
    lines = text.splitlines()
    chunks = []
    current_chunk = []
    
    for line in lines:
        stripped = line.strip()
        if re.match(r"^={3,}.*?={3,}$", stripped) or re.match(r"^={3,}$", stripped):
            if current_chunk:
                chunks.append("\n".join(current_chunk).strip())
                current_chunk = []
        current_chunk.append(line)
        
    if current_chunk:
        chunks.append("\n".join(current_chunk).strip())
        
    return [c for c in chunks if c.strip()]


# ──────────────────────────────────────────────────────────
# Knowledge Loader
# ──────────────────────────────────────────────────────────

def load_knowledge(filepath: str | Path) -> List[str]:
    """Read a knowledge file and return a list of text chunks.

    For the bilingual README (which uses ====== delimiters), each table
    block becomes one chunk.  For other files the text is split into
    overlapping word windows.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Knowledge file not found: {filepath}")

    text = path.read_text(encoding="utf-8", errors="ignore")

    if "======" in text:
        chunks = _split_by_section(text)
    else:
        chunks = _split_into_chunks(text, chunk_size=200, overlap=40)

    return [c for c in chunks if len(c.strip()) > 10]


# ──────────────────────────────────────────────────────────
# Retrieval
# ──────────────────────────────────────────────────────────

def retrieve_relevant_chunks(
    query: str,
    filepath: str | Path,
    top_k: int = 5,
) -> str:
    """Return the top_k most query-relevant chunks as a single
    concatenated string ready to inject into an LLM prompt.
    """
    chunks = load_knowledge(filepath)
    if not chunks:
        return ""

    corpus = [query] + chunks
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        analyzer="word",
    )
    tfidf_matrix = vectorizer.fit_transform(corpus)

    query_vec = tfidf_matrix[0]
    chunk_vecs = tfidf_matrix[1:]

    scores = cosine_similarity(query_vec, chunk_vecs).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]

    selected = [chunks[i] for i in top_indices if scores[i] > 0]
    if not selected:
        selected = chunks[:top_k]

    return "\n\n---\n\n".join(selected)

"""
Lightweight RAG pipeline over curated destination guides.

ingest -> clean -> chunk -> embed -> index -> retrieve -> inject

Uses scikit-learn's TF-IDF + cosine similarity instead of a hosted
embedding API: it needs no external key, runs fully offline, and is
plenty for a POC-scale curated corpus (a handful of markdown guides per
destination). Swap `_vectorize` for a real embedding model later without
touching the tool interface if the corpus grows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = Path(__file__).parent / "data"
CHUNK_SIZE_WORDS = 120
CHUNK_OVERLAP_WORDS = 20


@dataclass
class Chunk:
    text: str
    source: str


class DestinationRAG:
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._build_index()

    # -- ingest & chunk ----------------------------------------------------
    def _load_documents(self) -> list[tuple[str, str]]:
        docs = []
        for path in sorted(DATA_DIR.glob("*.md")):
            docs.append((path.stem, path.read_text(encoding="utf-8")))
        return docs

    def _clean(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _chunk(self, text: str, source: str) -> list[Chunk]:
        words = text.split(" ")
        chunks = []
        step = CHUNK_SIZE_WORDS - CHUNK_OVERLAP_WORDS
        for start in range(0, len(words), step):
            piece = " ".join(words[start:start + CHUNK_SIZE_WORDS])
            if piece.strip():
                chunks.append(Chunk(text=piece, source=source))
            if start + CHUNK_SIZE_WORDS >= len(words):
                break
        return chunks

    # -- embed & index -------------------------------------------------------
    def _build_index(self) -> None:
        for source, raw in self._load_documents():
            cleaned = self._clean(raw)
            self._chunks.extend(self._chunk(cleaned, source))

        if not self._chunks:
            return

        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform([c.text for c in self._chunks])

    # -- retrieve & inject -----------------------------------------------
    def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        if not self._chunks or self._vectorizer is None:
            return []
        query_vec = self._vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results = []
        for idx in ranked[:top_k]:
            if scores[idx] <= 0:
                continue
            results.append({
                "text": self._chunks[idx].text,
                "source": self._chunks[idx].source,
                "score": round(float(scores[idx]), 4),
            })
        return results


_rag_singleton: DestinationRAG | None = None


def get_rag() -> DestinationRAG:
    global _rag_singleton
    if _rag_singleton is None:
        _rag_singleton = DestinationRAG()
    return _rag_singleton

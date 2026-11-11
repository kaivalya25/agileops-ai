"""Ingest, index, search and evaluate the AgileOps knowledge base."""

import argparse
import json
import math
import re
from collections import Counter
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from agileops.database import connect, write_transaction

RUNBOOKS = Path(__file__).with_name("runbooks")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
RERANKING_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
Mode = Literal["semantic", "keyword", "hybrid"]
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
QUESTIONS = (
    (
        "Which approved CSV header should I restore after SOURCE_SCHEMA_MISMATCH?",
        {"RB-REPORT-SCHEMA"},
    ),
    ("How do I fix SQL_SYNTAX_ERROR and a WHERE after GROUP BY?", {"RB-REPORT-SQL"}),
    (
        "Which troubleshooting steps follow SOURCE_AUTH_FAILED after secret rotation?",
        {"RB-SOURCE-AUTH"},
    ),
    (
        "Why is gross_cents missing from the SQLite report schema?",
        {"RB-REPORT-COLUMN", "HIST-REPORT-0001"},
    ),
    (
        "How do I reconcile DUPLICATE_ORDER_ID and replayed source records?",
        {"RB-DUPLICATE-ORDERS"},
    ),
    (
        "What SOP verifies the count and regional totals after a reporting refresh?",
        {"SOP-REPORT-REFRESH"},
    ),
)


class DocumentMetadata(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    title: str = Field(min_length=1)
    system: str
    incident_type: str
    document_type: str
    severity: str
    date: date
    environment: str


class Chunk(BaseModel):
    id: str
    source: str
    metadata: DocumentMetadata
    text: str


class SearchFilters(BaseModel):
    system: str | None = None
    incident_type: str | None = None
    document_type: str | None = None
    severity: str | None = None
    environment: str | None = None
    from_date: date | None = None
    through_date: date | None = None

    def matches(self, metadata: DocumentMetadata) -> bool:
        fields = self.model_dump(
            exclude={"from_date", "through_date"}, exclude_none=True
        )
        return (
            all(getattr(metadata, field) == value for field, value in fields.items())
            and (self.from_date is None or metadata.date >= self.from_date)
            and (self.through_date is None or metadata.date <= self.through_date)
        )


class Hit(BaseModel):
    chunk: Chunk
    score: float


class Encoder(Protocol):
    name: str

    def encode(self, texts: Sequence[str]): ...


class SentenceEncoder:
    def __init__(self, name: str = EMBEDDING_MODEL) -> None:
        from sentence_transformers import SentenceTransformer

        self.name = name
        self.model = SentenceTransformer(name, device="cpu")

    def encode(self, texts: Sequence[str]):
        return self.model.encode(
            list(texts), normalize_embeddings=True, show_progress_bar=False
        )


class Reranker:
    def __init__(self, name: str = RERANKING_MODEL) -> None:
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(name, device="cpu")

    def score(self, query: str, hits: list[Hit]) -> list[Hit]:
        scores = self.model.predict(
            [(query, hit.chunk.text) for hit in hits], show_progress_bar=False
        )
        return sorted(
            [
                Hit(chunk=hit.chunk, score=float(score))
                for hit, score in zip(hits, scores)
            ],
            key=lambda hit: (-hit.score, hit.chunk.id),
        )


def ingest(
    directory: Path, *, words_per_chunk: int = 160, overlap: int = 24
) -> list[Chunk]:
    if not 0 <= overlap < words_per_chunk:
        raise ValueError("Chunk overlap must be smaller than the chunk size.")
    documents: set[str] = set()
    chunks = []
    for file in sorted(directory.rglob("*.md")):
        header, metadata_text, body = file.read_text(encoding="utf-8-sig").split(
            "---", 2
        )
        if header.strip():
            raise ValueError(f"Expected a metadata header in {file.name}.")
        metadata = DocumentMetadata.model_validate_json(metadata_text)
        if metadata.id in documents:
            raise ValueError(f"Duplicate document ID {metadata.id}.")
        documents.add(metadata.id)
        words = body.split()
        for start in range(0, len(words), words_per_chunk - overlap):
            end = start + words_per_chunk
            chunks.append(
                Chunk(
                    id=f"{metadata.id}:{start}",
                    source=file.relative_to(directory).as_posix(),
                    metadata=metadata,
                    text=" ".join(words[start:end]),
                )
            )
            if end >= len(words):
                break
    if not chunks:
        raise ValueError(f"No knowledge chunks found in {directory}.")
    return chunks


def build_index(path: Path, chunks: list[Chunk], encoder: Encoder) -> None:
    import faiss
    import numpy as np

    if not chunks:
        raise ValueError("An index requires at least one chunk.")
    vectors = np.ascontiguousarray(
        encoder.encode([f"{chunk.metadata.title}\n{chunk.text}" for chunk in chunks]),
        dtype=np.float32,
    )
    if (
        vectors.ndim != 2
        or len(vectors) != len(chunks)
        or not np.isfinite(vectors).all()
    ):
        raise ValueError("The encoder returned invalid embeddings.")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    path.parent.mkdir(parents=True, exist_ok=True)
    with write_transaction(path) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS knowledge_index (
               singleton INTEGER PRIMARY KEY CHECK(singleton = 1), model TEXT NOT NULL,
               chunks TEXT NOT NULL, index_bytes BLOB NOT NULL)"""
        )
        connection.execute(
            """INSERT INTO knowledge_index VALUES (1, ?, ?, ?)
               ON CONFLICT(singleton) DO UPDATE SET model = excluded.model,
               chunks = excluded.chunks, index_bytes = excluded.index_bytes""",
            (
                encoder.name,
                json.dumps([chunk.model_dump(mode="json") for chunk in chunks]),
                faiss.serialize_index(index).tobytes(),
            ),
        )


def _bm25(query: str, chunks: list[Chunk]) -> list[Hit]:
    terms = set(TOKEN_PATTERN.findall(query.lower()))
    if not terms or not chunks:
        return []
    documents = [
        Counter(TOKEN_PATTERN.findall(f"{chunk.metadata.title} {chunk.text}".lower()))
        for chunk in chunks
    ]
    lengths = [sum(document.values()) for document in documents]
    average = sum(lengths) / len(chunks) or 1
    weights = {}
    for term in terms:
        matching = sum(term in document for document in documents)
        weights[term] = math.log1p((len(chunks) - matching + 0.5) / (matching + 0.5))
    results = []
    for chunk, document, length in zip(chunks, documents, lengths):
        norm = 1.2 * (0.25 + 0.75 * length / average)
        score = sum(
            weights[term] * document[term] * 2.2 / (document[term] + norm)
            for term in sorted(terms)
        )
        if score > 0:
            results.append(Hit(chunk=chunk, score=score))
    return sorted(results, key=lambda hit: (-hit.score, hit.chunk.id))


class KnowledgeBase:
    def __init__(self, path: Path, encoder: Encoder | None = None) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"Build the knowledge index at {path} first.")
        with connect(path) as connection:
            row = connection.execute(
                "SELECT model, chunks, index_bytes FROM knowledge_index WHERE singleton = 1"
            ).fetchone()
        if row is None:
            raise ValueError("The knowledge index has no snapshot.")
        self.chunks = [
            Chunk.model_validate(chunk) for chunk in json.loads(row["chunks"])
        ]
        self.model = row["model"]
        self.index_bytes = row["index_bytes"]
        self.encoder = encoder
        self._index = None

    def _semantic(self, query: str, allowed: set[str]) -> list[Hit]:
        import faiss
        import numpy as np

        if self.encoder is None:
            self.encoder = SentenceEncoder(self.model)
        if self.encoder.name != self.model:
            raise ValueError(f"The index requires the {self.model} encoder.")
        if self._index is None:
            self._index = faiss.deserialize_index(
                np.frombuffer(self.index_bytes, dtype=np.uint8)
            )
        if self._index.ntotal != len(self.chunks):
            raise ValueError("Knowledge metadata does not match the vector index.")
        vector = np.ascontiguousarray(self.encoder.encode([query]), dtype=np.float32)
        if vector.shape != (1, self._index.d) or not np.isfinite(vector).all():
            raise ValueError("The encoder returned an incompatible query vector.")
        faiss.normalize_L2(vector)
        scores, indexes = self._index.search(vector, len(self.chunks))
        return [
            Hit(chunk=self.chunks[index], score=float(score))
            for score, index in zip(scores[0], indexes[0])
            if index >= 0 and self.chunks[index].id in allowed
        ]

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        mode: Mode = "hybrid",
        filters: SearchFilters | None = None,
        reranker: Reranker | None = None,
    ) -> list[Hit]:
        if not query.strip() or not 1 <= k <= 50:
            raise ValueError(
                "Search needs a question and a result count between 1 and 50."
            )
        chunks = [
            chunk
            for chunk in self.chunks
            if filters is None or filters.matches(chunk.metadata)
        ]
        if not chunks:
            return []
        keyword = _bm25(query, chunks) if mode != "semantic" else []
        semantic = (
            self._semantic(query, {chunk.id for chunk in chunks})
            if mode != "keyword"
            else []
        )
        if mode == "hybrid":
            scores: Counter[str] = Counter()
            sources = {}
            for ranking in (keyword, semantic):
                for rank, hit in enumerate(ranking, start=1):
                    scores[hit.chunk.id] += 1 / (60 + rank)
                    sources[hit.chunk.id] = hit.chunk
            results = [
                Hit(chunk=sources[key], score=score) for key, score in scores.items()
            ]
            results.sort(key=lambda hit: (-hit.score, hit.chunk.id))
        else:
            results = keyword or semantic
        if reranker and results:
            results = reranker.score(query, results[: max(20, k)])
        return results[:k]


def evaluate_retrieval(
    knowledge: KnowledgeBase, *, k: int, mode: Mode, reranker=None
) -> dict:
    results = []
    for question, expected in QUESTIONS:
        hits = knowledge.search(question, k=k, mode=mode, reranker=reranker)
        found = [hit.chunk.metadata.id for hit in hits]
        relevant = set(found) & expected
        first = next((i for i, doc in enumerate(found, 1) if doc in expected), None)
        results.append(
            {
                "question": question,
                "expected": sorted(expected),
                "retrieved": found,
                "recall_at_k": len(relevant) / len(expected),
                "precision_at_k": len(relevant) / k,
                "reciprocal_rank": 1 / first if first else 0,
            }
        )
    return {
        "mode": mode,
        "k": k,
        "cases": results,
        "recall_at_k": sum(row["recall_at_k"] for row in results) / len(results),
        "precision_at_k": sum(row["precision_at_k"] for row in results) / len(results),
        "mrr": sum(row["reciprocal_rank"] for row in results) / len(results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("tmp/knowledge.db"))
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--source", type=Path, default=RUNBOOKS)
    build.add_argument("--model", default=EMBEDDING_MODEL)
    for name in ("search", "evaluate"):
        command = commands.add_parser(name)
        if name == "search":
            command.add_argument("question")
            for field in SearchFilters.model_fields:
                command.add_argument("--" + field.replace("_", "-"))
        command.add_argument("-k", type=int, default=3)
        command.add_argument(
            "--mode", choices=["semantic", "keyword", "hybrid"], default="hybrid"
        )
        command.add_argument("--rerank", action="store_true")
    args = parser.parse_args()
    if args.command == "build":
        chunks = ingest(args.source)
        build_index(args.database, chunks, SentenceEncoder(args.model))
        result = {"indexed_chunks": len(chunks), "model": args.model}
    else:
        knowledge = KnowledgeBase(args.database)
        reranker = Reranker() if args.rerank else None
        if args.command == "evaluate":
            result = evaluate_retrieval(
                knowledge, k=args.k, mode=args.mode, reranker=reranker
            )
        else:
            filters = SearchFilters(
                **{field: getattr(args, field) for field in SearchFilters.model_fields}
            )
            result = [
                hit.model_dump(mode="json")
                for hit in knowledge.search(
                    args.question,
                    k=args.k,
                    mode=args.mode,
                    filters=filters,
                    reranker=reranker,
                )
            ]
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

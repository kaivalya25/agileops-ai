import re

import pytest

from agileops.knowledge import (
    RUNBOOKS,
    KnowledgeBase,
    SearchFilters,
    build_index,
    evaluate_retrieval,
    ingest,
)


class FixtureEncoder:
    name = "fixture-token-encoder"
    vocabulary = ("sql", "schema", "gross", "duplicate", "refresh", "auth", "header")

    def encode(self, texts):
        return [
            [
                re.findall(r"[a-z]+", text.lower()).count(word)
                for word in self.vocabulary
            ]
            for text in texts
        ]


def test_faiss_snapshot_reopens_and_filters_before_fusion(tmp_path):
    pytest.importorskip("faiss")
    path = tmp_path / "knowledge.db"
    chunks = ingest(RUNBOOKS, words_per_chunk=25, overlap=5)
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    assert len(chunks) > len(list(RUNBOOKS.glob("*.md")))
    build_index(path, chunks, FixtureEncoder())
    index = KnowledgeBase(path, FixtureEncoder())
    hits = index.search(
        "gross cents", filters=SearchFilters(document_type="historical_incident")
    )
    assert hits and {hit.chunk.metadata.id for hit in hits} == {"HIST-REPORT-0001"}
    assert (
        index.search("gross cents", filters=SearchFilters(environment="production"))
        == []
    )
    report = evaluate_retrieval(index, k=3, mode="keyword")
    assert report["cases"][0]["expected"] == ["RB-REPORT-SCHEMA"]
    assert 0 <= report["mrr"] <= 1

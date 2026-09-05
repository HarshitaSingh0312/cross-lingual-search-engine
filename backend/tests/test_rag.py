import uuid

from app.api.v1 import search as search_module
from app.services.rag_service import rag_service


async def _search_result_ids(client, q="artificial intelligence", top_k=3):
    resp = await client.get("/api/v1/search", params={"q": q, "top_k": top_k})
    return [r["search_result_id"] for r in resp.json()["results"]]


async def test_rag_returns_answer_with_citations(client, monkeypatch):
    ids = await _search_result_ids(client)

    async def fake_synthesize(query, docs):
        return f"This is about {query}. [1][2]"

    monkeypatch.setattr(search_module.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(rag_service, "synthesize", fake_synthesize)

    resp = await client.post("/api/v1/search/rag", json={"query": "artificial intelligence", "search_result_ids": ids})
    assert resp.status_code == 200

    data = resp.json()
    assert "[1][2]" in data["answer"]
    assert [c["number"] for c in data["citations"]] == [1, 2]
    assert data["citations"][0]["search_result_id"] == ids[0]
    assert data["model"] == search_module.settings.rag_model_name


async def test_rag_drops_out_of_range_citation_numbers(client, monkeypatch):
    ids = await _search_result_ids(client, top_k=2)

    async def fake_synthesize(query, docs):
        # [7] doesn't exist among the 2 docs sent - should never surface as a citation.
        return "Answer citing a document never sent. [1][7]"

    monkeypatch.setattr(search_module.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(rag_service, "synthesize", fake_synthesize)

    resp = await client.post("/api/v1/search/rag", json={"query": "x", "search_result_ids": ids})
    assert [c["number"] for c in resp.json()["citations"]] == [1]


async def test_rag_rejects_unknown_search_result_id(client, monkeypatch):
    monkeypatch.setattr(search_module.settings, "anthropic_api_key", "test-key")
    bogus = str(uuid.uuid4())
    resp = await client.post("/api/v1/search/rag", json={"query": "x", "search_result_ids": [bogus]})
    assert resp.status_code == 404


async def test_rag_requires_at_least_one_search_result_id(client):
    resp = await client.post("/api/v1/search/rag", json={"query": "x", "search_result_ids": []})
    assert resp.status_code == 422


async def test_rag_returns_503_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(search_module.settings, "anthropic_api_key", "")
    resp = await client.post("/api/v1/search/rag", json={"query": "x", "search_result_ids": [str(uuid.uuid4())]})
    assert resp.status_code == 503


async def test_rag_returns_503_on_anthropic_failure(client, monkeypatch):
    ids = await _search_result_ids(client, top_k=1)

    async def failing_synthesize(query, docs):
        raise RuntimeError("simulated Anthropic API failure")

    monkeypatch.setattr(search_module.settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(rag_service, "synthesize", failing_synthesize)

    resp = await client.post("/api/v1/search/rag", json={"query": "x", "search_result_ids": ids})
    assert resp.status_code == 503

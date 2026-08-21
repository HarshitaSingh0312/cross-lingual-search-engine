async def test_search_returns_results(client):
    resp = await client.get("/api/v1/search", params={"q": "artificial intelligence", "top_k": 5})
    assert resp.status_code == 200

    data = resp.json()
    assert data["query"] == "artificial intelligence"
    assert len(data["results"]) == 5
    for result in data["results"]:
        assert {"doc_id", "title", "summary", "language", "score"} <= result.keys()


async def test_search_finds_cross_lingual_matches(client):
    # A Spanish query should be able to surface non-Spanish documents on meaning alone.
    resp = await client.get("/api/v1/search", params={"q": "inteligencia artificial", "top_k": 10})
    languages = {r["language"] for r in resp.json()["results"]}
    assert len(languages) > 1


async def test_search_requires_query_param(client):
    resp = await client.get("/api/v1/search")
    assert resp.status_code == 422

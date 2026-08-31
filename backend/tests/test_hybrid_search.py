from app.services.hybrid_search import HybridSearchService
from app.services.cache_service import cache_service


async def test_hybrid_search_returns_results(client):
    resp = await client.get("/api/v1/search/hybrid", params={"q": "artificial intelligence", "top_k": 5})
    assert resp.status_code == 200

    data = resp.json()
    assert data["query"] == "artificial intelligence"
    assert len(data["results"]) == 5
    for result in data["results"]:
        assert {"doc_id", "title", "summary", "language", "score", "search_result_id"} <= result.keys()


async def test_hybrid_search_finds_cross_lingual_matches(client):
    resp = await client.get("/api/v1/search/hybrid", params={"q": "inteligencia artificial", "top_k": 10})
    languages = {r["language"] for r in resp.json()["results"]}
    assert len(languages) > 1


def test_reciprocal_rank_fusion_favors_docs_ranked_in_both_lists():
    # "b" is #2 in one list and #1 in the other - it should outrank "a" (#1 in only one list,
    # absent from the other), since RRF rewards agreement across retrievers over a single top rank.
    dense = ["a", "b", "c"]
    bm25 = ["b", "d", "e"]

    fused = HybridSearchService.reciprocal_rank_fusion([dense, bm25])
    ranked = sorted(fused, key=fused.get, reverse=True)

    assert ranked[0] == "b"
    assert set(ranked) == {"a", "b", "c", "d", "e"}


def test_reciprocal_rank_fusion_handles_disjoint_lists():
    fused = HybridSearchService.reciprocal_rank_fusion([["a", "b"], ["c", "d"]])
    assert fused["a"] == fused["c"]  # both rank 1 in their own list, equal fused score


def test_hybrid_cache_key_differs_from_dense_cache_key():
    dense_key = cache_service.make_key("test query", 10)
    hybrid_key = cache_service.make_key("test query", 10, method="hybrid")
    assert dense_key != hybrid_key

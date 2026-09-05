"""Load test for the cross-lingual search API.

Run against an already-running backend (docker compose up), from this directory:

    pip install -r requirements.txt
    locust -f locustfile.py --host http://localhost:8000 --headless \
        --users 20 --spawn-rate 5 --run-time 3m --csv results/run_u20

See docs/load_test_results.md for how these runs are turned into recorded p50/p95/p99
numbers (collect_metrics.py reads the real numbers back from Prometheus, not from
Locust's own client-side timings).
"""

import random
import uuid

from locust import HttpUser, between, task

# A realistic query mix, not a single repeated string — some queries are far more common
# than others (the same "popular vs. long-tail" shape real search traffic has), so caching
# behaves the way it would in production instead of either always missing or always hitting.
POPULAR_QUERIES = [
    "climate change",
    "inteligencia artificial",
    "intelligence artificielle",
    "cambio climático",
    "changement climatique",
    "computer science",
    "história del arte",
    "histoire de France",
    "machine learning",
    "segunda guerra mundial",
]

LONG_TAIL_QUERIES = [
    "renewable energy", "quantum physics", "ancient rome", "world war two",
    "economía global", "literatura española", "revolución francesa", "biología celular",
    "philosophie des sciences", "littérature française", "révolution industrielle",
    "système solaire", "réseaux de neurones", "biodiversité", "changement social",
    "evolución humana", "arquitectura moderna", "medicina tradicional", "energía solar",
    "cognitive science", "space exploration", "human evolution", "modern architecture",
    "renewable resources", "neural networks", "molecular biology", "art history",
    "political theory", "urban planning", "genetic engineering",
]


def pick_query() -> str:
    # 70/30 popular-vs-long-tail split, not a uniform draw over the whole pool.
    if random.random() < 0.7:
        return random.choice(POPULAR_QUERIES)
    return random.choice(LONG_TAIL_QUERIES)


class SearchUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.access_token: str | None = None
        self.last_search_result_id: str | None = None
        # Roughly half of simulated users are logged in - real traffic is a mix of
        # anonymous and authenticated search, and /me/history + feedback need a token.
        if random.random() < 0.5:
            email = f"loadtest-{uuid.uuid4().hex[:12]}@example.com"
            resp = self.client.post(
                "/api/v1/auth/signup",
                json={"email": email, "password": "loadtest-pw-123"},
                name="/api/v1/auth/signup",
            )
            if resp.status_code == 201:
                self.access_token = resp.json()["access_token"]

    @property
    def _auth_headers(self) -> dict:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        return {}

    @task(10)
    def dense_search(self) -> None:
        q = pick_query()
        resp = self.client.get(
            "/api/v1/search",
            params={"q": q, "top_k": 10},
            headers=self._auth_headers,
            name="/api/v1/search",
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                self.last_search_result_id = results[0]["search_result_id"]

    @task(3)
    def hybrid_search(self) -> None:
        q = pick_query()
        resp = self.client.get(
            "/api/v1/search/hybrid",
            params={"q": q, "top_k": 10},
            headers=self._auth_headers,
            name="/api/v1/search/hybrid",
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                self.last_search_result_id = results[0]["search_result_id"]

    @task(2)
    def feedback(self) -> None:
        if not self.last_search_result_id:
            return
        self.client.post(
            "/api/v1/feedback",
            json={"search_result_id": self.last_search_result_id, "is_relevant": True},
            headers=self._auth_headers,
            name="/api/v1/feedback",
        )

    @task(1)
    def history(self) -> None:
        if not self.access_token:
            return
        self.client.get("/api/v1/me/history", headers=self._auth_headers, name="/api/v1/me/history")

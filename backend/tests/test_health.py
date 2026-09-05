async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_ready_reports_all_dependencies_up(client):
    # conftest's autouse fixtures already load the model/BM25 index and the DB/Redis
    # containers are real in this test env, so a healthy stack should report fully ready.
    resp = await client.get("/api/v1/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"model_loaded": True, "redis": True, "database": True}


async def test_metrics_endpoint_exposes_prometheus_format(client):
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text or "http_request_duration_seconds" in resp.text

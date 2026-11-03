"""接口级冒烟测试：验证 /api/kb、/api/graph 与检索引用格式。

不依赖模型 key，也不需要起服务——用 FastAPI TestClient 在进程内跑。
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(BASE, "src", "safety_backend")
sys.path.insert(0, BACKEND)
sys.path.insert(0, os.path.join(BACKEND, "kb"))

import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from app import app
    return TestClient(app)


def test_health_degrades_without_key(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "degraded" in body


def test_kb_endpoint_returns_all_entries(client):
    r = client.get("/api/kb")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 40
    first = body["items"][0]
    for key in ("id", "topic", "title", "content", "source"):
        assert key in first, key


def test_graph_full(client):
    r = client.get("/api/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["total_nodes"] > 50
    assert body["total_edges"] > 100


def test_graph_focus_returns_smaller_subgraph(client):
    full = client.get("/api/graph").json()
    one = client.get("/api/graph", params={"focus": "K22", "layers": 1}).json()
    assert one["focus"] == "K22"
    assert 0 < one["total_nodes"] < full["total_nodes"]
    ids = {n["id"] for n in one["nodes"]}
    assert "K22" in ids


def test_search_returns_citation_ids(client):
    r = client.post("/api/search", json={"q": "交接要包含什么才算完成"})
    assert r.status_code == 200
    results = r.json()["results"]
    assert results, "检索应有结果"
    for item in results:
        assert item["id"] and item["source"], "每条结果必须带条目编号与来源"


def test_run_out_of_scope_is_rejected(client):
    r = client.post("/api/run", json={"business_id": "NOT-AUTH-999"})
    # 越权：返回 403 或业务层 out_of_scope，两者都可接受，但不能静默成功
    assert r.status_code in (200, 403)
    if r.status_code == 200:
        assert r.json()["status"] == "out_of_scope"

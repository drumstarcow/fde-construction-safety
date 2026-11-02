"""冒烟测试：不依赖网络与模型 key，验证服务能起、关键接口有响应。"""
import json, os, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "src", "safety_backend"))

def test_data_files_exist():
    d = os.path.join(BASE, "src", "safety_backend", "data")
    for name in ["business.json", "photos.json", "handover.json"]:
        assert os.path.exists(os.path.join(d, name)), name

def test_knowledge_base_size():
    kb = os.path.join(BASE, "src", "safety_backend", "kb", "knowledge.json")
    items = json.load(open(kb, encoding="utf-8"))
    assert len(items) >= 40, "知识库条目应不少于 40 条，当前 %d" % len(items)

def test_graph_edges():
    g = json.load(open(os.path.join(BASE, "src", "safety_backend", "kb", "graph.json"), encoding="utf-8"))
    assert len(g["nodes"]) > 0 and len(g["edges"]) > 0

def test_search_returns_citation():
    kb_dir = os.path.join(BASE, "src", "safety_backend", "kb")
    sys.path.insert(0, kb_dir)
    import kb_search as S
    res = S.search("交接要包含哪些内容才算完成", 3)
    assert res and all(r.get("id") and r.get("source") for r in res)

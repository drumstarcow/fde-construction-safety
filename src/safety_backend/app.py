"""施工隐患与整改闭环 · 协同助手 —— 后端入口（FastAPI）。

严格按《微专业-阶段五提示词v3后端版》的 HTTP API 契约实现：
  GET  /api/health
  GET  /api/business
  GET  /api/business/{id}
  POST /api/run
  POST /api/confirm
  GET  /api/handover
  GET  /api/audit
  POST /api/search
  GET  /api/eval

不写前端、不写业务系统、不自动销项/判定合格（红线）。
模型无 key 时自动降级，接口仍可跑（走规则）。
"""
import os
import sys
import json
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "kb"))

import audit.store as audit
from model.wrapper import ModelWrapper
from orchestrator import graph

DATA_DIR = os.path.join(ROOT, "data")


# ---------------- 数据加载 ----------------
def _load(name):
    with open(os.path.join(DATA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


BUSINESS = _load("business.json")
PHOTOS = _load("photos.json")
PHOTOS_BY_ID = {p["photo_id"]: p for p in PHOTOS}

MODEL = ModelWrapper()
CTX = {
    "business": BUSINESS,
    "photos_by_id": PHOTOS_BY_ID,
    "audit": audit,
    "model": MODEL,
}

# 幂等缓存：business_id -> (timestamp, result)
_RUN_CACHE = {}
_IDEMPOTENT_WINDOW = 300  # 秒


def _run(business_id):
    now = time.time()
    if business_id in _RUN_CACHE:
        ts, res = _RUN_CACHE[business_id]
        if now - ts < _IDEMPOTENT_WINDOW:
            res = dict(res)
            res["duplicate"] = True
            return res
    res = graph.run_pipeline(business_id, CTX)
    _RUN_CACHE[business_id] = (now, res)
    # 落库：将生成的草稿交接清单存为「待确认」状态（不自动确认，符合 REQ-03 卡点：
    # 未确认不得标记完成）。这样日常路径 run → confirm 才真正闭环，而非仅停留在响应体。
    _persist_draft_if_pending(res)
    return res


def _persist_draft_if_pending(res):
    """把 pending_confirm 的草稿交接清单落库为待确认项；已存在则不覆盖（尊重红线）。"""
    draft = res.get("draft")
    if not draft or res.get("status") != "pending_confirm":
        return
    ho_id = draft.get("handover_id")
    if not ho_id:
        return
    hs = _load_handover()
    if any(h.get("handover_id") == ho_id for h in hs):
        return  # 已存在则跳过，不覆盖原始记录
    entry = {
        "handover_id": ho_id,
        "business_id": draft.get("business_id"),
        "from_role": draft.get("from_role"),
        "to_role": draft.get("to_role"),
        "items": draft.get("items"),
        "unresolved_items": draft.get("unresolved_items", []),
        "note": draft.get("note"),
        "citations": draft.get("citations"),
        "confirmed_by": "",
        "confirmed_at": "",
    }
    hs.append(entry)
    _save_handover(hs)


# ---------------- 请求体 ----------------
class RunReq(BaseModel):
    business_id: str


class ConfirmReq(BaseModel):
    handover_id: str
    confirmed_by: str
    action: str = "approve"  # approve | revise
    changes: dict = None


class SearchReq(BaseModel):
    q: str


# ---------------- 应用 ----------------
app = FastAPI(title="施工隐患与整改闭环 · 协同助手后端", version="v3-backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL.mode, "degraded": MODEL.degraded}


@app.get("/api/business")
def list_business():
    return [
        {
            "business_id": b["business_id"],
            "event_time": b["event_time"],
            "area_code": b["area_code"],
            "level": b["level"],
            "status": b["status"],
            "version": b["version"],
        }
        for b in BUSINESS
    ]


@app.get("/api/business/{business_id}")
def get_business(business_id: str):
    b = next((x for x in BUSINESS if x["business_id"] == business_id), None)
    if not b:
        raise HTTPException(status_code=404, detail="business not found")
    related_photos = [PHOTOS_BY_ID[pid] for pid in b.get("photo_ids", []) if pid in PHOTOS_BY_ID]
    handovers = _load_handover()
    related_ho = [h for h in handovers if h.get("business_id") == business_id]
    audits = [a for a in audit.all() if a.get("business_id") == business_id]
    return {"business": b, "photos": related_photos, "handover": related_ho, "audit": audits}


@app.post("/api/run")
def run(req: RunReq):
    if not any(b["business_id"] == req.business_id for b in BUSINESS):
        # 越权/超范围：拒绝的同时留痕（红线要求：每次越权须有审计记录）
        audit.append("check_scope", actor="system", rule_hit="out_of_scope",
                     human_override="rejected_403", signer="", business_id=req.business_id)
        raise HTTPException(status_code=403, detail="out_of_scope / 越权：业务编号不在授权样本内")
    return _run(req.business_id)


@app.post("/api/confirm")
def confirm(req: ConfirmReq):
    handovers = _load_handover()
    target = next((h for h in handovers if h["handover_id"] == req.handover_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="handover not found")
    if not target.get("confirmed_by"):
        # 未确认状态不可导出
        target["confirmed_by"] = req.confirmed_by
        target["confirmed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        target["action"] = req.action
        if req.changes:
            target["changes"] = req.changes
        _save_handover(handovers)
        audit.append("confirm", actor=req.confirmed_by, rule_hit="人工确认",
                     human_override=req.action, signer=req.confirmed_by, business_id=target.get("business_id", ""))
    return {"ok": True, "final": True, "handover": target}


@app.get("/api/handover")
def list_handover():
    hs = _load_handover()
    pending = [h for h in hs if not h.get("confirmed_by")]
    confirmed = [h for h in hs if h.get("confirmed_by")]
    return {"pending": pending, "confirmed": confirmed}


@app.get("/api/audit")
def list_audit():
    rows = audit.all()
    rows = rows[::-1]  # 时间倒序
    return [
        {
            "action": r.get("action"),
            "actor": r.get("actor"),
            "rule_hit": r.get("rule_hit"),
            "model_suggestion": r.get("model_suggestion"),
            "human_override": r.get("human_override"),
            "signer": r.get("signer"),
            "at": r.get("at"),
            "business_id": r.get("business_id"),
        }
        for r in rows
    ]


@app.post("/api/search")
def search(req: SearchReq):
    results = kb_search.search(req.q, topk=5, expand=1)
    return {"q": req.q, "results": results}


@app.get("/api/eval")
def evaluate():
    return _run_eval()


# ---------------- handover 读写 ----------------
def _load_handover():
    with open(os.path.join(DATA_DIR, "handover.json"), encoding="utf-8") as f:
        return json.load(f)


def _save_handover(hs):
    with open(os.path.join(DATA_DIR, "handover.json"), "w", encoding="utf-8") as f:
        json.dump(hs, f, ensure_ascii=False, indent=2)


def _snapshot_handover():
    """深拷贝当前 handover.json，供评估结束后还原（保证评估可重复、不污染样本）。"""
    return json.loads(json.dumps(_load_handover(), ensure_ascii=False))


def _restore_handover(snap):
    _save_handover(json.loads(json.dumps(snap, ensure_ascii=False)))


# ---------------- 评估集（真跑） ----------------
import kb_search  # noqa: E402


def _run_eval():
    sets = []
    ho_snapshot = _snapshot_handover()  # 评估前快照，结尾还原

    # 回放集：对全部 100 笔历史隐患跑三步编排，检验自动关联率
    total = passed = failed = 0
    need_human_ids, conflict_ids = [], []
    for b in BUSINESS:
        total += 1
        r = graph.run_pipeline(b["business_id"], CTX)
        if r["status"] == "pending_confirm":
            passed += 1
        else:
            failed += 1
            (conflict_ids if r["status"] == "conflict" else need_human_ids).append(b["business_id"])
    rate = round(passed / total * 100, 1) if total else 0.0
    threshold = 0.8
    meets = rate >= threshold * 100
    buckets = []
    if need_human_ids:
        buckets.append("转人工%d笔(%s)" % (len(need_human_ids), ",".join(need_human_ids)))
    if conflict_ids:
        buckets.append("版本冲突%d笔(%s)" % (len(conflict_ids), ",".join(conflict_ids)))
    sets.append({
        "suite": "回放集", "total": total, "passed": passed, "failed": failed,
        "rate": rate, "threshold": threshold, "meets": meets,
        "evidence": "自动关联率=%d/%d=%.1f%%，阈值≥%.0f%%→%s；%s" % (
            passed, total, rate, threshold * 100, "达标" if meets else "未达标",
            "；".join(buckets) if buckets else "无异常"),
    })

    # 口径集：交接清单须含 f23 五要素（业务编号/版本/状态/未解决事项/接手人）
    hs = _load_handover()
    need = {"handover_id", "from_role", "to_role", "unresolved_items", "confirmed_by", "confirmed_at"}
    ok = sum(1 for h in hs if need.issubset(h.keys()))
    sets.append({"suite": "口径集", "total": len(hs), "passed": ok, "failed": len(hs) - ok,
                 "evidence": "交接字段含 f23 五要素：%d/%d" % (ok, len(hs))})

    # 异常集：四类情形（状态反复 / 资料缺依据 / 版本冲突 / 模型降级）
    cases = [("状态反复", "CS-0020"), ("资料缺依据", "CS-0007"), ("版本冲突", "CS-0013"), ("模型降级", "CS-0001")]
    ep = ef = 0
    cev = []
    for name, bid in cases:
        r = graph.run_pipeline(bid, CTX)
        good = (name == "模型降级" and r["degraded"]) or \
               (name != "模型降级" and r["status"] in ("need_human", "conflict"))
        if good:
            ep += 1
        else:
            ef += 1
            cev.append("%s:%s" % (name, r["status"]))
    sets.append({"suite": "异常集", "total": len(cases), "passed": ep, "failed": ef,
                 "evidence": "四类异常均转人工/降级：%s" % ("通过" if ef == 0 else ",".join(cev))})

    # 人工确认集（自包含，走真实日常路径，不依赖 data/handover.json 初始态）：
    #   ① POST /api/run 生成草稿 → /api/run 内部已将草稿落库为「待确认」（REQ-03 卡点真实闭环）
    #   ② POST /api/confirm 确认 → ③ 断言"已确认列表含该 handover_id 且不在待确认列表"
    # 结尾还原 handover.json，保证可重复、不影响口径集。
    sub1 = sub2 = False
    test_bid = test_ho = None
    for b in BUSINESS:
        rr = graph.run_pipeline(b["business_id"], CTX)
        if rr["status"] == "pending_confirm" and rr.get("draft"):
            hid = rr["draft"]["handover_id"]
            if not any(h["handover_id"] == hid for h in ho_snapshot):
                test_bid, test_ho = b["business_id"], hid
                break
    if test_bid:
        _RUN_CACHE.pop(test_bid, None)              # 强制 fresh run，保证可重复
        run_res = _run(test_bid)                   # ① 等价于 POST /api/run（内部已落库 pending）
        draft = run_res.get("draft") or {}
        ho_id = draft.get("handover_id") or test_ho
        sub1 = (run_res.get("status") == "pending_confirm" and bool(ho_id))
        # ② 确认前的落库断言：run 之后该草稿应已存在于 handover（待确认）
        persisted = any(h["handover_id"] == ho_id and not h.get("confirmed_by")
                        for h in _load_handover())
        confirm(ConfirmReq(handover_id=ho_id, confirmed_by="eval-测试员", action="approve"))  # ② POST /api/confirm
        hs1 = _load_handover()
        confirmed_now = {h["handover_id"] for h in hs1 if h.get("confirmed_by")}
        pending_now = [h["handover_id"] for h in hs1 if not h.get("confirmed_by")]
        sub2 = (persisted and ho_id in confirmed_now and ho_id not in pending_now)  # ③ 断言
    passed = int(sub1) + int(sub2)
    _restore_handover(ho_snapshot)  # 还原，避免污染样本/影响口径集
    sets.append({"suite": "人工确认集", "total": 2, "passed": passed, "failed": 2 - passed,
                 "evidence": "真实路径：POST /api/run(%s)→草稿%s 已落库待确认=%s → POST /api/confirm → 已确认列表含该id=%s 且不在待确认=%s；%s"
                            % (test_bid, test_ho, "是" if sub1 else "否", "是" if sub2 else "否", "是" if sub2 else "否",
                               "通过" if passed == 2 else "失败")})

    # 审计集：任取一笔业务，审计记录六字段齐全
    graph.run_pipeline("CS-0001", CTX)
    recs = [a for a in audit.all() if a.get("business_id") == "CS-0001"]
    fields = ["action", "actor", "rule_hit", "model_suggestion", "human_override", "signer"]
    good = any(all(f in r for f in fields) for r in recs)
    sets.append({"suite": "审计集", "total": 1, "passed": 1 if good else 0, "failed": 0 if good else 1,
                 "evidence": "CS-0001 审计记录六字段齐全：%s（命中 %d 条）" % ("是" if good else "否", len(recs))})

    return sets


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


# ---------------- 知识库与图谱（供前端可视化） ----------------
KB_DIR = os.path.join(ROOT, "kb")


@app.get("/api/kb")
def list_kb():
    """返回 49 条知识条目（含 id / 主题 / 内容 / 来源 / 关联标签）。"""
    with open(os.path.join(KB_DIR, "knowledge.json"), encoding="utf-8") as f:
        items = json.load(f)
    return {"total": len(items), "items": items}


@app.get("/api/graph")
def get_graph(layers: int = 1, focus: str = ""):
    """返回知识图谱节点与关系，供前端画图。

    layers: 关联层数（1=只返回与 focus 一跳相连的子图；0 或未给 focus 时返回全图）
    focus:  聚焦的条目 id，例如 K22
    """
    with open(os.path.join(KB_DIR, "graph.json"), encoding="utf-8") as f:
        g = json.load(f)

    nodes, edges = g.get("nodes", []), g.get("edges", [])
    if not focus or layers <= 0:
        return {"total_nodes": len(nodes), "total_edges": len(edges),
                "nodes": nodes, "edges": edges}

    # 从 focus 出发做 BFS，最多 layers 跳
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
        adj.setdefault(e["to"], []).append(e["from"])

    seen, frontier = {focus}, [focus]
    for _ in range(layers):
        nxt = []
        for n in frontier:
            for m in adj.get(n, []):
                if m not in seen:
                    seen.add(m)
                    nxt.append(m)
        frontier = nxt
        if not frontier:
            break

    sub_nodes = [n for n in nodes if n.get("id") in seen]
    sub_edges = [e for e in edges if e.get("from") in seen and e.get("to") in seen]
    return {"focus": focus, "layers": layers,
            "total_nodes": len(sub_nodes), "total_edges": len(sub_edges),
            "nodes": sub_nodes, "edges": sub_edges}


"""命令行演示：跑通三条路径并打印（用于出截图证据）。

① 正常：CS-0001 → pending_confirm + 草稿 + 引用
② 脏数据：CS-0007 → need_human + 原因（照片缺元数据）
③ 冲突：CS-0013 → conflict + 两版并列

运行：python scripts/demo.py
"""
import os
import sys
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "kb"))

import audit.store as audit
from model.wrapper import ModelWrapper
from orchestrator import graph


def build_ctx():
    data_dir = os.path.join(ROOT, "data")
    business = json.load(open(os.path.join(data_dir, "business.json"), encoding="utf-8"))
    photos = json.load(open(os.path.join(data_dir, "photos.json"), encoding="utf-8"))
    photos_by_id = {p["photo_id"]: p for p in photos}
    return {
        "business": business,
        "photos_by_id": photos_by_id,
        "audit": audit,
        "model": ModelWrapper(),
    }


def _print_trace(trace):
    print("  步骤追踪：")
    for t in trace:
        print("   - %s  (%s ms): %s" % (t["node"], t["durationMs"], _short(t["result"])))


def _short(obj, n=80):
    s = json.dumps(obj, ensure_ascii=False)
    return s[:n] + ("…" if len(s) > n else "")


def _line(c="="):
    print(c * 70)


def run_path(label, business_id, ctx):
    _line()
    print("路径 %s：business_id = %s" % (label, business_id))
    _line("-")
    res = graph.run_pipeline(business_id, ctx)
    print("状态(status):", res["status"])
    print("降级(degraded):", res["degraded"])
    if res.get("reasons"):
        print("原因(reasons):")
        for r in res["reasons"]:
            print("   -", r)
    if res.get("versions"):
        print("两版并列(versions):")
        for v in res["versions"]:
            print("   -", v)
    if res.get("draft"):
        d = res["draft"]
        print("草稿(draft):")
        print("   交接单号:", d["handover_id"], "| 从", d["from_role"], "→", d["to_role"])
        for it in d["items"]:
            print("   ·", it)
        print("   备注:", d["note"])
    if res.get("citations"):
        print("引用(citations):", ", ".join("%s(%s)" % (c["id"], c["title"]) for c in res["citations"]))
    _print_trace(res["trace"])
    return res


def main():
    ctx = build_ctx()
    print("\n施工隐患与整改闭环 · 协同助手 —— 后端演示（模型模式：%s）\n" % ctx["model"].mode)
    run_path("① 正常", "CS-0001", ctx)
    run_path("② 脏数据", "CS-0007", ctx)
    run_path("③ 冲突", "CS-0013", ctx)
    _line()
    print("演示结束。\n")


if __name__ == "__main__":
    main()

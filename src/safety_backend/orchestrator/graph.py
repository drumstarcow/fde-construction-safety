"""三步编排（等价于 LangGraph StateGraph；装不上 LangGraph 时用函数链，签名保持一致）。

Node1 check_scope    —— 校验业务编号是否在授权样本内
Node2 verify_version —— 调 kb_search 检索 K23/K41/K42，校验照片元数据与单据版本
Node3 draft_handover —— 调 kb_search 检索 K26/K27，生成待确认交接清单

任何一步都不写业务系统；状态只存在于内存/审计日志（红线）。
"""
import os
import sys
import time
import json

# 让本模块能 import kb/kb_search 与 rules/model 包
_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.abspath(_ROOT))
_KB_DIR = os.path.join(os.path.abspath(_ROOT), "kb")
sys.path.insert(0, os.path.abspath(_KB_DIR))
import kb_search  # 官方检索（BM25 + 字符二元组 + 图谱一跳扩展）
from rules import associate as assoc_mod
from rules import dedup as dedup_mod
from rules import version as ver_mod

# 知识库按 id 取条目（用于 K23/K41/K42/K26/K27 引用）
_KB_PATH = os.path.join(os.path.abspath(_KB_DIR), "knowledge.json")
_KB_BY_ID = {k["id"]: k for k in json.load(open(_KB_PATH, encoding="utf-8"))}


def _get_kb(kid):
    return _KB_BY_ID.get(kid)


def run_pipeline(business_id, ctx):
    audit = ctx["audit"]
    model = ctx["model"]
    business_list = ctx["business"]
    photos_by_id = ctx["photos_by_id"]
    t_start = time.time()

    trace = []
    degraded = model.degraded

    def node(name, fn):
        t0 = time.time()
        res = fn()
        trace.append({"node": name, "durationMs": round((time.time() - t0) * 1000, 1), "result": res})
        return res

    # ---- Node1 check_scope ----
    def _n1():
        biz = next((b for b in business_list if b["business_id"] == business_id), None)
        if biz is None:
            audit.append("check_scope", actor="system", rule_hit="out_of_scope", business_id=business_id)
            return {"in_scope": False}
        return {"in_scope": True, "business": biz}

    r1 = node("check_scope", _n1)
    if not r1["in_scope"]:
        return {
            "business_id": business_id,
            "status": "out_of_scope",
            "trace": trace,
            "draft": None,
            "reasons": ["业务编号不在授权样本内"],
            "versions": None,
            "citations": [],
            "degraded": degraded,
        }

    biz = r1["business"]

    # ---- Node2 verify_version ----
    def _n2():
        assoc = assoc_mod.associate(biz, photos_by_id)
        ver = ver_mod.check_version(biz)
        dup = dedup_mod.find_duplicate(biz, business_list)

        reasons = []
        if ver["conflict"]:
            reasons.append("单据版本冲突：存在 alt_versions，两版并列、不合并（附总监裁定）")
        if ver["flip"]:
            reasons.append("状态反复（如临边防护上午补装下午拆除致销项失效），须转人工并标注触发原因/接手人/确认时间")
        if assoc["insufficient"]:
            reasons.append("照片元数据缺失：%s 缺时间或位置，不猜不补，进人工修复队列" % (",".join(assoc["missing"])))
        if dup["duplicate"]:
            reasons.append("重复工单：与 %s 同区域/同隐患/同日期，进人工修复队列" % (",".join(dup["group"])))

        # 引用 K23/K41/K42
        cites = []
        for kid in ("K23", "K41", "K42"):
            e = _get_kb(kid)
            if e:
                cites.append({"id": e["id"], "title": e["title"], "source": e.get("source", "")})

        rule_hit = "ok" if not reasons else "; ".join(reasons)
        status = "ok"
        if ver["conflict"]:
            status = "conflict"
        elif reasons:
            status = "need_human"

        # 疑难记录若模型可用，尝试相关性建议（不可用则降级，不阻塞）
        model_suggestion = ""
        if status == "need_human" and model.available:
            model_suggestion = model.correlate(biz.get("title", "")) or ""

        audit.append("verify_version", actor="system", rule_hit=rule_hit,
                     model_suggestion=("suggestion" if model_suggestion else ""), business_id=business_id)

        out = {
            "status": status,
            "associate": assoc,
            "version": ver,
            "duplicate": dup,
            "reasons": reasons,
            "model_suggestion": model_suggestion,
            "versions": ver["versions"] if ver["conflict"] else None,
            "citations": cites,
        }
        return out

    r2 = node("verify_version", _n2)

    draft = None
    citations = r2["citations"]

    if r2["status"] == "conflict":
        # 版本冲突：两版并列，转人工裁定
        return _final(business_id, "conflict", trace, draft, r2["reasons"],
                     r2["versions"], citations, degraded, audit, model)

    if r2["status"] == "need_human":
        return _final(business_id, "need_human", trace, draft, r2["reasons"],
                     None, citations, degraded, audit, model)

    # ---- Node3 draft_handover ----
    def _n3():
        k26 = _get_kb("K26")
        k27 = _get_kb("K27")
        items = [
            "隐患：%s（等级 %s）" % (biz.get("title"), biz.get("level")),
            "责任区域：%s" % biz.get("area_code"),
            "关联照片：%s" % (",".join(biz.get("photo_ids", [])) or "无"),
            "当前状态：%s（版本 %s）" % (biz.get("status"), biz.get("version")),
        ]
        draft_obj = {
            "handover_id": "HO-%s" % biz["business_id"],
            "business_id": biz["business_id"],
            "from_role": "巡查员",
            "to_role": "整改协调员",
            "items": items,
            "unresolved_items": [],
            "note": "以下为系统【建议(suggestion)】草稿，须人工确认后方可导出交接清单；不自动批准、不写业务系统。",
            "citations": [{"id": e["id"], "title": e["title"], "source": e.get("source", "")}
                          for e in (k26, k27) if e],
        }
        cites3 = []
        for e in (k26, k27):
            if e:
                cites3.append({"id": e["id"], "title": e["title"], "source": e.get("source", "")})
        citations.extend(cites3)
        audit.append("draft_handover", actor="system", rule_hit="pending_confirm",
                     model_suggestion="suggestion", business_id=business_id)
        return draft_obj

    draft = node("draft_handover", _n3)
    return _final(business_id, "pending_confirm", trace, draft, None, None, citations, degraded, audit, model)


def _final(business_id, status, trace, draft, reasons, versions, citations, degraded, audit, model):
    audit.append("run_result", actor="system", rule_hit=status,
                 model_suggestion=("degraded" if degraded else ""), business_id=business_id)
    return {
        "business_id": business_id,
        "status": status,
        "trace": trace,
        "draft": draft,
        "reasons": reasons,
        "versions": versions,
        "citations": citations,
        "degraded": degraded,
    }

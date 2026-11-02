"""审计落盘：读写 data/audit.json。

审计记录六字段（对应 f45）：
  action, actor, rule_hit, model_suggestion, human_override, signer
外加 at(时间)、business_id、detail 便于溯源。
append 时绝不覆盖历史，只能追加（f15：错误结果不覆盖原记录）。
"""
import json
import os
import threading
import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT_PATH = os.path.join(_HERE, "..", "..", "data", "audit.json")
_lock = threading.Lock()


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def load():
    try:
        with open(AUDIT_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def all():
    return load()


def append(action, actor="system", rule_hit="", model_suggestion="",
           human_override="", signer="", business_id="", detail=""):
    rec = {
        "action": action,
        "actor": actor,
        "rule_hit": rule_hit,
        "model_suggestion": model_suggestion,
        "human_override": human_override,
        "signer": signer,
        "business_id": business_id,
        "detail": detail,
        "at": _now(),
    }
    with _lock:
        data = load()
        data.append(rec)
        with open(AUDIT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return rec

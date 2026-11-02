"""规则层③：版本校验与状态反复检测。

- 版本冲突：单据存在 alt_versions 且与当前 version 不一致 → 两版并列，不合并、不自行选宽松条款，附总监裁定（f24）。
- 状态反复：flags 含 status_flip（如临边防护上午补装下午拆除致销项失效）→ 转人工（f11/f44）。
"""


def check_version(business):
    flags = business.get("flags", []) or []
    if business.get("alt_versions"):
        versions = [
            {"version": business.get("version"), "status": business.get("status")}
        ] + business["alt_versions"]
        return {"conflict": True, "flip": False, "versions": versions}
    if "status_flip" in flags:
        return {"conflict": False, "flip": True, "versions": []}
    return {"conflict": False, "flip": False, "versions": []}

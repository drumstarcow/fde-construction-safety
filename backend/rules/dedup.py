"""规则层②：重复工单检测（去重）。

同一隐患被多人上报会形成重复工单：以 (责任区域 + 隐患标题 + 日期) 为去重键，
命中同组其它记录即判为重复，进人工修复队列（f31/f33：有歧义记录不进自动推荐样本）。
"""


def _key(b):
    return (b.get("area_code"), b.get("title"), (b.get("event_time") or "")[:10])


def find_duplicate(business, all_business):
    k = _key(business)
    group = [
        b["business_id"]
        for b in all_business
        if b["business_id"] != business["business_id"] and _key(b) == k
    ]
    if group:
        return {"duplicate": True, "group": sorted([business["business_id"]] + group)}
    return {"duplicate": False, "group": []}

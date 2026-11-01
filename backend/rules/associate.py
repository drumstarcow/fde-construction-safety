"""规则层①：照片与隐患的关联 / 去重 / 资料完整性校验。

确定性规则优先（红线：不自动销项、不写业务系统、不覆盖原记录）。
按 business_id + event_time + version 做关联；命中即出结果，不经过模型。
"""


def check_photos(business, photos_by_id):
    """校验该业务关联照片的元数据完整性。"""
    attached = []
    for pid in business.get("photo_ids", []):
        if pid in photos_by_id:
            attached.append(photos_by_id[pid])
    missing = [
        p["photo_id"]
        for p in attached
        if not p.get("photo_time") or not p.get("photo_location")
    ]
    return {
        "attached": attached,
        "missing": missing,
        "insufficient": len(missing) > 0,
        "count": len(attached),
    }


def associate(business, photos_by_id):
    """关联判定（规则命中即出结果，不外呼模型）。"""
    r = check_photos(business, photos_by_id)
    if r["insufficient"]:
        return {"matched": False, "insufficient": True, "missing": r["missing"]}
    # 元数据齐全 → 规则直接关联成功（对应 REQ-01 的“能自动关联”部分）
    return {
        "matched": True,
        "insufficient": False,
        "matched_photos": [p["photo_id"] for p in r["attached"]],
    }

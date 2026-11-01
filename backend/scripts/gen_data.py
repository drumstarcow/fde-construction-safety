"""扩展合成样本：在已验证的种子（CS-0001..CS-0020 / P-0001..P-0040）基础上，
向后追加 80 笔业务（CS-0021..CS-0100）与对应照片，使回放集达到 100 条。

设计目标（对照阶段四方案「回放集 100 条，自动关联率 ≥80%」）：
  - 种子 20 笔：9 干净 + 11 脏（已含 G1/G2/G3 重复、CS-0007 缺元数据、CS-0013/0019 版本冲突、CS-0020 状态反复）
  - 新增 80 笔：75 干净 + 5 脏（1 缺元数据 / 2 重复对 / 1 版本冲突 / 1 状态反复）
  → 合计 84 干净 / 16 脏 = 84% 自动关联率（≥80%）

规则（见 rules/*.py）：
  - 干净：在授权内、无 alt_versions、flags 空、照片 time+location 齐全、去重键(area,title,date)唯一
  - 脏：alt_versions→conflict；status_flip→need_human；照片缺字段→need_human；(area,title,date)重复→need_human
"""
import json
import os
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

bus = json.load(open(os.path.join(DATA, "business.json"), encoding="utf-8"))
photos = json.load(open(os.path.join(DATA, "photos.json"), encoding="utf-8"))

seed_n = len(bus)          # 20
photo_seq = len(photos) + 1  # 下一个照片编号（从 41 起）

AREAS = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "C1", "C2", "C3"]
HAZARDS = [
    "楼梯口防护栏杆缺失", "配电箱未上锁", "安全网破损", "未戴安全帽", "动火作业无监护",
    "临时用电私拉乱接", "焊接火花飞溅", "物料提升机无限位", "塔吊基础积水", "深基坑边坡无监测",
    "氧气乙炔间距不足", "外架密目网缺失", "消防器材失效", "洞口未覆盖", "脚手架脚手板未满铺",
    "高处作业未系安全带", "临电电缆拖地", "气瓶无防倾倒", "吊装无警戒区", "施工升降机超载",
]
UPLOADERS = ["林亦舟", "周敏", "陈志远", "黄文", "吴桐"]

# 新 80 笔的脏数据落点（其余为干净）
dirty_assign = {
    21: "missing",   # 缺元数据
    22: "dup_a",     # 重复对 a
    23: "dup_b",     # 重复对 b（与 a 同 area/title/date）
    24: "conflict",  # 版本冲突
    25: "flip",      # 状态反复
}
DUP_AREA, DUP_TITLE, DUP_DATE = "A1", "消防水管违规接管", "2026-10-22"

start = datetime.date(2026, 10, 16)
new_bus = []


def add_photo(seq, ptime, loc, uploader, attach):
    global photo_seq
    pid = "P-%04d" % photo_seq
    photo_seq += 1
    photos.append({
        "photo_id": pid,
        "photo_time": ptime,
        "photo_location": loc,
        "uploader": uploader,
        "attach_to": attach,
    })
    return pid


for n in range(21, 101):
    bid = "CS-%04d" % n
    kind = dirty_assign.get(n)
    area = AREAS[n % len(AREAS)]
    ev_date = start + datetime.timedelta(days=(n - 21))
    ev = ev_date.strftime("%Y-%m-%d") + "T09:20:00"
    uploader = UPLOADERS[n % len(UPLOADERS)]

    if kind == "missing":
        # 缺元数据：照片有但 location/time 为空，不猜不补
        title = "电梯井防护门缺失"
        p1 = add_photo(photo_seq, ev, area, uploader, bid)
        p2 = add_photo(photo_seq, None, None, uploader, bid)
        new_bus.append({
            "business_id": bid, "title": title, "event_time": ev, "area_code": area,
            "level": "中", "status": "整改中", "version": "v3",
            "photo_ids": [p1, p2], "alt_versions": [], "flags": [],
        })
    elif kind in ("dup_a", "dup_b"):
        # 重复对：与其他笔共享 (area,title,date)
        title = DUP_TITLE
        area = DUP_AREA
        ev = DUP_DATE + "T09:20:00"
        p1 = add_photo(photo_seq, ev, area, uploader, bid)
        new_bus.append({
            "business_id": bid, "title": title, "event_time": ev, "area_code": area,
            "level": "中", "status": "整改中", "version": "v3",
            "photo_ids": [p1], "alt_versions": [], "flags": [],
        })
    elif kind == "conflict":
        # 版本冲突：alt_versions 与当前并列
        title = "消防通道堆放材料（复核）"
        p1 = add_photo(photo_seq, ev, area, uploader, bid)
        new_bus.append({
            "business_id": bid, "title": title, "event_time": ev, "area_code": area,
            "level": "高", "status": "整改中", "version": "v3",
            "photo_ids": [p1],
            "alt_versions": [{"version": "v2", "status": "已销项"}],
            "flags": ["version_conflict"],
        })
    elif kind == "flip":
        # 状态反复：上午补装下午拆除致销项失效
        title = "临边防护反复"
        p1 = add_photo(photo_seq, ev, area, uploader, bid)
        p2 = add_photo(photo_seq, ev, area, uploader, bid)
        new_bus.append({
            "business_id": bid, "title": title, "event_time": ev, "area_code": area,
            "level": "中", "status": "销项失效", "version": "v3",
            "photo_ids": [p1, p2], "alt_versions": [], "flags": ["status_flip"],
        })
    else:
        # 干净：照片齐全、去重键唯一（日期逐笔不同）
        title = "%s（%s）" % (HAZARDS[n % len(HAZARDS)], area)
        p1 = add_photo(photo_seq, ev, area, uploader, bid)
        p2 = add_photo(photo_seq, ev, area, uploader, bid)
        new_bus.append({
            "business_id": bid, "title": title, "event_time": ev, "area_code": area,
            "level": ["低", "中", "高"][n % 3], "status": "整改中", "version": "v3",
            "photo_ids": [p1, p2], "alt_versions": [], "flags": [],
        })

bus.extend(new_bus)
json.dump(bus, open(os.path.join(DATA, "business.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
json.dump(photos, open(os.path.join(DATA, "photos.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)

clean = sum(1 for b in bus if not (
    b.get("alt_versions") or "status_flip" in (b.get("flags") or [])
    or any(pid for pid in b.get("photo_ids", []) if not next((p for p in photos if p["photo_id"] == pid), {}).get("photo_time") or not next((p for p in photos if p["photo_id"] == pid), {}).get("photo_location"))
))
print("business total =", len(bus), "| photos total =", len(photos))
print("新增业务 =", len(new_bus), "| 其中脏数据规划 =", len(dirty_assign))

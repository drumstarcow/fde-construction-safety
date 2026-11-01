# 施工隐患与整改闭环 · 协同助手（后端）

> 微专业 / FDE 训练中心 · 阶段五（构建集成）交付物
> 客户（合成）：**远筑工程**
> 定位：AI 协同**助手**，只产出**建议（suggestion）**，关键动作必须人工在环确认（human-in-the-loop）。

---

## 1. 这是什么

一个**后端 API 服务**，把前四个阶段沉淀的业务规则、知识库、脏数据处理逻辑，封装成可运行、可评估的服务。

- 不写前端（阶段五只做后端）。
- **不自动销项、不自动判定合格、不写业务系统、不覆盖原始记录、不借账号**——这是红线。
- 模型无 key 时**自动降级**，仅走规则，接口照常可用。

---

## 2. 目录结构

```
safety-backend/
├── app.py                 # FastAPI 入口，9 个 HTTP 接口（见 API.md）
├── orchestrator/
│   └── graph.py           # 三步编排：check_scope → verify_version → draft_handover
├── rules/
│   ├── associate.py       # 照片元数据关联与缺失识别
│   ├── dedup.py           # 重复工单识别（同区域/同隐患/同日期）
│   └── version.py         # 版本冲突 / 状态反复识别
├── model/
│   └── wrapper.py         # 模型封装：可用/降级两种模式
├── audit/
│   └── store.py           # 审计日志：六字段、追加写、线程锁
├── kb/                    # 官方交付素材（知识库）
│   ├── knowledge.json     # 49 条知识条目
│   ├── graph.json         # 图谱：89 节点 / 278 边
│   ├── kb_search.py       # 官方检索：BM25 + 字符二元组 + 图谱一跳扩展
│   ├── 事实库.md
│   └── 图1-现状流程.png / 图2-目标流程.png / 图3-知识库页面.png
├── data/                  # 合成样本（演示用，非真实业务数据）
│   ├── business.json      # 100 条业务单（含脏数据：重复/缺元数据/版本冲突/状态反复）
│   ├── photos.json        # 197 张照片元数据（少量故意缺时间或位置）
│   ├── handover.json      # 2 条交接清单（1 已确认 / 1 待确认）
│   └── audit.json         # 审计日志（运行时追加，初始为空）
├── scripts/
│   └── demo.py            # 三条路径演示脚本（正常 / 脏数据 / 冲突）
├── requirements.txt
├── API.md                 # 接口契约 + 真实跑过的请求/返回
├── DELIVERY.md            # 做了什么 / 没做什么 / 已知限制 / 五项未核实项
└── server.log             # 启动日志（运行后生成）
```

---

## 3. 运行方式

```bash
# 1) 安装依赖（本机托管 Python 已自带 fastapi/uvicorn）
pip install -r requirements.txt

# 2) 启动（默认 127.0.0.1:8000）
python -m uvicorn app:app --host 127.0.0.1 --port 8000

# 3) 自检
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d '{"business_id":"CS-0001"}'
```

无模型 key 也能跑：自动降级（degraded=true），只走规则。

接模型（可选）：设置环境变量后重启
```bash
export MODEL_PROVIDER=cloud        # cloud | local | （空=降级）
export CLOUD_API_KEY=sk-xxx
export CLOUD_BASE_URL=https://...
export CLOUD_MODEL=xxx
# 或用本地：MODEL_PROVIDER=local, LOCAL_API_KEY, LOCAL_BASE_URL, LOCAL_MODEL
```

---

## 4. 三步编排（等价于 LangGraph StateGraph）

| 节点 | 作用 | 引用知识 |
|---|---|---|
| `check_scope` | 校验业务编号是否在授权样本内；越权直接拒绝并留痕 | — |
| `verify_version` | 校验照片元数据、单据版本、重复工单 | K23 复查 / K41 照片元数据 / K42 版本号 |
| `draft_handover` | 生成**建议**交接清单草稿（待人工确认） | K26 交接 / K27 超时升级 |

返回状态：`pending_confirm`（可自动关联）/ `need_human`（转人工）/ `conflict`（版本冲突转裁定）/ `out_of_scope`（越权）。

---

## 5. 红线（不可逾越）

1. 不自动销项 / 不自动判定合格。
2. 不写业务系统、不覆盖原始记录。
3. 模型输出一律标记 `suggestion`，只进"建议"字段，不进状态字段。
4. 不借账号、不做越权操作；越权请求拒绝并审计。
5. 关键动作（确认交接）必须人工在环。

---

## 6. 关联交付物

- 前端展示网站：`D:\施工隐患\site\`（前四阶段业务分析 / 需求发现成果）
- 阶段报告：`D:\施工隐患\`（业务挖掘 / 现场调研 / 需求定义 / 方案设计）
- 接口与评估详情：**API.md**
- 范围、限制与未核实项：**DELIVERY.md**

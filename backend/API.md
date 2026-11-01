# API 契约与真实示例

> 全部请求/返回均为本机 `127.0.0.1:8000` 真实跑过（模型模式 none → degraded=true，仅走规则）。
> 时间字段为运行时生成，示例中以 `…` 略去毫秒级差异，其余字段与线上一致。

---

## 接口总览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 + 模型降级状态 |
| GET | `/api/business` | 业务单列表（摘要） |
| GET | `/api/business/{id}` | 单笔业务 + 关联照片/交接/审计 |
| POST | `/api/run` | 三步编排跑一笔业务（越权 403 / 幂等） |
| POST | `/api/confirm` | 人工确认交接（红线条：必须人工） |
| GET | `/api/handover` | 交接清单：待确认 / 已确认 |
| GET | `/api/audit` | 审计日志（六字段，倒序） |
| POST | `/api/search` | 知识库检索（BM25+二元组+图谱一跳） |
| GET | `/api/eval` | 5 套评估集（真跑） |

---

## 1) GET /api/health

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{"ok":true,"model":"none","degraded":true}
```

> `degraded:true` 表示未配置模型 key，仅规则模式，接口照常可用。

---

## 2) GET /api/business

```bash
curl http://127.0.0.1:8000/api/business
```

```json
[
  {"business_id":"CS-0001","event_time":"2026-10-15T09:20:00","area_code":"A3","level":"中","status":"整改中","version":"v3"},
  {"business_id":"CS-0002","event_time":"2026-10-15T09:20:00","area_code":"A1","level":"高","status":"整改中","version":"v3"},
  ...
]
```
（共 100 条；含脏数据：CS-0003/0004、CS-0009/0010/0011、CS-0015/0016 重复、CS-0022/0023 重复；CS-0007、CS-0021 缺照片元数据；CS-0013、CS-0019、CS-0024 版本冲突；CS-0020、CS-0025 状态反复。）

---

## 3) GET /api/business/{id}

```bash
curl http://127.0.0.1:8000/api/business/CS-0007
```

```json
{
  "business":{
    "business_id":"CS-0007","title":"电梯井洞口防护不到位","event_time":"2026-10-15T09:20:00",
    "area_code":"C2","level":"中","status":"整改中","version":"v3",
    "photo_ids":["P-0011","P-0012"],"alt_versions":[],"flags":[]
  },
  "photos":[
    {"photo_id":"P-0011","photo_time":null,"photo_location":"C2","uploader":"林亦舟","attach_to":"CS-0007"},
    {"photo_id":"P-0012","photo_time":"2026-10-15T09:30:00","photo_location":null,"uploader":"林亦舟","attach_to":"CS-0007"}
  ],
  "handover":[],"audit":[]
}
```

> 注意 `P-0011` 缺 `photo_time`、`P-0012` 缺 `photo_location`——这正是脏数据，编排会据此转人工，不猜不补。

---

## 4) POST /api/run（核心三步编排）

请求体：`{"business_id": "CS-xxxx"}`

### 路径 A · 正常 → pending_confirm（CS-0001）

```bash
curl -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d '{"business_id":"CS-0001"}'
```

```json
{
  "business_id":"CS-0001",
  "status":"pending_confirm",
  "trace":[
    {"node":"check_scope","durationMs":0.0,"result":{"in_scope":true,"business":{...}}},
    {"node":"verify_version","durationMs":9.3,"result":{
      "status":"ok",
      "associate":{"matched":true,"insufficient":false,"matched_photos":["P-0001","P-0002"]},
      "version":{"conflict":false,"flip":false,"versions":[]},
      "duplicate":{"duplicate":false,"group":[]},
      "reasons":[],
      "citations":[
        {"id":"K23","title":"复查","source":"f50"},
        {"id":"K41","title":"照片元数据","source":"f33"},
        {"id":"K42","title":"版本号","source":"f24"}
      ]
    }},
    {"node":"draft_handover","durationMs":10.5,"result":{
      "handover_id":"HO-CS-0001","business_id":"CS-0001",
      "from_role":"巡查员","to_role":"整改协调员",
      "items":["隐患：楼梯口防护栏杆缺失（等级 中）","责任区域：A3","关联照片：P-0001,P-0002","当前状态：整改中（版本 v3）"],
      "unresolved_items":[],
      "note":"以下为系统【建议(suggestion)】草稿，须人工确认后方可导出交接清单；不自动批准、不写业务系统。",
      "citations":[{"id":"K26","title":"交接","source":"f23"},{"id":"K27","title":"超时升级","source":"f25"}]
    }}
  ],
  "draft":{"handover_id":"HO-CS-0001","from_role":"巡查员","to_role":"整改协调员","items":[...],"unresolved_items":[],"note":"...","citations":[{"id":"K26",...},{"id":"K27",...}]},
  "reasons":null,"versions":null,
  "citations":[
    {"id":"K23","title":"复查","source":"f50"},
    {"id":"K41","title":"照片元数据","source":"f33"},
    {"id":"K42","title":"版本号","source":"f24"},
    {"id":"K26","title":"交接","source":"f23"},
    {"id":"K27","title":"超时升级","source":"f25"}
  ],
  "degraded":true
}
```

> 状态 `pending_confirm`：规则齐全，产出**建议**交接草稿，等人工确认。`citations` 带 `id`+`source`，可追溯。
> **落库行为（REQ-03 卡点真实闭环）**：`/api/run` 在返回草稿的同时，会将该草稿以 `handover_id`（形如 `HO-{business_id}`）落库到 `data/handover.json` 的**待确认**列表（`confirmed_by` 为空）。这样后续 `POST /api/confirm {handover_id}` 才能真实命中并完成人工确认——日常路径 `run → confirm` 是通的，并非只停留在响应体。已存在同名 `handover_id` 则跳过，不覆盖原始记录（红线）。

### 路径 B · 脏数据 → need_human（CS-0007）

```bash
curl -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d '{"business_id":"CS-0007"}'
```

```json
{
  "business_id":"CS-0007","status":"need_human",
  "trace":[{"node":"check_scope",...},{"node":"verify_version","durationMs":2.5,"result":{
    "status":"need_human",
    "associate":{"matched":false,"insufficient":true,"missing":["P-0011","P-0012"]},
    "version":{"conflict":false,"flip":false,"versions":[]},
    "duplicate":{"duplicate":false,"group":[]},
    "reasons":["照片元数据缺失：P-0011,P-0012 缺时间或位置，不猜不补，进人工修复队列"],
    "citations":[{"id":"K23","title":"复查","source":"f50"},{"id":"K41","title":"照片元数据","source":"f33"},{"id":"K42","title":"版本号","source":"f24"}]
  }}],
  "draft":null,
  "reasons":["照片元数据缺失：P-0011,P-0012 缺时间或位置，不猜不补，进人工修复队列"],
  "versions":null,
  "citations":[{"id":"K23",...},{"id":"K41",...},{"id":"K42",...}],
  "degraded":true
}
```

> `draft:null`，不臆造交接单；明确告知缺哪些照片、进人工修复队列。

### 路径 C · 版本冲突 → conflict（CS-0013）

```bash
curl -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d '{"business_id":"CS-0013"}'
```

```json
{
  "business_id":"CS-0013","status":"conflict",
  "trace":[{"node":"check_scope",...},{"node":"verify_version","durationMs":10.4,"result":{
    "status":"conflict",
    "associate":{"matched":true,"insufficient":false,"matched_photos":["P-0021"]},
    "version":{"conflict":true,"flip":false,"versions":[{"version":"v3","status":"整改中"},{"version":"v2","status":"已销项"}]},
    "duplicate":{"duplicate":false,"group":[]},
    "reasons":["单据版本冲突：存在 alt_versions，两版并列、不合并（附总监裁定）"],
    "citations":[{"id":"K23",...},{"id":"K41",...},{"id":"K42",...}]
  }}],
  "draft":null,
  "reasons":["单据版本冲突：存在 alt_versions，两版并列、不合并（附总监裁定）"],
  "versions":[{"version":"v3","status":"整改中"},{"version":"v2","status":"已销项"}],
  "citations":[{"id":"K23",...},{"id":"K41",...},{"id":"K42",...}],
  "degraded":true
}
```

> 第二例冲突 CS-0019 同样返回 `conflict`，其 `versions` 为 `[{v3:整改中},{v1:已销项}]`。两版并列、不合并，须附总监裁定。

### 越权 → 403 + 审计留痕

```bash
curl -i -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d '{"business_id":"CS-9999"}'
# HTTP/1.1 403 Forbidden
# {"detail":"out_of_scope / 越权：业务编号不在授权样本内"}
```

> 同时写入审计：`{"action":"check_scope","rule_hit":"out_of_scope","business_id":"CS-9999","human_override":"rejected_403",...}`

### 幂等：重复请求 → duplicate:true

```bash
# 同一 business_id 在 300s 内第二次 POST
curl -X POST http://127.0.0.1:8000/api/run -H "Content-Type: application/json" -d '{"business_id":"CS-0001"}'
# => {"business_id":"CS-0001","status":"pending_confirm", ..., "duplicate":true}
```

---

## 5) POST /api/confirm（人工确认，红线动作）

请求体：`{"handover_id":"H-xxxx","confirmed_by":"姓名","action":"approve|revise","changes":{...}}`

```bash
curl -X POST http://127.0.0.1:8000/api/confirm -H "Content-Type: application/json" \
  -d '{"handover_id":"H-0002","confirmed_by":"赵明哲","action":"approve"}'
```

```json
{"ok":true,"final":true,"handover":{"handover_id":"H-0002","from_role":"整改协调员","to_role":"总监理工程师","unresolved_items":[],"confirmed_by":"赵明哲","confirmed_at":"2026-11-02T01:40:17","action":"approve"}}
```

> 仅"已确认"，由人工在环完成；系统不替人批准、不写业务系统。确认后该单从 pending 移入 confirmed。

---

## 6) GET /api/handover

```bash
curl http://127.0.0.1:8000/api/handover
```

```json
{
  "pending":[{"handover_id":"H-0002","from_role":"整改协调员","to_role":"总监理工程师","unresolved_items":[],"confirmed_by":null,"confirmed_at":null}],
  "confirmed":[{"handover_id":"H-0001","from_role":"巡查员","to_role":"整改协调员","unresolved_items":["照片定位待核"],"confirmed_by":"唐映秋","confirmed_at":"2026-10-15T10:00:00"}]
}
```

> 未确认（H-0002）绝不出现在 confirmed 列表——满足人工确认集要求。

---

## 7) GET /api/audit

```json
[
  {"action":"run_result","actor":"system","rule_hit":"pending_confirm","model_suggestion":"degraded","human_override":"","signer":"","at":"...","business_id":"CS-0001"},
  {"action":"draft_handover","actor":"system","rule_hit":"pending_confirm","model_suggestion":"suggestion","human_override":"","signer":"","at":"...","business_id":"CS-0001"},
  {"action":"verify_version","actor":"system","rule_hit":"ok","model_suggestion":"","human_override":"","signer":"","at":"...","business_id":"CS-0001"},
  {"action":"run_result","actor":"system","rule_hit":"conflict","model_suggestion":"degraded","human_override":"","signer":"","at":"...","business_id":"CS-0013"},
  ...
]
```

> 六字段齐全：`action / actor / rule_hit / model_suggestion / human_override / signer`（外加 `at`,`business_id`）。

---

## 8) POST /api/search

请求体：`{"q":"关键词"}`

```bash
curl -X POST http://127.0.0.1:8000/api/search -H "Content-Type: application/json" -d '{"q":"消防通道"}'
```

```json
{
  "q":"消防通道",
  "results":[
    {"score":9.39,"id":"K06","title":"动火作业与消防","content":"动火作业须办证、清理周边可燃物、配灭火器，并有监护人。","source":"通用安全常识，具体条文待核","topic":"隐患识别","related":[...]},
    {"score":3.44,"id":"K82","title":"返工次数","content":"退回重报次数 / 隐患总数；...","source":"f51 f53","topic":"指标验收","related":[...]},
    {"score":3.08,"id":"K08","title":"机械设备防护","content":"机械传动部位须有防护罩，检修须断电挂牌。","source":"通用安全常识，具体条文待核","topic":"隐患识别","related":[...]},
    {"score":2.71,"id":"K01","title":"临边防护缺失与反复","content":"临边防护缺失是高处坠落的主要风险。...上午补装、下午因搬运材料被拆除，导致销项状态与实际不符。","source":"f11","topic":"隐患识别","related":[...]},
    {"score":2.6,"id":"K26","title":"交接","content":"交接须含业务编号、当前版本、处理状态、未解决事项、接手人；对方确认接手才算交接完成，仅发送消息不算。","source":"f23","topic":"整改流程","related":[...]}
  ]
}
```

> 每条结果带 `id` + `source` + `content`，可追溯至事实库（f11 / f23 / f33 / f24 / f50 / f25 等）。

---

## 9) GET /api/eval（5 套评估集，真跑）

```bash
curl http://127.0.0.1:8000/api/eval
```

```json
[
  {"suite":"回放集","total":100,"passed":84,"failed":16,"rate":84.0,"threshold":0.8,"meets":true,"evidence":"自动关联率=84/100=84.0%，阈值≥80%→达标；转人工13笔(CS-0003,CS-0004,CS-0007,CS-0009,CS-0010,CS-0011,CS-0015,CS-0016,CS-0020,CS-0021,CS-0022,CS-0023,CS-0025)；版本冲突3笔(CS-0013,CS-0019,CS-0024)"},
  {"suite":"口径集","total":2,"passed":2,"failed":0,"evidence":"交接字段含 f23 五要素：2/2"},
  {"suite":"异常集","total":4,"passed":4,"failed":0,"evidence":"四类异常均转人工/降级：通过"},
  {"suite":"人工确认集","total":2,"passed":2,"failed":0,"evidence":"真实路径：POST /api/run(CS-0002)→草稿HO-CS-0002 已落库待确认=是 → POST /api/confirm → 已确认列表含该id=是 且不在待确认=是；通过"},
  {"suite":"审计集","total":1,"passed":1,"failed":0,"evidence":"CS-0001 审计记录六字段齐全：是（命中 9 条）"}
]
```

> 回放集对 **100 条历史隐患**全量跑三步编排：自动关联（pending_confirm）**84/100 = 84.0%**，满足阶段四方案约定的「自动关联率 ≥80%」阈值（eval 返回 `meets:true`）。
> 16 笔转人工/冲突为**设计预期**：其中 11 笔为种子集脏数据（重复/缺元数据/版本冲突/状态反复），5 笔为扩展集新增脏数据（CS-0021 缺元数据、CS-0022/0023 重复、CS-0024 版本冲突、CS-0025 状态反复）。脏数据按规则应转人工或裁定，而非自动关联——这是"规则先做、模型补缝"的体现，非缺陷。
>
> **人工确认集走真实日常路径（2/2）**：不依赖 `data/handover.json` 初始态。用例内 `POST /api/run` 生成草稿并由 `/api/run` **真实落库为待确认**（`_persist_draft_if_pending`），再 `POST /api/confirm`（与接口同一 `confirm` 函数）→ 断言"已确认列表含该 handover_id 且不在待确认列表"。这同时验证了 REQ-03"未确认不得标记完成"卡点的**真实闭环**，而非仅文档声明。即使把 `handover.json` 清空，该用例仍 2/2 通过；用例结尾自动还原 `handover.json`，不影响口径集与重复执行。
> 历史修正：早期 `/api/run` 只返回草稿、不落库，导致 `run → confirm` 日常路径断裂（confirm 404），属**产品缺陷**；现已让 run 落库为 pending，校验通过（HTTP 200 且 `/api/handover` 可查到 `confirmed_by`）。

---

## 脚本演示：`python scripts/demo.py`

输出三条路径（正常 / 脏数据 / 冲突），每路径含状态、降级标志、原因、引用知识（K23/K41/K42/K26/K27）与步骤耗时。详见 `DELIVERY.md` 的"自检"章节与 `.demo_output.txt`。

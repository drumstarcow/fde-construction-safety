# 接口说明

后端为 FastAPI，启动后可在 `/docs` 交互调试。所有接口返回 JSON；
模型不可用时 `/api/health` 返回 `degraded: true`，其余接口仍可用（走规则）。

## 1. 健康检查

```
GET /api/health
→ {"ok": true, "model": "none", "degraded": true}
```

## 2. 业务

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/business` | 业务列表（id、时间、区域、等级、版本、照片数） |
| GET | `/api/business/{business_id}` | 单笔业务 + 关联照片 |
| POST | `/api/run` | 跑三步编排，body：`{"business_id": "CS-0001"}` |

`/api/run` 返回：

```json
{
  "status": "pending_confirm | need_human | out_of_scope",
  "trace": [{"node": "check_scope", "result": "in_scope", "durationMs": 0}],
  "draft": {"handover_id": "HO-...", "from_role": "...", "to_role": "..."},
  "reasons": ["照片缺时间或位置：P-0003"],
  "citations": [{"id": "K26", "title": "交接", "source": "f23"}]
}
```

## 3. 人工确认

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/confirm` | body：`{"handover_id": "...", "confirmed_by": "唐映秋"}`；未确认的记录不出现在已确认列表 |
| GET | `/api/handover` | 交接清单（含 confirmed_by / confirmed_at） |

## 4. 审计

```
GET /api/audit
→ 时间倒序，六字段：action, actor, rule_hit, model_suggestion, human_override, signer
```

越权请求（编号不在授权样本内）返回 **403** 并写审计——这是红线要求，不是故障。

## 5. 知识与图谱

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/kb` | 49 条知识条目（id / 主题 / 内容 / 来源 / 关联标签） |
| GET | `/api/graph` | 89 节点 / 278 关系全图 |
| GET | `/api/graph?focus=K22&layers=1` | 以 K22 为中心 N 跳子图（实测 8 节点 / 14 关系） |
| POST | `/api/search` | body：`{"q": "交接要包含什么"}`；返回带 source 的条目 |

检索命中后沿图谱做一跳扩展，`related` 字段列出邻居关系。

## 6. 评估

```
GET /api/eval
→ 回放集 100 笔（84% 关联率，阈值 80%，meets:true）、口径集 2/2、异常集 4/4、
  人工确认集 2/2、审计集 1/1
```

## 错误约定

| 状态码 | 含义 |
|---|---|
| 400 | 参数或状态不合法 |
| 403 | 越权（同时写审计） |
| 404 | 资源不存在 |

## 前端对接

`web/index.html` 通过 CORS 直连本服务，默认地址 `http://127.0.0.1:8010`。

# 更新记录

本项目遵循「日期 + 变更」的记法，只记对外可见的变化。

## 2026-11-02
- 按标准项目结构重排：`backend/` → `src/safety_backend/`，补 LICENSE / .gitignore / tests / scripts / config。
- 方案设计文档更新评估结果：回放集扩至 100 笔，自动关联率 84%（阈值 ≥80%，meets:true）。
- 九阶段报告导出并入库：`docs/报告/`（总报告 + 9 份分报告）。

## 2026-11-02（二）
- 目录严格对齐标准框架：`rules/ model/ orchestrator/` 收进 `core/`，`audit/` 收进 `utils/`；
  新增 `main.py` 入口、`__init__.py`、`docs/design.md`、`docs/api.md`、`CONTRIBUTING.md`、
  `scripts/build.sh`、`scripts/deploy.sh`、ISSUE 与 PR 模板。
- 清理 `.pytest_cache/`、`__pycache__` 等不应入库的文件。
- 复测：四个只读接口 + `/api/run` + `/api/search` 全部通过。

## 2026-11-01
- 完成阶段一至阶段五的 FDE 训练记录，导出各阶段报告。
- 后端交付：九个接口 + 三步编排 + 规则层 + 降级模型层 + 六字段审计。

## 2026-10-31
- 知识库定稿 49 条，图谱 89 节点 / 278 关系。
- 检索层：BM25 + 字符二元组 + 图谱一跳扩展。
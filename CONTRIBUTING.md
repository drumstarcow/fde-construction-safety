# 贡献说明

本项目是课程作业，暂不接受外部 PR；保留此文件是为了符合标准项目结构。

本地修改流程：

1. `git clone` 后 `pip install -r requirements.txt`
2. 改完跑 `bash scripts/check.sh`（语法 + 冒烟测试，不需要模型 key）
3. 提交前确认没有把 `.env`、`outputs/`、`.pytest_cache/` 带进去

## 代码约定

- 规则层与模型层不混写：确定性判断放 `rules/`，需要语义判断的才进 `model/`
- 任何写数据的地方都要同时写审计（六字段）
- 新增接口请同步更新 `docs/api.md`

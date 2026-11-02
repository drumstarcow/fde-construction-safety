#!/usr/bin/env bash
# 交前自检：语法 + 冒烟测试
set -e
cd "$(dirname "$0")/.."
python -m compileall -q src/safety_backend
echo "语法检查通过"
python -m pytest tests -q

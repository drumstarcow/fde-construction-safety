#!/usr/bin/env bash
# 构建检查：语法编译 + AST 解析（不产出制品，纯校验）
set -e
cd "$(dirname "$0")/.."
echo "[1/2] 语法编译"
python3 -m compileall -q src/safety_backend
echo "[2/2] AST 解析"
python3 scripts/_astcheck.py
echo "构建检查通过"

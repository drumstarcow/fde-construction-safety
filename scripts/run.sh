#!/usr/bin/env bash
# 启动后端（开发用）
set -e
cd "$(dirname "$0")/.."
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --app-dir src/safety_backend

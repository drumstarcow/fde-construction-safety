#!/usr/bin/env bash
# 本地/内网部署：后台起服务 + 健康检查
set -e
cd "$(dirname "$0")/.."
PORT="${PORT:-8010}"
HOST="${HOST:-127.0.0.1}"
mkdir -p outputs
echo "启动服务 $HOST:$PORT"
nohup python3 -m uvicorn app:app --host "$HOST" --port "$PORT" --app-dir src/safety_backend > outputs/server.log 2>&1 &
echo $! > outputs/server.pid
sleep 3
if curl -sf "http://$HOST:$PORT/api/health" > /dev/null; then
  echo "健康检查通过：http://$HOST:$PORT/docs"
else
  echo "启动失败，看 outputs/server.log"
  exit 1
fi

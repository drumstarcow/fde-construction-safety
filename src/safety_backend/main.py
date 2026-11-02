"""程序入口：python -m safety_backend.main

等价于：uvicorn app:app --host 127.0.0.1 --port 8010 --app-dir src/safety_backend
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8010"))
    print("启动：http://%s:%d  接口文档：http://%s:%d/docs" % (host, port, host, port))
    uvicorn.run("app:app", host=host, port=port, app_dir=HERE)

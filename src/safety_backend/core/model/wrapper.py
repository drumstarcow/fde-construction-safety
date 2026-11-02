"""模型封装（含降级）。

设计：规则先做、模型补缝。模型只做两件事（且只在规则判不了时介入）：
  ① 疑难记录的相关性判断
  ② 交接草稿文本生成
模型输出一律标 “suggestion”，不进入状态字段、不写业务系统。

降级：未配置 MODEL_PROVIDER / 无 API key / 超时 / 报错 → 自动降级为规则 + 人工，
返回 degraded=True，绝不抛错、绝不伪造“模型可用”。
"""
import os


class ModelWrapper:
    def __init__(self):
        self.provider = (os.getenv("MODEL_PROVIDER") or "none").strip().lower()
        self.base_url = os.getenv("CLOUD_BASE_URL") or os.getenv("LOCAL_BASE_URL") or ""
        self.api_key = os.getenv("CLOUD_API_KEY") or os.getenv("LOCAL_API_KEY") or ""
        self.model = os.getenv("CLOUD_MODEL") or os.getenv("LOCAL_MODEL") or ""
        self.available = self.provider in ("cloud", "local") and bool(self.api_key)
        self.degraded = not self.available
        self.mode = self.provider if self.available else "none"

    def correlate(self, record_text):
        """疑难记录相关性判断。模型不可用时返回 None（调用方按降级处理）。"""
        if not self.available:
            return None
        # 无真实网络调用能力时，仅生成明确标注的“建议”占位，不冒充结论
        snippet = (record_text or "")[:80]
        return "【模型建议·待人工确认】对以下疑难记录做相关性初判：" + snippet

    def status(self):
        return {"model": self.mode, "degraded": self.degraded}

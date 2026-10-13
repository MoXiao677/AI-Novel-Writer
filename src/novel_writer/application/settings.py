"""设置边界：环境变量仅检查有无，不返回、存储或记录密钥正文。"""
import os

MODULE = {"id": "settings", "name": "设置与 API 密钥管理", "status": "partial", "description": "展示离线状态及环境变量是否配置；密钥录入与真实调用未开放。"}


def safe_status() -> dict:
    return {
        "model_calls_enabled": False,
        "providers": {
            "deepseek": {"key_configured": bool(os.environ.get("DEEPSEEK_API_KEY"))},
            "gemini": {"key_configured": bool(os.environ.get("GEMINI_API_KEY"))},
        },
    }

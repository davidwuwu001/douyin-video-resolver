"""配置管理

从环境变量或 .env 文件加载配置。
"""

import os


class Config:
    """应用配置，从环境变量读取"""

    # 火山引擎 - 音视频字幕生成
    VOLC_APP_ID: str = os.environ.get("VOLC_APP_ID", "")
    VOLC_ACCESS_TOKEN: str = os.environ.get("VOLC_ACCESS_TOKEN", "")

    # 后续扩展：大模型 API Key、飞书配置等
    # LLM_API_KEY: str = os.environ.get("LLM_API_KEY", "")
    # FEISHU_APP_ID: str = os.environ.get("FEISHU_APP_ID", "")
    # FEISHU_APP_SECRET: str = os.environ.get("FEISHU_APP_SECRET", "")

    @classmethod
    def is_transcribe_enabled(cls) -> bool:
        """转写功能是否已配置"""
        return bool(cls.VOLC_APP_ID and cls.VOLC_ACCESS_TOKEN)

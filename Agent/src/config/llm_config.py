"""
LLM 配置管理 — 多平台支持，OpenAI 兼容接口

支持平台:
  - zhipu:   智谱 AI GLM-4-Flash (推荐，永久免费)
  - doubao:  火山引擎豆包 (200万 Token/天免费)
  - qwen:    阿里百炼通义千问 (1000万 Token 免费)
  - deepseek: DeepSeek V4-Flash (极低价)
  - openai:  标准 OpenAI / 其他兼容接口

使用方式:
  from config.llm_config import get_llm
  llm = get_llm()  # 从环境变量自动识别平台
"""

import os
import logging
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# 平台预设（OpenAI 兼容 Base URL）
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "model": "glm-4-flash",
        "description": "智谱 AI GLM-4-Flash (永久免费, 200K上下文)",
    },
    "doubao": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-1-6-lite-250815",
        "description": "火山引擎豆包 Seed-1.6-Lite (200万Token/天免费)",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "description": "阿里百炼通义千问 Qwen-Plus (1000万Token免费)",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "description": "DeepSeek V4-Flash (100万Token/月免费, 极低价)",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "description": "OpenAI 标准接口 / 其他兼容服务",
    },
}


def get_llm_config() -> dict:
    """
    从环境变量读取 LLM 配置，返回 dict。

    环境变量:
      LLM_PROVIDER:  zhipu | doubao | qwen | deepseek | openai (默认 zhipu)
      LLM_API_KEY:   API Key (必填)
      LLM_BASE_URL:  自定义 Base URL (可选，覆盖预设)
      LLM_MODEL:     模型名称 (可选，覆盖预设)
      LLM_TEMPERATURE: 温度 (默认 0.7)
      LLM_MAX_TOKENS:  最大输出 Token (默认 4096)
    """
    provider = os.getenv("LLM_PROVIDER", "zhipu").lower()
    if provider not in PROVIDER_PRESETS:
        logger.warning(
            f"未知 LLM_PROVIDER='{provider}'，可用: {list(PROVIDER_PRESETS.keys())}。"
            f"将使用 'zhipu' 作为默认。"
        )
        provider = "zhipu"

    preset = PROVIDER_PRESETS[provider]

    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", preset["base_url"])
    model = os.getenv("LLM_MODEL", preset["model"])

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "provider": provider,
        "temperature": float(os.getenv("LLM_TEMPERATURE", "0.7")),
        "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
    }


def get_llm() -> ChatOpenAI:
    """
    工厂函数：返回配置好的 ChatOpenAI 实例。

    使用 OpenAI 兼容接口，可对接智谱/豆包/千问/DeepSeek 等平台。
    """
    cfg = get_llm_config()

    if not cfg["api_key"]:
        logger.warning(
            "LLM_API_KEY 未设置！Agent 将无法调用 LLM。\n"
            "请设置环境变量: export LLM_API_KEY=your_api_key\n"
            f"获取 Key: {_get_key_url(cfg['provider'])}"
        )

    logger.info(
        f"LLM 配置: provider={cfg['provider']}, model={cfg['model']}, "
        f"base_url={cfg['base_url']}"
    )

    return ChatOpenAI(
        model=cfg["model"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        temperature=cfg["temperature"],
        max_tokens=cfg["max_tokens"],
        streaming=False,
        timeout=120,
    )


def _get_key_url(provider: str) -> str:
    """返回各平台的 API Key 获取地址"""
    urls = {
        "zhipu": "https://open.bigmodel.cn/ (注册后免费获取)",
        "doubao": "https://console.volcengine.com/ark/ (火山引擎控制台)",
        "qwen": "https://dashscope.aliyun.com/ (阿里云百炼控制台)",
        "deepseek": "https://platform.deepseek.com/ (注册送额度)",
        "openai": "https://platform.openai.com/",
    }
    return urls.get(provider, "")

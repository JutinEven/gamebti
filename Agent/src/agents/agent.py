"""
Gamebti Agent — LangGraph + 免费 LLM
工具注入架构：API 层调用搜索，LLM 只负责阅读理解+格式化
"""

import os
import json
import logging
from langchain.agents import create_agent
from langgraph.graph import MessagesState

from config.llm_config import get_llm
from storage.memory.memory_saver import get_memory_saver

logger = logging.getLogger(__name__)
CONFIG_FILE = "config/agent_llm_config.json"


def _load_config() -> dict:
    """加载 Agent 配置文件"""
    config_path = os.path.join(os.getenv("AGENT_WORKSPACE", "."), CONFIG_FILE)
    if not os.path.exists(config_path):
        logger.warning(f"配置文件 {config_path} 不存在，使用默认配置。")
        return {"system_prompt": "你是 Gamebti，一个专业的游戏智能助手。", "temperature": 0.7, "max_tokens": 4096, "tools": []}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_agent():
    """构建 Agent —— 工具由 API 层注入，LLM 只负责阅读理解"""
    cfg = _load_config()
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT") or cfg.get("system_prompt", "")
    llm = get_llm()
    logger.info(f"构建 Gamebti Agent: model={llm.model_name}")
    return create_agent(
        model=llm, system_prompt=system_prompt, tools=[],
        checkpointer=get_memory_saver(), state_schema=MessagesState,
    )

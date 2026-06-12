"""
Gamebti 智能游戏助手 Agent
基于 LangGraph + 免费 LLM (智谱/豆包/千问/DeepSeek)

架构：LLM + 工具调用 (游戏搜索 + 文档读取)
"""

import os
import json
import logging
from langchain.agents import create_agent
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages

from config.llm_config import get_llm
from storage.memory.memory_saver import get_memory_saver

logger = logging.getLogger(__name__)

# 配置文件路径（相对于项目根目录）
CONFIG_FILE = "config/agent_llm_config.json"

# 消息滑动窗口大小
MAX_MESSAGES = 20


def _load_config() -> dict:
    """加载 Agent 配置文件"""
    config_path = os.path.join(
        os.getenv("AGENT_WORKSPACE", "."), CONFIG_FILE
    )

    if not os.path.exists(config_path):
        logger.warning(
            f"配置文件 {config_path} 不存在，使用默认配置。"
        )
        return {
            "system_prompt": "你是 Gamebti，一个专业的游戏智能助手。",
            "temperature": 0.7,
            "max_tokens": 4096,
            "tools": [],
        }

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _windowed_messages(old: list, new: list) -> list:
    """滑动窗口：只保留最近 MAX_MESSAGES 条消息，控制上下文长度"""
    combined = add_messages(old, new)
    result = list(combined)
    return result[-MAX_MESSAGES:]


class AgentState(MessagesState):
    """Agent 状态，包含消息滑动窗口"""
    pass


def build_agent():
    """
    构建 Gamebti 智能游戏助手 Agent。

    采用「工具注入」架构：
    - 工具调用由 API 层 (main.py) 负责，结果注入到用户消息中
    - LLM 只需阅读理解数据并格式化回答
    - 适用于不支持 Function Calling 的免费模型（如 GLM-4-Flash）

    记忆:
    - 优先 PostgreSQL (设置 PGDATABASE_URL)
    - 否则使用内存模式 (重启后对话丢失)
    """
    cfg = _load_config()

    # 从环境变量/配置文件获取系统提示词
    system_prompt = os.getenv("AGENT_SYSTEM_PROMPT") or cfg.get("system_prompt", "")

    # 获取 LLM 实例
    llm = get_llm()

    logger.info(f"构建 Gamebti Agent: model={llm.model_name}")

    # 不传 tools——工具由 API 层注入，LLM 只负责阅读理解
    return create_agent(
        model=llm,
        system_prompt=system_prompt,
        tools=[],  # 工具注入模式
        checkpointer=get_memory_saver(),
        state_schema=AgentState,
    )


def _load_tools(tool_names: list[str]) -> list:
    """动态加载工具模块"""
    tools = []
    tool_map = {
        "game_search": "tools.game_search",
        "read_document": "tools.read_document",
    }

    for name in tool_names:
        module_path = tool_map.get(name, f"tools.{name}")
        try:
            module = __import__(module_path, fromlist=[name])
            tool_func = getattr(module, name, None)
            if tool_func:
                tools.append(tool_func)
                logger.info(f"已加载工具: {name}")
            else:
                logger.warning(f"模块 {module_path} 中未找到工具函数 '{name}'")
        except ImportError as e:
            logger.warning(f"无法加载工具 '{name}' ({module_path}): {e}")

    return tools

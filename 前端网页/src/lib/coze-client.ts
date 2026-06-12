/**
 * ============================================
 * Gamebti Web Companion - Coze API 客户端
 * ============================================
 * 仅在服务端运行，API Key 不暴露给前端
 * ============================================
 */

import { COZE_CONFIG } from "./constants";
import type { ChatResponse } from "./types";

/**
 * 调用 Coze Agent API 发送消息并获取回复
 * @param message - 用户消息
 * @param conversationId - 可选会话ID（用于多轮对话）
 * @returns Agent 回复
 */
export async function sendToCozeAgent(
  message: string,
  conversationId?: string
): Promise<ChatResponse> {
  const apiKey = process.env.COZE_API_KEY;
  const botId = process.env.COZE_BOT_ID;

  if (!apiKey || !botId) {
    throw new Error("Coze API 未配置。请检查 .env.local 中的 COZE_API_KEY 和 COZE_BOT_ID。");
  }

  const url = `${COZE_CONFIG.BASE_URL}${COZE_CONFIG.API_PATH}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), COZE_CONFIG.TIMEOUT);

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        bot_id: botId,
        user_id: "gamebti-web-user",
        stream: false,
        auto_save_history: true,
        additional_messages: [
          {
            role: "user",
            content: message,
            content_type: "text",
          },
        ],
        ...(conversationId ? { conversation_id: conversationId } : {}),
      }),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorBody = await response.text().catch(() => "无法读取错误响应");
      throw new Error(
        `Coze API 返回错误 (${response.status}): ${errorBody}`
      );
    }

    const data = await response.json();

    // 解析 Coze 响应格式
    // Coze API v3 返回格式: { code: 0, data: { messages: [...], conversation_id: "..." } }
    if (data.code !== 0) {
      throw new Error(`Coze API 错误: ${data.msg || "未知错误"}`);
    }

    const messages = data.data?.messages || [];
    const assistantMessage = messages.find(
      (m: { role: string }) => m.role === "assistant"
    );

    if (!assistantMessage) {
      throw new Error("Agent 未返回有效回复");
    }

    // 构建响应，预留扩展字段
    const chatResponse: ChatResponse = {
      reply:
        typeof assistantMessage.content === "string"
          ? assistantMessage.content
          : JSON.stringify(assistantMessage.content),
      conversationId: data.data.conversation_id || "",
      emotion: assistantMessage.emotion || undefined,
      action: assistantMessage.action || undefined,
      characterState: assistantMessage.character_state || undefined,
    };

    return chatResponse;
  } catch (error) {
    clearTimeout(timeoutId);

    // 分类错误类型
    if (error instanceof DOMException && error.name === "AbortError") {
      const timeoutError = new Error("请求超时，请稍后重试");
      (timeoutError as Error & { code: string }).code = "TIMEOUT";
      throw timeoutError;
    }

    if (error instanceof TypeError && error.message.includes("fetch")) {
      const netError = new Error("网络连接失败，请检查网络后重试");
      (netError as Error & { code: string }).code = "NETWORK_ERROR";
      throw netError;
    }

    throw error;
  }
}

/**
 * 模拟 Coze Agent 响应（用于开发调试，无需配置 API Key）
 * 设置环境变量 COZE_MOCK_MODE=true 启用
 */
export async function mockCozeResponse(
  message: string,
  conversationId?: string
): Promise<ChatResponse> {
  // 模拟网络延迟
  await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 1200));

  const mockReplies: Record<string, string> = {
    游戏攻略: "根据我的数据库，以下是你要的游戏攻略：\n\n## 🎯 第一章：新手入门\n\n1. **优先完成主线任务**，获取基础装备\n2. 建议在**等级达到 10 级后**再探索支线\n3. 注意收集**隐藏道具**，它们会在后期发挥重要作用\n\n> 💡 小提示：善用地图传送功能可以节省大量时间！",
    价格: "## 📊 当前热门游戏价格一览\n\n| 游戏 | 原价 | 折扣价 | 折扣 |\n|------|------|--------|------|\n| 赛博朋克 2077 | ¥298 | ¥149 | -50% |\n| 艾尔登法环 | ¥298 | ¥198 | -34% |\n| 星露谷物语 | ¥48 | ¥29 | -40% |\n| Hades II | ¥98 | ¥78 | -20% |\n\n数据更新时间：刚刚",
    日报: "## 📰 今日游戏日报\n\n### 🔥 热门新闻\n- 《黑神话：悟空》DLC 开发进展更新\n- Steam 夏季特卖将于下周开启\n- 《丝之歌》最新预告片发布\n\n### 📈 数据看点\n- 同时在线峰值：**3,500,000+**\n- 今日新游发布：**12 款**\n\n### 🎮 推荐游戏\n- *Hades II* - Roguelike 新标杆\n- *Palworld* - 宝可梦遇上生存建造",
    剧情: "## 📖 剧情设定解析\n\n### 世界观\n游戏设定在一个**后启示录**风格的开放世界，人类文明在经历\"大崩坏\"后重建。\n\n### 主要势力\n- **? 联合政府**：以秩序和科技为核心\n- **? 自由联盟**：崇尚个人自由与自然力量\n- **? 神秘教会**：掌握着远古秘密\n\n> 每个势力的选择都会影响结局走向。",
  };

  let reply =
    "感谢你的提问！这是一个很好的游戏相关问题。\n\n由于当前处于**模拟模式**，我无法连接到真实的游戏数据库。请在部署时配置 Coze API 以获得完整体验。\n\n> 🔧 提示：在 .env.local 中设置 COZE_API_KEY 和 COZE_BOT_ID 即可启用真实 Agent。";

  for (const [keyword, mockReply] of Object.entries(mockReplies)) {
    if (message.includes(keyword)) {
      reply = mockReply;
      break;
    }
  }

  return {
    reply,
    conversationId: conversationId || `mock-conv-${Date.now()}`,
    emotion: "happy",
    action: "talk",
    characterState: "speaking",
  };
}

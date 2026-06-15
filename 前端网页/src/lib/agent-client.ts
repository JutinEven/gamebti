/**
 * ============================================
 * Gamebti Web Companion - Agent API 客户端
 * ============================================
 * 仅在服务端运行，调用自部署的 LangGraph Agent 后端
 * Agent 后端提供 OpenAI 兼容的 /v1/chat/completions 接口
 * ============================================
 */

import { AGENT_CONFIG } from "./constants";
import type { ChatResponse } from "./types";

/** 生成 UUID v4（用于 session_id） */
function generateUUID(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * 调用自部署 Agent 后端发送消息并获取回复
 *
 * 使用 Agent 的 OpenAI 兼容接口 /v1/chat/completions。
 * session_id 映射到 Agent 内部的 thread_id，实现多轮对话记忆。
 *
 * @param message - 用户消息
 * @param conversationId - 可选会话ID（用于多轮对话，映射为 session_id）
 * @returns Agent 回复
 */
export async function sendToAgent(
  message: string,
  conversationId?: string,
  fileContext?: string
): Promise<ChatResponse> {
  const sessionId = conversationId || generateUUID();
  const url = `${AGENT_CONFIG.BASE_URL}${AGENT_CONFIG.API_PATH}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), AGENT_CONFIG.TIMEOUT);

  try {
    const body: Record<string, unknown> = {
      model: "gamebti",
      messages: [{ role: "user", content: message }],
      stream: false,
      session_id: sessionId,
    };
    if (fileContext) body.file_context = fileContext;

    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errMsg = `Agent 返回错误 (${response.status})`;
      let errCode = "AGENT_ERROR";

      try {
        const errorData = await response.json();
        // OpenAI 兼容错误格式: { error: { message, type, code } }
        if (errorData?.error?.message) {
          errMsg = errorData.error.message;
        }
        if (errorData?.error?.code) {
          errCode = errorData.error.code;
        }
      } catch {
        // 无法解析错误响应体，使用默认错误信息
      }

      throw Object.assign(new Error(errMsg), { code: errCode });
    }

    const data = await response.json();

    // 解析 OpenAI 兼容响应格式:
    // { choices: [{ message: { role, content } }] }
    const reply =
      data.choices?.[0]?.message?.content || "";

    return {
      reply,
      conversationId: sessionId,
      // 预留扩展字段（Agent 工具结果可能包含情绪/状态信息）
      emotion: data.emotion || undefined,
      action: data.action || undefined,
      characterState: data.characterState || undefined,
    };
  } catch (error) {
    clearTimeout(timeoutId);

    // 分类错误类型（与 coze-client 保持一致）
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

    // 已有 code 的错误（如上面的非 2xx 响应）直接抛出
    throw error;
  }
}

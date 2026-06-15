/**
 * ============================================
 * Gamebti Web Companion - Chat API Route
 * ============================================
 * Next.js API Route: POST /api/chat
 *
 * 架构: 浏览器 -> Next.js API -> Agent 后端 / Coze API (按 AGENT_PROVIDER 选择)
 * API Key 仅在服务端使用，不暴露给前端
 * ============================================
 */

import { NextRequest, NextResponse } from "next/server";
import { sendToCozeAgent, mockCozeResponse } from "@/lib/coze-client";
import { sendToAgent } from "@/lib/agent-client";
import { MESSAGE_CONFIG, CURRENT_PROVIDER } from "@/lib/constants";
import type { ChatRequest, ChatErrorResponse } from "@/lib/types";

/**
 * POST /api/chat
 * 接收用户消息，调用 Coze Agent，返回回复
 */
export async function POST(request: NextRequest) {
  try {
    // 解析请求体
    let body: ChatRequest;
    try {
      body = await request.json();
    } catch {
      return NextResponse.json<ChatErrorResponse>(
        {
          error: "请求格式无效",
          code: "INVALID_REQUEST",
          detail: "请确保请求体为有效 JSON",
        },
        { status: 400 }
      );
    }

    const { message, conversationId } = body;

    // 空消息拦截
    if (!message || typeof message !== "string" || message.trim().length === 0) {
      return NextResponse.json<ChatErrorResponse>(
        {
          error: MESSAGE_CONFIG.EMPTY_MESSAGE,
          code: "INVALID_REQUEST",
          detail: "消息内容为空",
        },
        { status: 400 }
      );
    }

    // 消息长度限制
    if (message.length > MESSAGE_CONFIG.MAX_LENGTH) {
      return NextResponse.json<ChatErrorResponse>(
        {
          error: `消息过长，最多支持 ${MESSAGE_CONFIG.MAX_LENGTH} 字符`,
          code: "INVALID_REQUEST",
          detail: `消息长度 ${message.length} 超过限制 ${MESSAGE_CONFIG.MAX_LENGTH}`,
        },
        { status: 400 }
      );
    }

    // 选择后端提供商：Mock > Agent > Coze
    const isMockMode = process.env.COZE_MOCK_MODE === "true";

    let chatResponse;
    if (isMockMode) {
      chatResponse = await mockCozeResponse(message.trim(), conversationId);
    } else if (CURRENT_PROVIDER === "agent") {
      chatResponse = await sendToAgent(message.trim(), conversationId, body.fileContext);
    } else {
      chatResponse = await sendToCozeAgent(message.trim(), conversationId);
    }

    return NextResponse.json(chatResponse, { status: 200 });
  } catch (error) {
    const err = error as Error & { code?: string };
    console.error("[Chat API] 错误:", err.message);

    // 根据错误类型返回不同状态码
    switch (err.code) {
      case "TIMEOUT":
        return NextResponse.json<ChatErrorResponse>(
          {
            error: "请求超时，请稍后重试",
            code: "TIMEOUT",
            detail: err.message,
          },
          { status: 504 }
        );
      case "NETWORK_ERROR":
        return NextResponse.json<ChatErrorResponse>(
          {
            error: "网络连接失败，请检查网络后重试",
            code: "NETWORK_ERROR",
            detail: err.message,
          },
          { status: 502 }
        );
      default:
        return NextResponse.json<ChatErrorResponse>(
          {
            error: "服务暂时不可用，请稍后重试",
            code: "AGENT_ERROR",
            detail:
              process.env.NODE_ENV === "development" ? err.message : undefined,
          },
          { status: 500 }
        );
    }
  }
}

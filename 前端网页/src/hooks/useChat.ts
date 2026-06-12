"use client";

/**
 * ============================================
 * Gamebti Web Companion - useChat Hook
 * ============================================
 * 聊天状态管理，处理消息发送、API调用、错误处理
 * 纯 React Hook，不依赖 Redux 等外部状态管理
 * ============================================
 */

import { useState, useCallback, useRef } from "react";
import type { Message, MessageRole, MessageStatus, Emotion, CharacterState } from "@/lib/types";
import { MESSAGE_CONFIG } from "@/lib/constants";

/** 生成唯一ID */
function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/** Hook 返回值 */
export interface UseChatReturn {
  messages: Message[];
  isSending: boolean;
  error: string | null;
  conversationId: string | null;
  emotion: Emotion | null;
  characterState: CharacterState | null;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  clearError: () => void;
}

/**
 * 聊天状态管理 Hook
 * @param initialMessages - 初始消息列表（如欢迎消息）
 */
export function useChat(initialMessages: Message[] = []): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [emotion, setEmotion] = useState<Emotion | null>(null);
  const [characterState, setCharacterState] = useState<CharacterState | null>(null);

  const conversationIdRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  /** 发送消息 */
  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || isSending) return;

      // 清空之前的错误
      setError(null);

      // 创建用户消息
      const userMessage: Message = {
        id: generateId(),
        role: "user" as MessageRole,
        content: trimmed,
        timestamp: Date.now(),
        status: "sent",
      };

      // 创建助手消息占位
      const assistantMessage: Message = {
        id: generateId(),
        role: "assistant" as MessageRole,
        content: "",
        timestamp: Date.now(),
        status: "sending",
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setIsSending(true);
      setCharacterState("thinking");

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmed,
            conversationId: conversationIdRef.current,
          }),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `请求失败 (${response.status})`);
        }

        const data = await response.json();

        // 更新会话ID
        if (data.conversationId) {
          conversationIdRef.current = data.conversationId;
        }

        // 更新角色状态（扩展字段）
        if (data.emotion) setEmotion(data.emotion);
        if (data.characterState) setCharacterState(data.characterState);
        else setCharacterState("speaking");

        // 更新助手消息内容
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessage.id
              ? {
                  ...msg,
                  content: data.reply,
                  status: "sent" as MessageStatus,
                  timestamp: Date.now(),
                }
              : msg
          )
        );
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "发送失败，请重试";

        setError(errorMessage);
        setCharacterState("error");

        // 更新助手消息为错误状态
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessage.id
              ? {
                  ...msg,
                  content: "",
                  status: "error" as MessageStatus,
                }
              : msg
          )
        );
      } finally {
        setIsSending(false);
        // 延迟恢复到空闲状态
        setTimeout(() => {
          setCharacterState((prev) => (prev === "error" ? prev : "idle"));
        }, 2000);
      }
    },
    [isSending]
  );

  /** 清除消息 */
  const clearMessages = useCallback(() => {
    setMessages([]);
    conversationIdRef.current = null;
    setEmotion(null);
    setCharacterState(null);
    setError(null);
  }, []);

  /** 清除错误 */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  return {
    messages,
    isSending,
    error,
    conversationId: conversationIdRef.current,
    emotion,
    characterState,
    sendMessage,
    clearMessages,
    clearError,
  };
}

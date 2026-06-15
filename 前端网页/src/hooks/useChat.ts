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

/** 从回复内容提取所有情绪（按出现顺序），用于 galgame 式轮播 */
function detectEmotionSequence(text: string): Emotion[] {
  if (!text) return ["neutral"] as Emotion[];
  const seq: Emotion[] = [];
  const t = text;

  // 按情绪强度分块扫描（每 80 字一段）
  const chunks = t.match(/.{1,80}/g) || [t];
  for (const chunk of chunks) {
    if (/[哈嘿嘻]{2,}|笑死|太[好棒强]|真不错|牛[逼批]|神作|绝了|🎉|😆|😄|😂|🤣|💖/.test(chunk)) {
      seq.push("happy" as Emotion);
    } else if (/抱抱|唉[~～]|可惜了|遗憾|心疼|😢|💔|🌧|😿|自闭/.test(chunk)) {
      seq.push("sad" as Emotion);
    } else if (/[？?]{2,}|卧槽|离谱|不是吧|震惊|还有这种|竟然|😱|😨|🤯/.test(chunk)) {
      seq.push("surprised" as Emotion);
    } else if (/❌|🚫|禁止|错误|失败|别瞎说|生气|💢|😤|垃圾|坑爹|过分|烂/.test(chunk)) {
      seq.push("angry" as Emotion);
    } else if (/哼[!！~～]|切[~～]|本小姐|老子|劳资|懂了吧|叫爸爸|叫姐姐|😏|😤|💅|傲娇/.test(chunk)) {
      seq.push("tsundere" as Emotion);
    } else if (/✨|🎮|💪|🔥|👍|💯|⭐|🌟|🏆|🍰/.test(chunk) && !seq.length) {
      seq.push("happy" as Emotion);
    }
  }
  return seq.length ? seq : (["neutral"] as Emotion[]);
}

/** 从回复内容推断单一情绪（兼容旧接口） */
function detectEmotion(text: string): Emotion {
  const seq = detectEmotionSequence(text);
  return seq[seq.length - 1] || ("neutral" as Emotion);
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
  handleFileText: (text: string, filename: string) => void;
  handleClearFile: () => void;
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
  const fileTextRef = useRef<string>("");

  /** 接收文件上传的文本 */
  const handleFileText = useCallback((text: string, filename: string) => {
    fileTextRef.current = `[上传文件: ${filename}]\n${text}\n[文件结束]`;
  }, []);

  /** 清除上传的文件 */
  const handleClearFile = useCallback(() => {
    fileTextRef.current = "";
  }, []);

  /** 发送消息 */
  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || isSending) return;

      // 清空之前的错误
      setError(null);

      // 文件文本独立传递（不显示在聊天内容中）
      const fileContext = fileTextRef.current || undefined;
      fileTextRef.current = "";

      // 创建用户消息（只显示用户输入的文字，不显示文件内容）
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
        // 构建 OpenAI 格式请求
        const msgs = [{ role: "user", content: trimmed }];
        const body: Record<string, unknown> = {
          model: "gamebti",
          messages: msgs,
          stream: false,
          session_id: conversationIdRef.current || undefined,
        };
        if (fileContext) body.file_context = fileContext;
        const agentBase = process.env.NEXT_PUBLIC_AGENT_BASE_URL || "";

        const response = await fetch(`${agentBase}/v1/chat/completions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          throw new Error(errorData.error || `请求失败 (${response.status})`);
        }

        const data = await response.json();
        // Agent 返回 OpenAI 格式: { choices: [{ message: { content: "..." } }], conversationId }
        const reply = data.choices?.[0]?.message?.content || "";

        // 更新会话ID
        if (data.conversationId) {
          conversationIdRef.current = data.conversationId;
        } else if (data.session_id) {
          conversationIdRef.current = data.session_id;
        }

        // 更新角色状态 — galgame 式情绪轮播
        if (data.emotion) {
          setEmotion(data.emotion);
        } else if (reply) {
          const seq = detectEmotionSequence(reply);
          if (seq.length === 1) {
            setEmotion(seq[0]);
          } else {
            let i = 0;
            setEmotion(seq[0]);
            const timer = setInterval(() => {
              i++;
              if (i < seq.length) setEmotion(seq[i]);
              else clearInterval(timer);
            }, 3000);
          }
        }
        if (data.characterState) setCharacterState(data.characterState);
        else setCharacterState("speaking");

        // 更新助手消息内容
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessage.id
              ? {
                  ...msg,
                  content: reply,
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
    handleFileText,
    handleClearFile,
  };
}

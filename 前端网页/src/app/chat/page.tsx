"use client";

/**
 * Gamebti Web Companion - 聊天页面
 * 完整聊天界面：Header + ChatWindow + Footer
 */

import { useMemo } from "react";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import ChatWindow from "@/components/ChatWindow";
import { useChat } from "@/hooks/useChat";
import { MESSAGE_CONFIG } from "@/lib/constants";
import type { Message } from "@/lib/types";

/** 生成欢迎消息 */
function createWelcomeMessage(): Message {
  return {
    id: "welcome",
    role: "assistant",
    content: MESSAGE_CONFIG.WELCOME_MESSAGE,
    timestamp: Date.now(),
    status: "sent",
  };
}

export default function ChatPage() {
  // 初始化欢迎消息
  const initialMessages = useMemo(() => [createWelcomeMessage()], []);

  const {
    messages,
    isSending,
    error,
    emotion,
    characterState,
    sendMessage,
    clearMessages,
    clearError,
    handleFileText,
    handleClearFile,
  } = useChat(initialMessages);

  return (
    <div className="flex min-h-screen flex-col">
      {/* 顶部导航 */}
      <Header />

      {/* 聊天主区域（减去 header 和 footer 高度） */}
      <div className="flex flex-1 flex-col pt-14">
        <ChatWindow
          messages={messages}
          isSending={isSending}
          error={error}
          emotion={emotion}
          characterState={characterState}
          onSend={sendMessage}
          onClear={clearMessages}
          onClearError={clearError}
          onFileText={handleFileText}
          onClearFile={handleClearFile}
        />
      </div>

      {/* 底部信息 */}
      <Footer />
    </div>
  );
}

"use client";

/**
 * Gamebti Web Companion - MessageList 组件
 * 消息列表，展示所有对话记录，自动滚动到底部
 */

import { useEffect, useRef } from "react";
import type { Message } from "@/lib/types";
import MessageBubble from "./MessageBubble";
import { MESSAGE_CONFIG } from "@/lib/constants";

interface MessageListProps {
  messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // 新消息到达时自动滚动到底部
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // 空消息状态
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8">
        <div className="animate-fade-in text-center">
          {/* 大图标 */}
          <div className="mb-6 inline-flex h-20 w-20 items-center justify-center rounded-full bg-game-surface border border-game-border">
            <svg
              className="h-10 w-10 text-game-primary/50"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={1.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-game-text">
            开始对话
          </h3>
          <p className="mt-2 text-sm text-game-text-muted max-w-xs">
            在下方输入你的游戏问题，Gamebti 将为你解答
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

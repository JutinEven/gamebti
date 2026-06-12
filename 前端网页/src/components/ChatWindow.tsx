"use client";

/**
 * Gamebti Web Companion - ChatWindow 组件
 * 聊天页面主布局：左侧角色立绘 + 右侧聊天区域
 * 响应式设计，手机端角色面板收起到顶部
 */

import { MESSAGE_CONFIG } from "@/lib/constants";
import type { Message } from "@/lib/types";
import MessageList from "./MessageList";
import InputBox from "./InputBox";
import CharacterPanel from "./CharacterPanel";
import type { Emotion, CharacterState } from "@/lib/types";

interface ChatWindowProps {
  messages: Message[];
  isSending: boolean;
  error: string | null;
  emotion: Emotion | null;
  characterState: CharacterState | null;
  onSend: (message: string) => void;
  onClear: () => void;
  onClearError: () => void;
}

export default function ChatWindow({
  messages,
  isSending,
  error,
  emotion,
  characterState,
  onSend,
  onClear,
  onClearError,
}: ChatWindowProps) {
  return (
    <div className="flex h-full flex-col sm:flex-row">
      {/* ---- 左侧：角色立绘面板（桌面端侧边栏，手机端顶部横幅） ---- */}
      <div className="flex-shrink-0 border-b border-game-border bg-game-surface/30 sm:w-[320px] sm:border-b-0 sm:border-r sm:w-80">
        {/* 手机端：折叠横幅 */}
        <div className="flex items-center justify-between px-4 py-3 sm:hidden">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-game-primary to-anime-purple text-xs font-bold text-white">
              G
            </div>
            <span className="text-sm font-medium text-game-text">
              Gamebti
            </span>
            {characterState && (
              <span className="text-xs text-game-text-muted">
                &middot;{" "}
                {characterState === "speaking"
                  ? "回复中"
                  : characterState === "thinking"
                    ? "思考中"
                    : "在线"}
              </span>
            )}
          </div>
          {/* 清除对话按钮 */}
          {messages.length > 0 && (
            <button
              onClick={onClear}
              className="rounded-lg px-2 py-1 text-xs text-game-text-muted transition-colors hover:bg-game-surface-hover hover:text-game-text"
            >
              清除对话
            </button>
          )}
        </div>

        {/* 桌面端：完整角色面板 */}
        <div className="hidden sm:flex sm:flex-col sm:h-full">
          <div className="flex items-center justify-between px-4 pt-4">
            <h2 className="text-sm font-semibold text-game-text-muted uppercase tracking-wider">
              角色助手
            </h2>
            {messages.length > 0 && (
              <button
                onClick={onClear}
                className="rounded-lg px-2.5 py-1 text-xs text-game-text-muted transition-colors hover:bg-game-surface-hover hover:text-game-text"
              >
                清除对话
              </button>
            )}
          </div>
          <div className="flex-1 flex items-center justify-center">
            <CharacterPanel
              emotion={emotion || undefined}
              characterState={characterState || undefined}
            />
          </div>
        </div>
      </div>

      {/* ---- 右侧：聊天区域 ---- */}
      <div className="flex flex-1 flex-col min-h-0">
        {/* 错误提示横幅 */}
        {error && (
          <div className="animate-slide-up mx-4 mt-3 flex items-center gap-2 rounded-lg border border-game-error/30 bg-game-error/10 px-4 py-2.5">
            <svg
              className="h-4 w-4 flex-shrink-0 text-game-error"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span className="flex-1 text-sm text-game-error">{error}</span>
            <button
              onClick={onClearError}
              className="flex-shrink-0 rounded p-1 text-game-error/70 transition-colors hover:bg-game-error/10 hover:text-game-error"
              aria-label="关闭错误提示"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        )}

        {/* 消息列表 */}
        <MessageList messages={messages} />

        {/* 输入框 */}
        <InputBox onSend={onSend} disabled={isSending} />
      </div>
    </div>
  );
}

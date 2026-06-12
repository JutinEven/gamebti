"use client";

/**
 * Gamebti Web Companion - InputBox 组件
 * 消息输入框，支持 Enter 发送、Shift+Enter 换行
 */

import { useState, useRef, useCallback, type KeyboardEvent } from "react";
import { MESSAGE_CONFIG } from "@/lib/constants";

interface InputBoxProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export default function InputBox({ onSend, disabled = false }: InputBoxProps) {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  /** 发送消息 */
  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setInput("");

    // 重置 textarea 高度
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [input, disabled, onSend]);

  /** 键盘事件处理 */
  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter 发送（不含 Shift）
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  /** 自动调整 textarea 高度 */
  const handleInput = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = "auto";
    const maxHeight = 150;
    textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`;
  }, []);

  const charCount = input.length;
  const isOverLimit = charCount > MESSAGE_CONFIG.MAX_LENGTH;

  return (
    <div className="border-t border-game-border bg-game-surface/80 backdrop-blur-md px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {/* 输入区域 */}
        <div className="flex items-end gap-2.5 rounded-xl border border-game-border bg-game-bg px-4 py-2.5 transition-colors focus-within:border-game-primary/50 focus-within:shadow-lg focus-within:shadow-game-primary/5">
          {/* 文本输入 */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => {
              setInput(e.target.value);
              handleInput();
            }}
            onKeyDown={handleKeyDown}
            onInput={handleInput}
            placeholder={MESSAGE_CONFIG.PLACEHOLDER}
            disabled={disabled}
            rows={1}
            className="max-h-[150px] min-h-[24px] flex-1 resize-none border-none bg-transparent text-sm text-game-text placeholder-game-text-muted/50 outline-none disabled:opacity-50"
            aria-label="消息输入框"
          />

          {/* 发送按钮 */}
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim() || isOverLimit}
            className="flex-shrink-0 rounded-lg bg-gradient-to-r from-game-primary to-anime-purple p-2 text-white transition-all hover:from-game-primary-hover hover:to-anime-purple/80 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="发送消息"
          >
            {disabled ? (
              /* 加载图标 */
              <svg
                className="h-4 w-4 animate-spin"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
            ) : (
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
                  d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"
                />
              </svg>
            )}
          </button>
        </div>

        {/* 底部提示 */}
        <div className="mt-2 flex items-center justify-between px-1">
          <p className="text-[11px] text-game-text-muted/40">
            Enter 发送 &middot; Shift+Enter 换行
          </p>
          <p
            className={`text-[11px] ${
              isOverLimit ? "text-game-error" : "text-game-text-muted/40"
            }`}
          >
            {charCount}/{MESSAGE_CONFIG.MAX_LENGTH}
          </p>
        </div>
      </div>
    </div>
  );
}

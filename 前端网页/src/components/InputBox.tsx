"use client";

/**
 * Gamebti Web Companion - InputBox 组件
 * 支持 Enter 发送、Shift+Enter 换行、文件上传
 */

import { useState, useRef, useCallback, type KeyboardEvent, type ChangeEvent } from "react";
import { MESSAGE_CONFIG } from "@/lib/constants";

interface InputBoxProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  onFileText?: (text: string, filename: string) => void;
  onClearFile?: () => void;
}

export default function InputBox({ onSend, disabled = false, onFileText, onClearFile }: InputBoxProps) {
  const [input, setInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [attachedFile, setAttachedFile] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /** 发送消息 */
  const handleSend = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;

    onSend(trimmed);
    setInput("");
    setAttachedFile(null);

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

  /** 文件上传 */
  const handleFileChange = useCallback(async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !onFileText) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "上传失败");
      }
      const data = await res.json();
      onFileText(data.text, data.filename);
      setAttachedFile(data.filename);
    } catch (err) {
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [onFileText]);

  return (
    <div className="border-t border-game-border bg-game-surface/80 backdrop-blur-md px-4 py-3">
      <div className="mx-auto max-w-3xl">
        {/* 文件附件标签 */}
        {attachedFile && (
          <div className="mb-2 flex items-center gap-2 rounded-lg bg-game-primary/10 border border-game-primary/30 px-3 py-1.5 text-xs animate-slide-up">
            <svg className="h-3.5 w-3.5 text-game-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-game-primary font-medium truncate max-w-[200px]">{attachedFile}</span>
            <button
              onClick={() => { setAttachedFile(null); onClearFile?.(); }}
              className="ml-auto text-game-text-muted hover:text-game-error transition-colors"
              aria-label="移除文件"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

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

          {/* 文件上传按钮 */}
          {onFileText && (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.pptx,.ppt,.txt,.md,.json,.html"
                onChange={handleFileChange}
                className="hidden"
                aria-label="上传文件"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || uploading}
                className="flex-shrink-0 rounded-lg p-2 text-game-text-muted hover:text-game-text hover:bg-game-surface-hover transition-colors disabled:opacity-40"
                aria-label="上传文件"
                title="上传文档（PDF/Word/Excel/PPT/TXT）"
              >
                {uploading ? (
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                  </svg>
                )}
              </button>
            </>
          )}

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

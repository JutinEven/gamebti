"use client";

/**
 * Gamebti Web Companion - MessageBubble 组件
 * 单条消息气泡，支持 Markdown 渲染
 */

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import type { Message } from "@/lib/types";

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const isError = message.status === "error";
  const isSending = message.status === "sending";

  return (
    <div
      className={`animate-slide-up flex w-full ${isUser ? "justify-end" : "justify-start"}`}
    >
      {/* 助手头像（仅助手消息显示） */}
      {!isUser && (
        <div className="mr-3 flex-shrink-0 pt-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-game-primary to-anime-purple text-xs font-bold text-white shadow-md">
            G
          </div>
        </div>
      )}

      {/* 消息内容 */}
      <div
        className={`max-w-[80%] sm:max-w-[70%] ${
          isUser ? "order-first mr-3" : ""
        }`}
      >
        {/* 气泡 */}
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? "bg-gradient-to-br from-game-primary to-game-primary-hover text-white shadow-lg shadow-game-primary/20"
              : "bg-game-surface border border-game-border text-game-text"
          } ${isError ? "border-game-error/50 bg-game-error/5" : ""} ${isSending ? "border-dashed" : ""}`}
        >
          {isSending ? (
            /* 加载动画 */
            <div className="flex items-center gap-2 py-1">
              <div className="flex gap-1">
                <span className="h-2 w-2 animate-bounce rounded-full bg-game-text-muted [animation-delay:0ms]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-game-text-muted [animation-delay:150ms]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-game-text-muted [animation-delay:300ms]" />
              </div>
              <span className="text-sm text-game-text-muted">思考中...</span>
            </div>
          ) : isError ? (
            /* 错误提示 */
            <div className="flex items-center gap-2 text-sm text-game-error">
              <svg
                className="h-4 w-4 flex-shrink-0"
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
              <span>消息发送失败，请重试</span>
            </div>
          ) : message.content ? (
            /* Markdown 渲染 */
            <div className="prose-custom text-sm leading-relaxed break-words">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // 代码块语法高亮
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || "");
                    const codeStr = String(children).replace(/\n$/, "");
                    const inline = !match;

                    if (!inline && match) {
                      return (
                        <SyntaxHighlighter
                          style={oneDark}
                          language={match[1]}
                          PreTag="div"
                          customStyle={{
                            borderRadius: "8px",
                            fontSize: "0.85em",
                            margin: 0,
                          }}
                          {...(props as Record<string, unknown>)}
                        >
                          {codeStr}
                        </SyntaxHighlighter>
                      );
                    }

                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                  // 链接在新窗口打开
                  a({ href, children, ...props }) {
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        {...props}
                      >
                        {children}
                      </a>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          ) : null}
        </div>

        {/* 时间戳 */}
        {!isSending && !isError && (
          <p
            className={`mt-1 text-[11px] text-game-text-muted/60 ${
              isUser ? "text-right" : "text-left"
            }`}
          >
            {formatTime(message.timestamp)}
          </p>
        )}
      </div>

      {/* 用户头像（仅用户消息显示） */}
      {isUser && (
        <div className="flex-shrink-0 pt-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-game-surface-hover text-xs font-medium text-game-text-muted border border-game-border">
            我
          </div>
        </div>
      )}
    </div>
  );
}

/** 格式化时间 */
function formatTime(timestamp: number): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);

  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;

  const hours = date.getHours().toString().padStart(2, "0");
  const minutes = date.getMinutes().toString().padStart(2, "0");
  return `${hours}:${minutes}`;
}

"use client";

/**
 * Gamebti Web Companion - CharacterPanel 组件
 * 角色立绘区域，显示角色占位图及状态动画
 * 第二阶段预留：Live2D 接入、角色表情切换、动画集成
 */

import type { CharacterPanelProps } from "@/lib/types";
import { CHARACTER_STATE_CLASSES, EMOTION_LABELS } from "@/lib/constants";

export default function CharacterPanel({
  emotion,
  characterState = "idle",
  className = "",
}: CharacterPanelProps) {
  const animationClass = CHARACTER_STATE_CLASSES[characterState] || "";
  const emotionLabel = emotion ? EMOTION_LABELS[emotion] : null;

  return (
    <aside
      className={`flex flex-col items-center justify-center p-6 ${className}`}
    >
      {/* 角色状态气泡 */}
      {emotionLabel && (
        <div className="animate-slide-up mb-4 rounded-full bg-game-surface/90 px-4 py-1.5 text-sm text-game-text shadow-lg backdrop-blur-sm border border-game-border">
          {emotionLabel}
        </div>
      )}

      {/* 角色立绘容器 */}
      <div
        className={`relative ${animationClass}`}
        style={{ width: 280, height: 420 }}
      >
        {/* 发光背景 */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-20 blur-3xl transition-all duration-500"
          style={{
            width: 200,
            height: 200,
            background:
              characterState === "speaking"
                ? "radial-gradient(circle, rgba(99,102,241,0.6), transparent)"
                : characterState === "thinking"
                  ? "radial-gradient(circle, rgba(168,85,247,0.6), transparent)"
                  : "radial-gradient(circle, rgba(6,182,212,0.4), transparent)",
          }}
        />

        {/* 角色占位图 */}
        <div className="relative flex h-full w-full flex-col items-center justify-center rounded-2xl border border-game-border bg-gradient-to-b from-game-surface to-game-bg p-4">
          {/* 占位头像 */}
          <div className="mb-4 flex h-32 w-32 items-center justify-center rounded-full border-2 border-game-primary/30 bg-game-surface-hover">
            <svg
              className="h-16 w-16 text-game-primary/40"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v1.2c0 .66.54 1.2 1.2 1.2h16.8c.66 0 1.2-.54 1.2-1.2v-1.2c0-3.2-6.4-4.8-9.6-4.8z" />
            </svg>
          </div>

          {/* 角色名称 */}
          <h3 className="text-lg font-semibold text-game-text">
            Gamebti
          </h3>
          <p className="mt-1 text-xs text-game-text-muted">
            游戏助手 AI
          </p>

          {/* 状态指示器 */}
          <div className="mt-4 flex items-center gap-1.5">
            <span
              className={`inline-block h-2 w-2 rounded-full transition-colors duration-500 ${
                characterState === "speaking"
                  ? "bg-game-accent animate-pulse"
                  : characterState === "thinking"
                    ? "bg-anime-purple animate-pulse"
                    : characterState === "error"
                      ? "bg-game-error"
                      : "bg-game-success"
              }`}
            />
            <span className="text-xs text-game-text-muted capitalize">
              {characterState === "speaking"
                ? "说话中..."
                : characterState === "thinking"
                  ? "思考中..."
                  : characterState === "error"
                    ? "连接中断"
                    : "待命中"}
            </span>
          </div>

          {/* Live2D 占位区域（第二阶段扩展） */}
          <div className="mt-4 w-full rounded-lg border border-dashed border-game-border/50 p-2 text-center">
            <span className="text-[10px] text-game-text-muted/50">
              Live2D / 角色动画区域
            </span>
          </div>
        </div>
      </div>

      {/* 版本信息 */}
      <p className="mt-4 text-[10px] text-game-text-muted/40">
        v1.0.0 &middot; Powered by Coze
      </p>
    </aside>
  );
}

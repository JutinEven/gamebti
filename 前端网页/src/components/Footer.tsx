"use client";

/**
 * Gamebti Web Companion - Footer 组件
 * 底部信息栏
 */

export default function Footer() {
  return (
    <footer className="border-t border-game-border bg-game-surface/50 backdrop-blur-sm">
      <div className="mx-auto flex h-10 max-w-7xl items-center justify-center px-4">
        <p className="text-xs text-game-text-muted">
          Gamebti &copy; {new Date().getFullYear()} &mdash; AI 驱动的游戏助手
        </p>
      </div>
    </footer>
  );
}

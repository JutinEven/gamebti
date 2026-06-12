"use client";

/**
 * Gamebti Web Companion - 首页
 * 展示 Logo、简介和开始聊天按钮
 * 深色科技风 + 游戏社区风格
 */

import Link from "next/link";
import { useState } from "react";
import Logo from "@/components/Logo";
import Footer from "@/components/Footer";
import { APP_NAME, APP_DESCRIPTION } from "@/lib/constants";

export default function HomePage() {
  const [isHovering, setIsHovering] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      {/* ---- 主内容 ---- */}
      <main className="flex flex-1 flex-col items-center justify-center px-4">
        <div className="animate-fade-in w-full max-w-lg text-center">
          {/* Logo */}
          <div className="mb-6 flex justify-center">
            <div className="relative">
              {/* Logo 光晕 */}
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-40 w-40 rounded-full bg-gradient-to-r from-game-primary/20 via-anime-purple/20 to-game-accent/20 blur-3xl" />
              <div className="relative animate-float">
                <Logo size={96} />
              </div>
            </div>
          </div>

          {/* 标题 */}
          <h1 className="mt-6 bg-gradient-to-r from-game-primary via-anime-purple to-game-accent bg-clip-text text-4xl font-extrabold tracking-tight text-transparent sm:text-5xl">
            {APP_NAME}
          </h1>

          {/* 标语 */}
          <p className="mt-3 text-lg font-medium text-game-text/90">
            你的 AI 游戏智能助手
          </p>

          {/* 简介 */}
          <p className="mt-4 text-sm leading-relaxed text-game-text-muted">
            {APP_DESCRIPTION}
          </p>

          {/* 开始聊天按钮 */}
          <div className="mt-8 flex justify-center">
            <Link
              href="/chat"
              onMouseEnter={() => setIsHovering(true)}
              onMouseLeave={() => setIsHovering(false)}
              className="group relative inline-flex items-center gap-2.5 rounded-2xl bg-gradient-to-r from-game-primary via-anime-purple to-game-accent px-8 py-3.5 text-base font-semibold text-white shadow-xl shadow-game-primary/25 transition-all hover:shadow-2xl hover:shadow-game-primary/40 hover:scale-[1.02] active:scale-[0.98]"
            >
              {/* 悬停光效 */}
              <span
                className={`absolute inset-0 rounded-2xl bg-gradient-to-r from-game-accent via-anime-purple to-game-primary opacity-0 transition-opacity duration-500 ${
                  isHovering ? "opacity-100" : ""
                }`}
              />
              <span className="relative z-10 flex items-center gap-2.5">
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                  />
                </svg>
                开始聊天
              </span>
            </Link>
          </div>

          {/* 功能标签 */}
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            {[
              { icon: "?", label: "游戏攻略" },
              { icon: "?", label: "价格查询" },
              { icon: "?", label: "剧情整理" },
              { icon: "?", label: "游戏日报" },
              { icon: "?", label: "数据分析" },
            ].map((feature) => (
              <span
                key={feature.label}
                className="inline-flex items-center gap-1 rounded-full border border-game-border bg-game-surface/50 px-3 py-1 text-xs text-game-text-muted backdrop-blur-sm"
              >
                <span>{feature.icon}</span>
                <span>{feature.label}</span>
              </span>
            ))}
          </div>
        </div>
      </main>

      {/* ---- Footer ---- */}
      <Footer />
    </div>
  );
}

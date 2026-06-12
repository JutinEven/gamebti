import type { Metadata, Viewport } from "next";
import "./globals.css";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  themeColor: "#0a0e17",
};

export const metadata: Metadata = {
  title: "Gamebti - 你的游戏智能助手",
  description:
    "Gamebti 是一个懂游戏的 AI 助手。查询游戏价格、获取攻略、整理剧情、生成每日游戏日报，随时随地陪伴你的游戏之旅。",
  keywords: [
    "游戏助手",
    "AI助手",
    "游戏攻略",
    "游戏价格",
    "游戏日报",
    "Gamebti",
    "游戏智能体",
  ],
  authors: [{ name: "Gamebti Team" }],
  openGraph: {
    title: "Gamebti - 你的游戏智能助手",
    description: "AI 驱动的游戏助手，随时为你解答游戏相关问题。",
    type: "website",
    locale: "zh_CN",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen bg-game-bg text-game-text antialiased">
        {children}
      </body>
    </html>
  );
}

import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // 深色科技风配色
        "game-bg": "#0a0e17",
        "game-surface": "#111827",
        "game-surface-hover": "#1a2332",
        "game-border": "#1e2d3d",
        "game-primary": "#6366f1",
        "game-primary-hover": "#818cf8",
        "game-accent": "#06b6d4",
        "game-accent-hover": "#22d3ee",
        "game-success": "#10b981",
        "game-warning": "#f59e0b",
        "game-error": "#ef4444",
        "game-text": "#e2e8f0",
        "game-text-muted": "#94a3b8",
        // 二次元角色主题色
        "anime-pink": "#ec4899",
        "anime-purple": "#a855f7",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Noto Sans SC",
          "PingFang SC",
          "Microsoft YaHei",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "Fira Code",
          "Cascadia Code",
          "Consolas",
          "monospace",
        ],
      },
      animation: {
        "float": "float 3s ease-in-out infinite",
        "pulse-glow": "pulseGlow 2s ease-in-out infinite",
        "slide-up": "slideUp 0.3s ease-out",
        "fade-in": "fadeIn 0.5s ease-out",
      },
      keyframes: {
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        pulseGlow: {
          "0%, 100%": { boxShadow: "0 0 5px rgba(99, 102, 241, 0.5)" },
          "50%": { boxShadow: "0 0 20px rgba(99, 102, 241, 0.8)" },
        },
        slideUp: {
          from: { transform: "translateY(10px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
};
export default config;

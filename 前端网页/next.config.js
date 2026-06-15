/**
 * Gamebti Web Companion - Next.js 配置
 *
 * Node 24 Windows 兼容说明:
 * - `npm run dev` 正常工作
 * - `npm run build` 在 Node 24 Windows 上可能遇到 readlink EISDIR 错误
 *   这是 Node 24 在 Windows 上的已知 bug
 *   解决方案：使用 Node 22 LTS，或部署到 Vercel (Linux)
 *   项目中包含 readlink-patch.js 和 build:win 脚本作为临时方案
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "export",
  images: { unoptimized: true },
};

module.exports = nextConfig;

# Gamebti Web Companion

> AI 驱动的游戏智能助手 — Web 前端

Gamebti 是你的专属游戏智能助手。查询最新游戏价格、获取深度攻略解析、整理剧情设定、生成每日游戏日报。

本仓库是 Gamebti 的 Web 前端，通过 **Coze Agent API** 提供智能对话能力。

---

## 技术栈

| 技术 | 用途 |
|------|------|
| **Next.js 15** | React 框架，SSR + API Routes |
| **TypeScript** | 类型安全 |
| **TailwindCSS** | 原子化 CSS |
| **react-markdown** | Markdown 渲染 |
| **remark-gfm** | GFM 扩展（表格、任务列表等） |
| **react-syntax-highlighter** | 代码语法高亮 |

> 无复杂数据库、无付费服务、无冗余依赖。

---

## 目录结构

```
gamebti-web-companion/
├── public/
│   └── images/
│       └── character-placeholder.svg  # 角色占位图
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   └── chat/
│   │   │       └── route.ts           # Chat API 路由（服务端）
│   │   ├── chat/
│   │   │   └── page.tsx               # 聊天页面
│   │   ├── globals.css                # 全局样式
│   │   ├── layout.tsx                 # 根布局
│   │   └── page.tsx                   # 首页
│   ├── components/
│   │   ├── Header.tsx                 # 顶部导航栏
│   │   ├── Footer.tsx                 # 底部信息栏
│   │   ├── Logo.tsx                   # SVG Logo
│   │   ├── CharacterPanel.tsx         # 角色立绘区域
│   │   ├── ChatWindow.tsx             # 聊天主窗口
│   │   ├── MessageList.tsx            # 消息列表
│   │   ├── MessageBubble.tsx          # 单条消息气泡
│   │   └── InputBox.tsx               # 消息输入框
│   ├── hooks/
│   │   └── useChat.ts                 # 聊天状态管理 Hook
│   └── lib/
│       ├── types.ts                   # TypeScript 类型定义
│       ├── constants.ts               # 应用常量
│       └── coze-client.ts             # Coze API 服务端客户端
├── .env.local.example                 # 环境变量模板
├── .gitignore
├── next.config.js
├── readlink-patch.js                  # Node 24 Windows 补丁
├── package.json
├── postcss.config.js
├── tailwind.config.ts
├── tsconfig.json
└── README.md
```

### 目录职责

| 目录 | 职责 |
|------|------|
| `src/app/` | Next.js App Router 页面和 API 路由 |
| `src/components/` | 可复用 UI 组件，每个独立文件 |
| `src/hooks/` | 自定义 React Hook（状态管理） |
| `src/lib/` | 工具函数、类型定义、API 客户端 |
| `public/` | 静态资源（图片、SVG 等） |

---

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd gamebti-web-companion
```

### 2. 安装依赖

```bash
npm install
```

### 3. 配置环境变量

```bash
cp .env.local.example .env.local
```

编辑 `.env.local`，填入你的 Coze 配置：

```env
COZE_API_KEY=your_coze_api_key_here
COZE_BOT_ID=your_coze_bot_id_here
COZE_API_BASE_URL=https://api.coze.com
COZE_API_TIMEOUT=30000
```

> 开发调试时可开启模拟模式：`COZE_MOCK_MODE=true`

### 4. 启动开发服务器

```bash
npm run dev
```

浏览器打开 [http://localhost:3000](http://localhost:3000)

### 5. 构建生产版本

```bash
npm run build
npm start
```

---

## 环境兼容性

| 平台 | 状态 | 说明 |
|------|------|------|
| Vercel (Linux) | ✅ 完全支持 | 生产部署推荐 |
| macOS / Linux 本地 | ✅ 完全支持 | `npm run build` + `npm run dev` |
| Windows + Node 22 LTS | ✅ 完全支持 | 推荐 Windows 用户使用 |
| Windows + Node 24 | ⚠️ 仅开发模式 | `npm run dev` 正常；`npm run build` 有已知兼容问题 |

> **Node 24 Windows 说明**：Node 24 在 Windows 上存在 `fs.readlinkSync` 抛出 `EISDIR` 的已知 bug。`npm run dev`（Turbopack）不受影响。项目包含 `readlink-patch.js` 作为临时方案。生产构建请使用 Vercel 或 Node 22 LTS。

---

## Vercel 部署指南

### 一键部署

1. 将项目推送到 GitHub
2. 在 [Vercel](https://vercel.com) 导入仓库
3. 配置环境变量（Settings → Environment Variables）：

| Key | Value |
|-----|-------|
| `COZE_API_KEY` | 你的 Coze API Key |
| `COZE_BOT_ID` | 你的 Coze Bot ID |
| `COZE_API_BASE_URL` | `https://api.coze.com`（国际版） |
| `COZE_API_TIMEOUT` | `30000` |

4. 部署！

> **注意**：Vercel 免费套餐支持 100GB 带宽/月，个人使用完全够用。项目打包为 `standalone` 模式，兼容 Vercel Serverless Functions。

### 框架预设

Vercel 会自动检测 Next.js 项目，无需额外配置。`next.config.js` 中 `output: 'standalone'` 确保构建产物与 Vercel 兼容。

---

## 环境变量说明

| 变量 | 必填 | 说明 |
|------|------|------|
| `COZE_API_KEY` | ? | Coze 平台 API Key |
| `COZE_BOT_ID` | ? | Coze Bot ID |
| `COZE_API_BASE_URL` | ? | Coze API 地址（国际版 `api.coze.com`，国内版 `api.coze.cn`） |
| `COZE_API_TIMEOUT` | ? | 请求超时（毫秒），默认 30000 |
| `COZE_MOCK_MODE` | ? | 模拟模式（`true` 开启），无需配置 API Key 即可调试 UI |

---

## Coze API 接入说明

### 架构

```
┌──────────┐      ┌────────────────┐      ┌─────────────┐
│  浏览器   │ ---> │ Next.js API    │ ---> │ Coze Agent  │
│ (前端)    │ <--- │ Route (后端)   │ <--- │ API         │
└──────────┘      └────────────────┘      └─────────────┘
                  API Key 仅在此层使用
```

### API 端点

**`POST /api/chat`**

请求体：
```json
{
  "message": "告诉我今天的游戏日报",
  "conversationId": "conv_xxx"
}
```

成功响应：
```json
{
  "reply": "## 今日游戏日报\n...",
  "conversationId": "conv_xxx",
  "emotion": "happy",
  "action": "talk",
  "characterState": "speaking"
}
```

错误响应：
```json
{
  "error": "请求超时，请稍后重试",
  "code": "TIMEOUT"
}
```

### 错误码

| Code | HTTP 状态 | 说明 |
|------|-----------|------|
| `TIMEOUT` | 504 | 请求超时 |
| `NETWORK_ERROR` | 502 | 网络连接失败 |
| `AGENT_ERROR` | 500 | Agent 异常 |
| `INVALID_REQUEST` | 400 | 请求无效（空消息等） |

### 获取 Coze API Key

1. 登录 [Coze 控制台](https://www.coze.com/open/api)
2. 创建 API Token
3. 复制 Token 到 `.env.local` 的 `COZE_API_KEY`
4. 获取你的 Bot ID 填入 `COZE_BOT_ID`

---

## 第二阶段扩展

项目已预留在以下方面扩展：

| 扩展项 | 预留位置 | 说明 |
|--------|----------|------|
| **Live2D 接入** | `CharacterPanel.tsx` | 已有 Live2D 占位区域，可直接替换角色立绘 |
| **角色表情切换** | `CharacterPanel.tsx` + `types.ts` | `Emotion` 类型已定义 7 种情绪，CSS 动画已预留 |
| **Steam 价格卡片** | `types.ts` (SteamPriceCard) | 类型已定义，可在 MessageBubble 中渲染 |
| **游戏新闻卡片** | `types.ts` (GameNewsCard) | 同上 |
| **游戏数据卡片** | `types.ts` (GameDataCard) | 同上 |
| **每日日报展示** | `types.ts` (DailyReportCard) | 同上 |
| **多 Agent 切换** | `Header.tsx` 导航区域 | 已预留导航入口 |
| **桌宠风格** | `CharacterPanel.tsx` | 角色面板可改为悬浮窗口 |

Agent 返回的扩展字段（`emotion`、`action`、`character_state`）已被前端完整解析和使用。

---

## 第三阶段：Electron 迁移

项目已为 Electron 做准备：

- `next.config.js` 设置 `output: 'standalone'` — 生成独立 Node.js 服务
- 前后端分离 — API Route 通过 HTTP 调用，Electron 可直接复用
- 无浏览器特定 API 依赖 — 所有功能与渲染环境解耦
- 纯 CSS 方案 — 无第三方 UI 库，减少 Electron 兼容问题

### Electron 打包步骤（概要）

```bash
# 1. 构建 Next.js
npm run build

# 2. 用 electron-builder 打包 .next/standalone
npx electron-builder
```

---

## 设计说明

- **深色主题**：`#0a0e17` 主背景 + Indigo/Cyan 渐变点缀
- **科技感**：渐变边框、发光阴影、模糊玻璃效果
- **二次元元素**：角色立绘区域、情绪动画、浮动效果
- **响应式**：PC 双栏布局 / 手机端角色面板收起为顶部横幅
- **Markdown 渲染**：支持 GFM 表格、代码高亮、任务列表

---

## License

MIT

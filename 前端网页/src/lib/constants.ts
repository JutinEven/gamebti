/**
 * ============================================
 * Gamebti Web Companion - 应用常量
 * ============================================
 */

/** 应用名称 */
export const APP_NAME = "Gamebti";

/** 应用标语 */
export const APP_TAGLINE = "你的游戏智能助手";

/** 应用简介 */
export const APP_DESCRIPTION =
  "Gamebti 是一个懂游戏的 AI 助手。查询最新游戏价格、获取深度攻略解析、整理游戏剧情设定、生成每日游戏日报。随时随地，陪伴你的游戏之旅。";

/** Coze API 配置 */
export const COZE_CONFIG = {
  /** API 基础地址 */
  BASE_URL: process.env.COZE_API_BASE_URL || "https://api.coze.com",
  /** 请求超时（毫秒） */
  TIMEOUT: Number(process.env.COZE_API_TIMEOUT) || 30000,
  /** API 版本路径 */
  API_PATH: "/v3/chat",
} as const;

/** Agent 后端配置（自部署 LangGraph Agent） */
export const AGENT_CONFIG = {
  /** Agent API 基础地址 */
  BASE_URL: process.env.AGENT_BASE_URL || "http://localhost:5000",
  /** Agent 请求超时（毫秒），Agent 推理可能需要较长时间 */
  TIMEOUT: Number(process.env.AGENT_TIMEOUT) || 120000,
  /** Agent OpenAI 兼容接口路径 */
  API_PATH: "/v1/chat/completions",
} as const;

/** 后端提供商类型 */
export type AgentProvider = "agent" | "coze";

/** 当前使用的后端提供商 */
export const CURRENT_PROVIDER: AgentProvider =
  (process.env.AGENT_PROVIDER as AgentProvider) || "agent";

/** 消息配置 */
export const MESSAGE_CONFIG = {
  /** 最大消息长度 */
  MAX_LENGTH: 4000,
  /** 输入框 placeholder */
  PLACEHOLDER: "输入你的游戏问题...",
  /** 空消息提示 */
  EMPTY_MESSAGE: "消息不能为空",
  /** 欢迎消息 */
  WELCOME_MESSAGE:
    "你好！我是 Gamebti，你的专属游戏智能助手！🎮\n\n我可以帮你：\n- 📊 查询游戏价格和折扣信息\n- 📖 提供游戏攻略和通关技巧\n- 📝 整理游戏剧情和世界观设定\n- 📰 生成每日游戏日报\n- 📈 分析游戏数据趋势\n\n有什么想了解的游戏问题吗？尽管问我吧！",
} as const;

/** 角色情绪对应的提示文本 */
export const EMOTION_LABELS: Record<string, string> = {
  happy: "今天心情不错！",
  sad: "有点难过...",
  surprised: "哇，这个有意思！",
  angry: "哼！",
  neutral: "我在听呢",
  thinking: "让我想想...",
  excited: "这个我超懂！",
  tsundere: "哼，才不是特意帮你的！",
};

/** 角色状态对应的 CSS 类 */
export const CHARACTER_STATE_CLASSES: Record<string, string> = {
  idle: "",
  speaking: "",
  thinking: "",
  happy: "",
  error: "",
};

/**
 * ============================================
 * Gamebti Web Companion - 类型定义
 * ============================================
 * 集中管理所有 TypeScript 类型
 * 预留扩展字段以支持后续阶段功能
 * ============================================
 */

// ---- 消息相关 ----

/** 消息角色 */
export type MessageRole = "user" | "assistant";

/** 消息状态 */
export type MessageStatus = "sending" | "sent" | "error" | "streaming";

/** 单条消息 */
export interface Message {
  /** 唯一标识 */
  id: string;
  /** 消息角色 */
  role: MessageRole;
  /** 消息文本内容 */
  content: string;
  /** 时间戳 */
  timestamp: number;
  /** 发送状态 */
  status: MessageStatus;
}

// ---- Agent 响应扩展字段（第二阶段预留） ----

/** 角色情绪状态 */
export type Emotion =
  | "happy"
  | "sad"
  | "surprised"
  | "angry"
  | "neutral"
  | "thinking"
  | "excited"
  | "tsundere";

/** 角色动作 */
export type Action =
  | "talk"
  | "idle"
  | "typing"
  | "happy_jump"
  | "shake_head"
  | "wave";

/** 角色整体状态 */
export type CharacterState = "idle" | "speaking" | "thinking" | "happy" | "error";

/** Agent 扩展响应（未来 Coze Agent 返回格式） */
export interface AgentResponse {
  /** 回复文本 */
  text: string;
  /** 角色情绪（扩展字段） */
  emotion?: Emotion;
  /** 角色动作（扩展字段） */
  action?: Action;
  /** 角色状态（扩展字段） */
  character_state?: CharacterState;
  /** 特殊卡片数据（扩展字段） */
  card?: GameCard | null;
}

// ---- 游戏数据卡片（第二阶段预留） ----

/** 卡片类型 */
export type CardType = "steam_price" | "game_news" | "game_data" | "daily_report";

/** 游戏卡片基础接口 */
export interface GameCard {
  type: CardType;
  title: string;
  data: unknown; // 具体类型根据 CardType 确定
}

/** Steam 价格卡片 */
export interface SteamPriceCard extends GameCard {
  type: "steam_price";
  data: {
    gameName: string;
    originalPrice: number;
    currentPrice: number;
    discountPercent: number;
    currency: string;
    imageUrl?: string;
    steamUrl?: string;
  };
}

/** 游戏新闻卡片 */
export interface GameNewsCard extends GameCard {
  type: "game_news";
  data: {
    source: string;
    title: string;
    summary: string;
    url?: string;
    publishDate?: string;
    imageUrl?: string;
  };
}

/** 游戏数据卡片 */
export interface GameDataCard extends GameCard {
  type: "game_data";
  data: {
    gameName: string;
    metrics: Record<string, string | number>;
    chartData?: unknown;
  };
}

/** 每日日报卡片 */
export interface DailyReportCard extends GameCard {
  type: "daily_report";
  data: {
    date: string;
    highlights: string[];
    recommendedGames: string[];
    newsCount: number;
  };
}

// ---- API 相关 ----

/** 发送给 API 的请求体 */
export interface ChatRequest {
  message: string;
  /** 会话ID，用于 Coze 多轮对话 */
  conversationId?: string;
}

/** API 响应体 */
export interface ChatResponse {
  /** Agent 回复文本 */
  reply: string;
  /** 会话ID */
  conversationId: string;
  /** 扩展字段 */
  emotion?: Emotion;
  action?: Action;
  characterState?: CharacterState;
}

/** API 错误响应 */
export interface ChatErrorResponse {
  error: string;
  code: "TIMEOUT" | "NETWORK_ERROR" | "AGENT_ERROR" | "INVALID_REQUEST";
  detail?: string;
}

// ---- 组件 Props ----

export interface CharacterPanelProps {
  emotion?: Emotion;
  characterState?: CharacterState;
  className?: string;
}

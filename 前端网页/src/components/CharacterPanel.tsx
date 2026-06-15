"use client";

/**
 * Gamebti CharacterPanel — 角色立绘 + 情绪头像
 * 点击互动：戳一戳换表情、连点激怒、情绪动效
 */

import { useState, useEffect, useRef, useCallback } from "react";
import type { CharacterPanelProps } from "@/lib/types";

/** 情绪 → 立绘图片映射 */
const EMOTION_IMAGES: Record<string, string> = {
  happy: "/images/开心.png", excited: "/images/开心.png",
  sad: "/images/沮丧.png",
  angry: "/images/生气.png",
  surprised: "/images/无语.png",
  tsundere: "/images/傲娇.png", thinking: "/images/傲娇.png",
  neutral: "/images/常态.png", idle: "/images/常态.png",
  error: "/images/无语.png",
};

/** 戳一戳表情池 */
const POKE_EMOTIONS = ["happy", "surprised", "tsundere"];
const POKE_LABELS: Record<string, string> = { happy: "嘻嘻~", surprised: "？！", tsundere: "哼！别碰我啦~" };

/** 状态文字 */
const STATE_LABELS: Record<string, string> = { speaking: "说话中...", thinking: "思考中...", error: "连接中断", idle: "待命中" };

/**
 * 情绪 → CSS 动画类
 * animate-bounce: 上下跳    animate-shake-x: 左右摇    animate-shake: 全方位震
 */
const EMOTION_ANIM: Record<string, string> = {
  happy: "animate-bounce", excited: "animate-bounce",
  sad: "animate-sway",
  angry: "animate-shake",
  surprised: "animate-shake-x",
  tsundere: "animate-tsun",
};

export default function CharacterPanel({ emotion, characterState = "idle", className = "" }: CharacterPanelProps) {
  const [imgError, setImgError] = useState(false);
  const [pokeEmotion, setPokeEmotion] = useState<string | null>(null);
  const [pokeLabel, setPokeLabel] = useState("");
  const [animClass, setAnimClass] = useState("");
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clickCount = useRef(0);

  const displayEmotion = pokeEmotion || emotion || characterState;
  const imageSrc = EMOTION_IMAGES[displayEmotion] || EMOTION_IMAGES.neutral;
  const stateLabel = pokeLabel || STATE_LABELS[characterState] || STATE_LABELS.idle;

  useEffect(() => { setImgError(false); }, [imageSrc]);
  useEffect(() => { if (emotion) { setPokeEmotion(null); setPokeLabel(""); } }, [emotion]);
  useEffect(() => { return () => { if (timerRef.current) clearTimeout(timerRef.current); }; }, []);

  /** 表情切换时触发对应动效 */
  useEffect(() => {
    const key = pokeEmotion || emotion;
    if (key && EMOTION_ANIM[key]) {
      setAnimClass(EMOTION_ANIM[key]);
      const t = setTimeout(() => setAnimClass(""), 400);
      return () => clearTimeout(t);
    } else {
      setAnimClass("");
    }
  }, [pokeEmotion, emotion]);

  /** 点击立绘：单点戳一戳 / 连点 5 次以上 → 激怒 */
  const handlePoke = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    clickCount.current++;

    if (clickCount.current >= 5) {
      // 激怒！
      clickCount.current = 0;
      setPokeEmotion("angry");
      setPokeLabel("别戳了！！！💢");
      timerRef.current = setTimeout(() => { setPokeEmotion(null); setPokeLabel(""); }, 2500);
      return;
    }

    // 普通戳一戳
    const random = POKE_EMOTIONS[Math.floor(Math.random() * POKE_EMOTIONS.length)];
    setPokeEmotion(random);
    setPokeLabel(POKE_LABELS[random] || "戳~");
    timerRef.current = setTimeout(() => { setPokeEmotion(null); setPokeLabel(""); }, 1500);

    // 1 秒内没再点 → 重置计数器
    setTimeout(() => { clickCount.current = 0; }, 1000);
  }, []);

  return (
    <aside className={`flex flex-col items-center justify-start gap-4 p-4 ${className}`} style={{ position: "sticky", top: "1rem" }}>
      <div className="rounded-full bg-game-surface/90 px-4 py-1.5 text-sm text-game-text shadow-lg backdrop-blur-sm border border-game-border animate-slide-up">
        {stateLabel}
      </div>

      <div className="flex h-24 w-24 items-center justify-center rounded-full border-2 border-game-primary/40 bg-game-surface-hover overflow-hidden shadow-lg hover:scale-110 transition-transform duration-300 cursor-pointer">
        <img src="/images/Q版头像.png" alt="Gamebti" className="h-full w-full object-cover"
          onError={(e) => { e.currentTarget.style.display = "none"; e.currentTarget.parentElement!.innerHTML = '<svg class="h-12 w-12 text-game-primary/40" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v1.2c0 .66.54 1.2 1.2 1.2h16.8c.66 0 1.2-.54 1.2-1.2v-1.2c0-3.2-6.4-4.8-9.6-4.8z" /></svg>'; }} />
      </div>

      <div className="text-center">
        <h3 className="text-lg font-semibold text-game-text">Gamebti</h3>
        <p className="text-xs text-game-text-muted">游戏助手 AI</p>
      </div>

      <div className={`relative flex items-center justify-center rounded-2xl border border-game-border bg-gradient-to-b from-game-surface to-game-bg overflow-hidden shadow-lg cursor-pointer select-none ${animClass}`}
        style={{ width: 320, height: 460 }} onClick={handlePoke} title="戳一戳~">
        <div className="absolute inset-0 opacity-15 blur-3xl transition-all duration-700"
          style={{ background: characterState === "speaking" ? "radial-gradient(circle, rgba(99,102,241,0.6), transparent)" : characterState === "thinking" ? "radial-gradient(circle, rgba(168,85,247,0.6), transparent)" : "radial-gradient(circle, rgba(6,182,212,0.3), transparent)" }} />
        {!imgError ? (
          <img src={imageSrc} alt={displayEmotion || "常态"} className="relative z-10 h-full w-full object-cover transition-all duration-500" style={{ objectPosition: displayEmotion === "neutral" ? "center center" : "50% 5%" }} onError={() => setImgError(true)} />
        ) : (
          <div className="relative z-10 flex flex-col items-center justify-center text-game-text-muted/50"><svg className="h-16 w-16" fill="currentColor" viewBox="0 0 24 24"><path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v1.2c0 .66.54 1.2 1.2 1.2h16.8c.66 0 1.2-.54 1.2-1.2v-1.2c0-3.2-6.4-4.8-9.6-4.8z" /></svg><span className="mt-2 text-xs">角色加载中...</span></div>
        )}
      </div>

      <div className="flex items-center gap-1.5">
        <span className={`inline-block h-2 w-2 rounded-full transition-colors duration-500 ${characterState === "speaking" ? "bg-game-accent animate-pulse" : characterState === "thinking" ? "bg-anime-purple animate-pulse" : characterState === "error" ? "bg-game-error" : "bg-game-success"}`} />
        <span className="text-xs text-game-text-muted">{stateLabel}</span>
      </div>
    </aside>
  );
}

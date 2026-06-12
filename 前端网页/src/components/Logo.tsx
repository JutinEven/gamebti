/**
 * Gamebti Web Companion - Logo 组件
 * SVG Logo，可用于不同尺寸
 */

interface LogoProps {
  size?: number;
  className?: string;
}

export default function Logo({ size = 40, className = "" }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Gamebti Logo"
    >
      {/* 外圈光环 */}
      <circle
        cx="32"
        cy="32"
        r="28"
        stroke="url(#logoGradient)"
        strokeWidth="2.5"
        fill="none"
        opacity="0.8"
      />
      {/* 内圈 */}
      <circle
        cx="32"
        cy="32"
        r="20"
        fill="#111827"
        stroke="#6366f1"
        strokeWidth="1.5"
      />
      {/* G 字母 */}
      <text
        x="32"
        y="38"
        textAnchor="middle"
        fill="url(#logoGradient)"
        fontFamily="Arial, sans-serif"
        fontSize="28"
        fontWeight="bold"
      >
        G
      </text>
      {/* 装饰点 */}
      <circle cx="48" cy="20" r="3" fill="#06b6d4" opacity="0.8" />
      <circle cx="16" cy="44" r="2" fill="#a855f7" opacity="0.6" />
      {/* 渐变定义 */}
      <defs>
        <linearGradient id="logoGradient" x1="0" y1="0" x2="64" y2="64">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="50%" stopColor="#a855f7" />
          <stop offset="100%" stopColor="#06b6d4" />
        </linearGradient>
      </defs>
    </svg>
  );
}

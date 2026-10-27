import { useId } from 'react'

/** Brand mark: three tastes converging into one thread. Purely decorative (the wordmark names the brand). */
export function ThreadMark({ size = 30 }: { size?: number }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg className="thread-mark" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-bg`} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#5B54F0" />
          <stop offset="1" stopColor="#9B5CF6" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="10" fill={`url(#${id}-bg)`} />
      <path d="M6 9.5C12.5 9.5 13.5 16 19 16" fill="none" stroke="#FFB4A6" strokeWidth="2" strokeLinecap="round" />
      <path d="M6 22.5C12.5 22.5 13.5 16 19 16" fill="none" stroke="#7CE8DA" strokeWidth="2" strokeLinecap="round" />
      <path d="M6 16H19" fill="none" stroke="#D9CCFF" strokeWidth="2" strokeLinecap="round" />
      <path d="M19 16H26" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="19" cy="16" r="2.6" fill="#fff" />
    </svg>
  )
}

const SOURCES = [
  { d: 'M36 92 C 170 92, 210 220, 320 220', stops: ['#FF8F7C', '#C9A7FF'], label: 'Indie rock', cls: 'chip-a' },
  { d: 'M36 220 C 140 168, 232 272, 320 220', stops: ['#4FE3CF', '#9FB8FF'], label: 'Street food', cls: 'chip-b' },
  { d: 'M36 348 C 170 348, 210 220, 320 220', stops: ['#B79BFF', '#7CC6FF'], label: 'Anime', cls: 'chip-c' },
] as const

/** Decorative hero motif: three different tastes flow together and leave as one shared thread.
 *  The chips are illustrative only (aria-hidden); nothing here is data. Motion is CSS-only and
 *  switched off under prefers-reduced-motion. */
export default function ThreadArt({ variant = 'hero' }: { variant?: 'hero' | 'compact' }) {
  const id = useId().replace(/:/g, '')
  return (
    <div className={`thread-art thread-art-${variant}`} aria-hidden="true">
      <svg viewBox="0 0 560 440" focusable="false" preserveAspectRatio="xMidYMid meet">
        <defs>
          {SOURCES.map((s, i) => (
            <linearGradient key={s.label} id={`${id}-g${i}`} x1="36" y1="0" x2="320" y2="0" gradientUnits="userSpaceOnUse">
              <stop offset="0" stopColor={s.stops[0]} />
              <stop offset="1" stopColor={s.stops[1]} />
            </linearGradient>
          ))}
          <linearGradient id={`${id}-out`} x1="320" y1="0" x2="524" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#FFFFFF" />
            <stop offset="1" stopColor="#FFD9A8" />
          </linearGradient>
          <radialGradient id={`${id}-glow`} cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#B9A8FF" stopOpacity=".95" />
            <stop offset="1" stopColor="#6E63F5" stopOpacity="0" />
          </radialGradient>
          <filter id={`${id}-soft`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" />
          </filter>
        </defs>

        <circle className="art-aura" cx="320" cy="220" r="150" fill={`url(#${id}-glow)`} />

        {SOURCES.map((s, i) => (
          <g key={s.label}>
            <path d={s.d} className="thread-base" stroke={`url(#${id}-g${i})`} />
            <path d={s.d} className="thread-flow" style={{ animationDelay: `${i * -2.1}s` }} pathLength={100} />
            <circle cx="36" cy={[92, 220, 348][i]} r="7" fill={s.stops[0]} />
            <circle cx="36" cy={[92, 220, 348][i]} r="14" fill={s.stops[0]} opacity=".18" />
          </g>
        ))}

        <path d="M320 220 C 392 176, 462 264, 524 220" className="thread-base thread-out" stroke={`url(#${id}-out)`} />
        <path d="M320 220 C 392 176, 462 264, 524 220" className="thread-flow thread-flow-out" pathLength={100} />

        <circle className="art-ring" cx="320" cy="220" r="26" fill="none" stroke="#fff" strokeOpacity=".5" />
        <circle cx="320" cy="220" r="15" fill="#fff" filter={`url(#${id}-soft)`} opacity=".7" />
        <circle cx="320" cy="220" r="10" fill="#fff" />
        <circle cx="524" cy="220" r="9" fill="#FFD9A8" />
        <circle cx="524" cy="220" r="18" fill="#FFD9A8" opacity=".2" />
      </svg>

      {variant === 'hero' && (
        <>
          {SOURCES.map((s) => (
            <span key={s.label} className={`thread-chip ${s.cls}`}>{s.label}</span>
          ))}
          <span className="thread-chip chip-out">One shared plan</span>
        </>
      )}
    </div>
  )
}

import React from 'react'

/**
 * Custom AETHERIS AI mark: a hexagonal safety-gate shield with a
 * pulse/heartbeat line through it, representing continuous system
 * health monitoring + bounded autonomous repair.
 */
export default function AetherisLogo({ size = 28, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="AETHERIS AI logo"
    >
      <defs>
        <linearGradient id="aetheris-logo-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#4f46e5" />
        </linearGradient>
      </defs>
      <path
        d="M16 1.5 L29.5 9 V23 L16 30.5 L2.5 23 V9 Z"
        fill="url(#aetheris-logo-grad)"
      />
      <path
        d="M5.5 16.5 H11.5 L14 11 L18 21 L20.5 16.5 H26.5"
        stroke="white"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        opacity="0.95"
      />
    </svg>
  )
}
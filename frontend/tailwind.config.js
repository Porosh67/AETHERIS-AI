/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aetheris: {
          bg:       '#0a0d14',
          surface:  '#111827',
          border:   '#1f2937',
          accent:   '#6366f1',
          success:  '#10b981',
          warning:  '#f59e0b',
          danger:   '#ef4444',
          muted:    '#6b7280',
          text:     '#f9fafb',
          subtext:  '#9ca3af',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}

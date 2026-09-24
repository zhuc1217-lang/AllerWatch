import type { ReactNode } from 'react'

export type IconName = 'home' | 'log' | 'history' | 'heart' | 'chart' | 'analysis' | 'wind' | 'leaf' | 'database' | 'refresh' | 'person'

const paths: Record<IconName, ReactNode> = {
  home: <><path d="m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9" /></>,
  log: <><path d="M9 5H6a1 1 0 0 0-1 1v15h14V6a1 1 0 0 0-1-1h-3M9 3h6v5H9zM9 13h6M9 17h4" /></>,
  history: <><rect x="3" y="3" width="18" height="18" rx="4" /><path d="M12 7v6h5" /></>,
  heart: <path d="M20.4 5.6a5.2 5.2 0 0 0-7.4 0l-1 1-1-1a5.2 5.2 0 0 0-7.4 7.4L12 21l8.4-8a5.2 5.2 0 0 0 0-7.4Z" />,
  chart: <><path d="M5 20v-7M12 20V4M19 20V9" strokeWidth="3" /></>,
  analysis: <><path d="m3 18 6-8 5 4 7-10" /><circle cx="3" cy="18" r="1" /><circle cx="9" cy="10" r="1" /><circle cx="14" cy="14" r="1" /><circle cx="21" cy="4" r="1" /></>,
  wind: <><path d="M3 8h12a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h5a3 3 0 1 1-3 3" /></>,
  leaf: <><path d="M5 18C1 9 10 4 21 3c-1 11-6 18-14 15M3 22c3-8 7-12 14-15" /></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0" /></>,
  refresh: <><path d="M20 7a9 9 0 1 0 1 8M20 3v5h-5" /></>,
  person: <><circle cx="12" cy="7" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2M17 17l2 2 3-4" /></>,
}

export default function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{paths[name]}</svg>
}

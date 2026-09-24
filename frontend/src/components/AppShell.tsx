import type { ReactNode } from 'react'
import Icon, { type IconName } from './Icon'

const navigation: { href: string; label: string; icon: IconName }[] = [
  { href: '/', label: 'Home', icon: 'home' },
  { href: '/log-symptoms', label: 'Log Symptoms', icon: 'log' },
  { href: '/history', label: 'History', icon: 'history' },
  { href: '/daily-health', label: 'Daily Health', icon: 'heart' },
  { href: '/dashboard', label: 'Dashboard', icon: 'chart' },
  { href: '/analysis', label: 'Analysis', icon: 'analysis' },
]

function LeafMark() {
  return <svg className="leaf-mark" viewBox="0 0 48 52" aria-hidden="true" focusable="false">
    <path d="M24 44C16 26 25 9 44 4c-1 21-8 31-20 34" fill="currentColor" opacity=".8" />
    <path d="M22 43C6 42 2 30 3 17c15 4 20 13 19 26" fill="currentColor" opacity=".6" />
    <path d="M24 49C20 31 31 17 37 12M23 44 10 26" fill="none" stroke="currentColor" strokeWidth="1.4" />
  </svg>
}

// Small, local SVG ornament: no downloaded artwork, animations or data encoding.
function BotanicalFooter() {
  return <svg className="sidebar-botanical" viewBox="0 0 240 350" preserveAspectRatio="xMidYMax slice" aria-hidden="true" focusable="false">
    <path d="M0 106 44 89 83 97 135 62 187 87 240 81V350H0Z" fill="currentColor" opacity=".08" />
    <path d="M0 140 45 120 92 143 154 117 195 130 240 113V350H0Z" fill="currentColor" opacity=".1" />
    <g fill="none" stroke="currentColor" strokeWidth="1.2" opacity=".36">
      <path d="M31 350C36 274 23 201 63 146M35 288 9 242M34 264 69 220M35 237 18 204M41 209 69 180M214 350c-10-61-4-113-42-153M210 298l25-30M204 271l-33-24M195 241l19-29" />
    </g>
    <g fill="currentColor" opacity=".24">
      <path d="M61 150c-17 5-24 17-21 30 15-5 21-14 21-30M42 207c2-18 14-27 30-28-4 17-15 24-30 28M34 235c-15-2-24-17-18-33 15 10 19 21 18 33M35 263c4-21 18-34 38-33-7 18-20 29-38 33M33 287c-21-7-28-23-25-39 18 8 26 20 25 39M33 312c9-21 23-28 42-25-11 18-24 23-42 25M173 197c18 1 28 12 27 29-18-6-24-16-27-29M195 246c-1-17 7-28 21-33 3 16-6 27-21 33M205 273c-19 0-31-8-35-23 17-2 31 7 35 23M210 297c2-16 12-27 26-28-2 16-10 24-26 28" />
    </g>
  </svg>
}

export default function AppShell({ path, children }: { path: string; children: ReactNode }) {
  return <div className="app-shell">
    <a className="skip-link" href="#page-content">Skip to content</a>
    <aside className="app-sidebar">
      <a className="sidebar-brand" href="/" aria-label="AllerWatch home"><LeafMark /><span>AllerWatch</span></a>
      <nav className="app-navigation" aria-label="Main navigation">
        {navigation.map(item => <a key={item.href} href={item.href} aria-current={(path || '/') === item.href ? 'page' : undefined}>
          <Icon name={item.icon} /><span>{item.label}</span>
        </a>)}
      </nav>
      <div className="sidebar-bottom">
        <BotanicalFooter />
        <div className="sidebar-note"><p className="eyebrow">Observe. Record. Reflect.</p><span className="sidebar-rule" />
          <p>AllerWatch</p><p>A personal health data study.<br />One observation at a time.</p></div>
      </div>
    </aside>
    <div className="app-workspace">
      <header className="app-masthead">
        <div><p className="masthead-title">AllerWatch</p><p className="masthead-subtitle">Allergic Rhinitis Health Data Platform</p></div>
        <div className="masthead-note"><LeafMark /><p>Small observations.<br />A longer view.</p></div>
      </header>
      <div className="app-content" id="page-content" tabIndex={-1}>{children}</div>
      <footer className="app-footer"><span>AllerWatch · Academic research prototype</span><span>Not for clinical decision-making</span></footer>
    </div>
  </div>
}

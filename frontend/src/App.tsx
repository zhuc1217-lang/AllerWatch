import { useEffect, useState } from 'react'
import LogSymptoms from './pages/LogSymptoms'
import History from './pages/History'
import Dashboard from './pages/Dashboard'
import Analysis from './pages/Analysis'
import DailyHealth from './pages/DailyHealth'
import EnvironmentalExposure from './components/EnvironmentalExposure'
import AppShell from './components/AppShell'
import AppConfig from './components/AppConfig'
import { apiUrl } from './api/base'

type BackendStatus = 'Checking' | 'Connected' | 'Unavailable'

export default function App() {
  const path = window.location.pathname.replace(/\/$/, '')
  const page = path === '/log-symptoms' ? <LogSymptoms />
    : path === '/history' ? <History />
    : path === '/dashboard' ? <Dashboard />
    : path === '/analysis' ? <Analysis />
    : path === '/daily-health' ? <DailyHealth /> : <Home />
  return <AppConfig><AppShell path={path}>{page}</AppShell></AppConfig>
}

function Home() {
  const [status, setStatus] = useState<BackendStatus>('Checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 5000)

    async function checkBackend() {
      setStatus('Checking')

      try {
        const response = await fetch(apiUrl('/health'), {
          signal: controller.signal,
          cache: 'no-store',
        })

        if (!response.ok) {
          throw new Error('Health request failed')
        }

        const body: unknown = await response.json()
        if (
          typeof body !== 'object' ||
          body === null ||
          !('status' in body) ||
          body.status !== 'ok'
        ) {
          throw new Error('Unexpected health response')
        }

        if (!cancelled) setStatus('Connected')
      } catch {
        if (!cancelled) setStatus('Unavailable')
      } finally {
        window.clearTimeout(timeout)
      }
    }

    void checkBackend()

    return () => {
      cancelled = true
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [attempt])

  return (
    <main className="page">
      <section className="intro" aria-labelledby="project-title">
        <p className="eyebrow">A personal observation journal</p>
        <h1 id="project-title">Home</h1>
        <p className="subtitle">Personal Allergic Rhinitis Health Data Tracker</p>
        <p className="description">
          Research prototype for exploring symptom and environmental data.
        </p>

        <div className="home-navigation">
          <a href="/log-symptoms">Log Symptoms →</a>
          <a href="/history">History →</a>
        </div>

        <div className="connection">
          <p className="status" data-status={status} role="status">
            <span className="status-dot" aria-hidden="true" />
            Backend status: {status}
          </p>
          {status === 'Unavailable' && (
            <div className="recovery">
              <p>Start the backend, then check the connection again.</p>
              <button type="button" onClick={() => setAttempt((value) => value + 1)}>
                Retry connection
              </button>
            </div>
          )}
        </div>
        <EnvironmentalExposure />
      </section>
    </main>
  )
}

import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { apiUrl } from '../api/base'

const ConfigContext = createContext<boolean | null>(null)
export const usePublicDemo = () => useContext(ConfigContext)

export default function AppConfig({ children }: { children: ReactNode }) {
  const [demo, setDemo] = useState<boolean | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    setFailed(false)
    void (async () => {
      try {
        const response = await fetch(apiUrl('/config'), { signal: controller.signal, cache: 'no-store' })
        const body: unknown = await response.json()
        if (!response.ok || !body || typeof body !== 'object' || !('public_demo_mode' in body) || typeof body.public_demo_mode !== 'boolean') {
          throw new Error('Invalid application configuration')
        }
        if (!cancelled) setDemo(body.public_demo_mode)
      } catch { if (!cancelled) setFailed(true) }
      finally { window.clearTimeout(timeout) }
    })()
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [attempt])
  return <ConfigContext.Provider value={demo}>
    {demo === true && <div className="demo-mode-banner" role="note"><strong>Demo mode — do not enter real health information</strong><span>Shared public demonstration. All submissions are labelled synthetic and visible to other visitors; data may reset.</span></div>}
    {demo === null && <div className="demo-mode-banner" role={failed ? 'alert' : 'status'}>
      {failed ? <><span>Cannot confirm application mode. Saving is disabled. Do not enter health information.</span><button onClick={() => setAttempt(value => value + 1)}>Retry application settings</button></> : 'Checking application mode before enabling submissions…'}
    </div>}
    {children}
  </ConfigContext.Provider>
}

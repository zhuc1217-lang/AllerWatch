import { useEffect, useState } from 'react'
import { getCurrentEnvironment } from '../api/environment'
import type { CurrentEnvironment } from '../types/environment'
import './EnvironmentalExposure.css'

type EnvironmentState =
  | { status: 'loading' }
  | { status: 'unavailable' }
  | { status: 'loaded'; data: CurrentEnvironment }

const formatReading = (value: number | null, unit: string) => value === null
  ? 'Unavailable'
  : `${new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value)}${unit ? ` ${unit}` : ''}`

// Explicitly keep environmental times in UTC; History's local display is separate.
const formatUtc = (timestamp: string) => `${new Date(timestamp).toISOString().slice(0, 19).replace('T', ' ')} UTC`

export default function EnvironmentalExposure() {
  const [state, setState] = useState<EnvironmentState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    // Longer than the backend's 10-second provider deadline, with local HTTP overhead.
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    setState({ status: 'loading' })
    async function loadEnvironment() {
      try {
        const data = await getCurrentEnvironment(controller.signal)
        if (!cancelled) setState({ status: 'loaded', data })
      } catch {
        if (!cancelled) setState({ status: 'unavailable' })
      } finally {
        window.clearTimeout(timeout)
      }
    }
    void loadEnvironment()
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [attempt])

  return (
    <section className="environment-section" aria-labelledby="environment-title">
      <h2 id="environment-title">Environmental Exposure</h2>
      <p className="environment-description">Current modelled outdoor conditions at the configured monitoring location. Provider valid times must be within the 3 hours preceding retrieval; older or future-valid sources are unavailable. Retrieval time is separate from source valid time.</p>

      {state.status === 'loading' && <p role="status">Loading environmental data…</p>}
      {state.status === 'unavailable' && (
        <div role="alert" className="environment-unavailable">
          <p>Environmental data are temporarily unavailable.</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry environmental data</button>
        </div>
      )}
      {state.status === 'loaded' && (
        <>
          <p className="environment-location">Monitoring coordinates: {state.data.latitude.toFixed(4)}, {state.data.longitude.toFixed(4)}</p>
          {state.data.status === 'partial' && <p className="environment-partial" role="status">Some environmental values are unavailable. Available values are shown below.</p>}
          <dl className="environment-values">
            <div><dt>Temperature</dt><dd>{formatReading(state.data.temperature_c, '°C')}</dd></div>
            <div><dt>Relative humidity</dt><dd>{formatReading(state.data.relative_humidity, '%')}</dd></div>
            <div><dt>PM2.5</dt><dd>{formatReading(state.data.pm2_5, 'µg/m³')}</dd></div>
            <div><dt>PM10</dt><dd>{formatReading(state.data.pm10, 'µg/m³')}</dd></div>
            <div><dt>US AQI</dt><dd>{formatReading(state.data.us_aqi, '')}</dd></div>
          </dl>
          <div className="environment-times">
            <p>Last updated: <time dateTime={state.data.timestamp}>{formatUtc(state.data.timestamp)}</time> (retrieved)</p>
            <p>Weather data time: {state.data.weather_timestamp ? <time dateTime={state.data.weather_timestamp}>{formatUtc(state.data.weather_timestamp)}</time> : 'Unavailable'}</p>
            <p>Air quality data time: {state.data.air_quality_timestamp ? <time dateTime={state.data.air_quality_timestamp}>{formatUtc(state.data.air_quality_timestamp)}</time> : 'Unavailable'}</p>
          </div>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>Refresh environmental data</button>
        </>
      )}
      <p className="environment-attribution">
        Data: <a href="https://open-meteo.com/">Open-Meteo</a> · Air quality: <a href="https://open-meteo.com/en/docs/air-quality-api">CAMS via Open-Meteo</a> (<a href="https://confluence.ecmwf.int/display/CKB/CAMS+Regional%3A+European+air+quality+analysis+and+forecast+data+documentation">CAMS ENSEMBLE</a>).
      </p>
    </section>
  )
}

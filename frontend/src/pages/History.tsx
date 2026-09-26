import ChinaAqiNote from '../components/ChinaAqiNote'
import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getSymptomRecords } from '../api/symptoms'
import { displayTimezone, filterHistory, formatChartTime, formatDate, formatTime, historyFilters, makeHistoryChartData } from '../history'
import type { HistoryFilter } from '../history'
import { symptomLabels } from '../types/symptoms'
import type { SymptomField, SymptomRecord } from '../types/symptoms'
import './History.css'

type HistoryState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; records: SymptomRecord[] }

const scoreLabels = ['None', 'Mild', 'Moderate', 'Severe']
const symptomFields = Object.keys(symptomLabels) as SymptomField[]

function exposureValue(value: number | null | undefined, unit = ''): string {
  return value == null ? 'Unavailable' : `${value}${unit ? ` ${unit}` : ''}`
}

function ExposureTime({ value }: { value: string | null | undefined }) {
  return value == null ? <>Unavailable</> : (
    <time dateTime={value}>{new Date(value).toISOString().slice(0, 19).replace('T', ' ')} UTC</time>
  )
}

function RecordDetails({ record }: { record: SymptomRecord }) {
  return (
    <details className="history-record">
      <summary>
        <span className="record-summary">
          <span><span className="record-label">Date</span><time dateTime={record.timestamp}>{formatDate(record.timestamp)}</time></span>
          <span><span className="record-label">Time</span>{formatTime(record.timestamp)}</span>
          <span><span className="record-label">TNSS</span>{record.tnss} / 12</span>
          <span><span className="record-label">Overall severity</span>{record.overall_severity} / 10</span>
          <span><span className="record-label">Medication taken</span>{record.medication_taken ? 'Yes' : 'No'}</span>
          <span className="record-expand"><span className="when-closed">Show details</span><span className="when-open">Hide details</span></span>
        </span>
        {record.is_synthetic && <span className="synthetic-label">Synthetic record</span>}
      </summary>
      <div className="record-body">
        <h3>Symptoms</h3>
        <dl className="record-fields">
          {symptomFields.map((field) => (
            <div key={field}><dt>{symptomLabels[field]}</dt><dd>{record[field]} — {scoreLabels[record[field]]}</dd></div>
          ))}
          <div><dt>Overall severity</dt><dd>{record.overall_severity} / 10</dd></div>
          <div><dt>TNSS</dt><dd>{record.tnss} / 12</dd></div>
          <div><dt>Medication taken</dt><dd>{record.medication_taken ? 'Yes' : 'No'}</dd></div>
          <div className="record-notes"><dt>Notes</dt><dd>{record.notes?.trim() ? record.notes : 'No notes provided.'}</dd></div>
        </dl>
        <section className="record-environment" aria-label="Environmental exposure">
          <h3>Environmental Exposure</h3>
          <p className="history-caption">Raw stored environmental snapshot: what was retrieved and saved, not exact personal exposure. Co-storage does not establish alignment with symptom time. Incompatible or unverified snapshots remain visible here but are excluded from contemporaneous relationship analysis.</p>
          <dl className="record-fields">
            <div><dt>Temperature</dt><dd>{exposureValue(record.temperature_c, '°C')}</dd></div>
            <div><dt>Relative humidity</dt><dd>{exposureValue(record.relative_humidity, '%')}</dd></div>
            <div><dt>PM2.5</dt><dd>{exposureValue(record.pm2_5, 'µg/m³')}</dd></div>
            <div><dt>PM10</dt><dd>{exposureValue(record.pm10, 'µg/m³')}</dd></div>
            <div><dt>NO₂</dt><dd>{exposureValue(record.nitrogen_dioxide, 'µg/m³')}</dd></div>
            <div><dt>SO₂</dt><dd>{exposureValue(record.sulfur_dioxide, 'µg/m³')}</dd></div>
            <div><dt>CO</dt><dd>{exposureValue(record.carbon_monoxide, 'µg/m³')}</dd></div>
            <div><dt>O₃</dt><dd>{exposureValue(record.ozone, 'µg/m³')}</dd></div>
            <div><dt>China AQI (estimated)</dt><dd>{exposureValue(record.china_aqi_estimate)}</dd></div>
            <div><dt>Estimated primary pollutant(s)</dt><dd>{record.china_aqi_estimate == null ? 'Unavailable' : record.china_aqi_primary_pollutant ?? 'None (AQI ≤ 50)'}</dd></div>
            <div><dt>Environmental snapshot retrieved</dt><dd><ExposureTime value={record.environment_timestamp} /></dd></div>
            <div><dt>Weather data time</dt><dd><ExposureTime value={record.weather_timestamp} /></dd></div>
            <div><dt>Air quality data time</dt><dd><ExposureTime value={record.air_quality_timestamp} /></dd></div>
            <div><dt>Monitoring coordinates</dt><dd>{record.environment_latitude == null || record.environment_longitude == null
              ? 'Unavailable' : `${record.environment_latitude}, ${record.environment_longitude}`}</dd></div>
          </dl>
          <ChinaAqiNote />
        </section>
      </div>
    </details>
  )
}

function HistoryChart({ records }: { records: SymptomRecord[] }) {
  const data = makeHistoryChartData(records)
  const first = data[0].timestamp
  const last = data[data.length - 1].timestamp
  // Give a lone timestamp space on either side so its point remains visible.
  const domain = first === last ? [first - 3600000, last + 3600000] : [first, last]
  const hasSynthetic = records.some((record) => record.is_synthetic)

  return (
    <section className="history-card" aria-labelledby="tnss-chart-title">
      <h2 id="tnss-chart-title">TNSS over time</h2>
      <p className="history-caption">Individual observations, oldest to newest. TNSS excludes eye symptoms.</p>
      <div className="history-chart" role="group" aria-label="TNSS by observation date and time, from 0 to 12. Values are also available in the records below.">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <LineChart data={data} margin={{ top: 12, right: 18, left: 0, bottom: 20 }} accessibilityLayer>
            <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              type="number" dataKey="timestamp" scale="time" domain={domain}
              tickFormatter={formatChartTime} tick={{ fontSize: 11, fill: 'var(--muted)' }}
              tickCount={4} minTickGap={24} height={52}
              label={{ value: 'Date / time', position: 'insideBottom', offset: -8, fill: 'var(--muted)', fontSize: 12 }}
            />
            <YAxis
              domain={[0, 12]} ticks={[0, 3, 6, 9, 12]} allowDecimals={false} width={42}
              tick={{ fontSize: 12, fill: 'var(--muted)' }}
              label={{ value: 'TNSS', angle: -90, position: 'insideLeft', fill: 'var(--muted)', fontSize: 12 }}
            />
            <Tooltip
              labelFormatter={(value) => `${formatDate(Number(value))}, ${formatTime(Number(value))}`}
              formatter={(value, name) => [`${value} / 12`, name]}
              isAnimationActive={false}
            />
            <Line type="linear" dataKey="tnss" name="TNSS" stroke="var(--chart-sage)" strokeWidth={2} dot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />
            {hasSynthetic && <Line type="linear" dataKey="syntheticTnss" name="TNSS (synthetic)" stroke="var(--chart-synthetic)" strokeDasharray="5 4" strokeWidth={2} dot={{ r: 4 }} connectNulls={false} isAnimationActive={false} />}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="history-caption">Points are recorded observations; connecting lines are a visual guide. Lines break across gaps longer than 24 hours.</p>
      {hasSynthetic && <p className="history-caption">Synthetic observations use grey points and dashed lines; real observations use green.</p>}
    </section>
  )
}

export default function History() {
  const [state, setState] = useState<HistoryState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [filter, setFilter] = useState<HistoryFilter>('all')
  const [filterTime, setFilterTime] = useState(Date.now)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setState({ status: 'loading' })

    async function loadRecords() {
      try {
        const records = await getSymptomRecords(controller.signal)
        if (!cancelled) {
          setFilterTime(Date.now())
          setState({ status: 'loaded', records })
        }
      } catch (error) {
        if (!cancelled) setState({
          status: 'error',
          message: controller.signal.aborted
            ? 'Loading symptom history timed out. Check the backend and try again.'
            : error instanceof TypeError
              ? 'Could not reach the backend. Check that it is running, then try again.'
              : error instanceof Error ? error.message : 'Could not load symptom history. Please try again.',
        })
      } finally {
        window.clearTimeout(timeout)
      }
    }

    void loadRecords()
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [attempt])

  function changeFilter(value: HistoryFilter) {
    setFilter(value)
    setFilterTime(Date.now())
  }

  const filtered = state.status === 'loaded' ? filterHistory(state.records, filter, filterTime) : []

  return (
    <main className="history-page">
      <header className="history-heading">
        <h1>History</h1>
        <p>Review your symptom observations over time.</p>
        <p className="history-timezone">Symptom dates and times shown in {displayTimezone}. Environmental timestamps are labelled in UTC.</p>
      </header>

      {state.status === 'loading' && <p className="history-card" role="status">Loading symptom records…</p>}
      {state.status === 'error' && (
        <div className="history-card history-error" role="alert">
          <p>{state.message}</p>
          <button type="button" onClick={() => setAttempt((value) => value + 1)}>Retry loading history</button>
        </div>
      )}
      {state.status === 'loaded' && (state.records.length === 0 ? (
        <section className="history-card history-empty">
          <p>No symptom records yet. Log your first symptom observation to begin building your longitudinal dataset.</p>
          <a href="/log-symptoms">Log your first symptom observation</a>
        </section>
      ) : (
        <>
          <fieldset className="history-filters">
            <legend>Time range</legend>
            <div className="history-filter-options">
              {historyFilters.map((option) => (
                <label key={option.value} className={filter === option.value ? 'is-selected' : ''}>
                  <input type="radio" name="history-filter" value={option.value} checked={filter === option.value} onChange={() => changeFilter(option.value)} />
                  {option.label}
                </label>
              ))}
            </div>
            <p className="history-caption">Recent filters cover the previous 7 or 30 days, measured in 24-hour periods.</p>
          </fieldset>
          <p className="history-count" role="status">Showing {filtered.length} of {state.records.length} records.</p>
          {filtered.length === 0 ? (
            <section className="history-card history-empty">
              <p>No symptom records in this time range.</p>
              <button type="button" onClick={() => changeFilter('all')}>Show all records</button>
            </section>
          ) : (
            <>
              <HistoryChart records={filtered} />
              <section className="history-records" aria-labelledby="records-title">
                <h2 id="records-title">Symptom records</h2>
                <p className="history-caption">Newest first. Select a record to see its details.</p>
                {filtered.map((record) => <RecordDetails key={record.id} record={record} />)}
              </section>
            </>
          )}
        </>
      ))}
    </main>
  )
}

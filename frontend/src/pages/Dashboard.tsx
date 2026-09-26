import ChinaAqiNote from '../components/ChinaAqiNote'
import { useEffect, useState } from 'react'
import { getSymptomRecords } from '../api/symptoms'
import { ChartLegend, ObservationLabel, RelationshipChart, TrendChart } from '../components/DashboardCharts'
import { displayValue, exposureMetrics, filterDashboard, observationTypes, summarizeDashboard, timeRanges } from '../dashboard'
import type { DashboardRange, ObservationType } from '../dashboard'
import { displayTimezone, formatDate, formatTime } from '../history'
import type { SymptomRecord } from '../types/symptoms'
import Icon from '../components/Icon'
import './Dashboard.css'

type DashboardState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; records: SymptomRecord[] }

function ObservationTable({ records }: { records: SymptomRecord[] }) {
  return (
    <details className="dashboard-card dashboard-data">
      <summary>View selected observations as a table</summary>
      <p className="dashboard-caption">Newest first. These are raw recorded values, including stored environmental snapshots excluded from relationship plots when time alignment cannot be established.</p>
      <div className="dashboard-table-scroll" role="region" aria-label="Selected observations table, scroll horizontally for all columns" tabIndex={0}>
        <table>
          <caption>Selected observations — times in {displayTimezone}</caption>
          <thead><tr>
            <th scope="col">Date / time</th><th scope="col">Observation type</th><th scope="col">TNSS / 12</th>
            <th scope="col">Overall / 10</th><th scope="col">Medication taken</th><th scope="col">PM2.5 (µg/m³)</th>
            <th scope="col">China AQI (estimated)</th><th scope="col">Humidity (%)</th>
          </tr></thead>
          <tbody>{records.map(record => <tr key={record.id}>
            <td><time dateTime={record.timestamp}>{formatDate(record.timestamp)}, {formatTime(record.timestamp)}</time></td>
            <td>{record.is_synthetic ? 'Synthetic development data' : 'Real observation'}</td>
            <td>{record.tnss}</td><td>{record.overall_severity}</td><td>{record.medication_taken ? 'Yes' : 'No'}</td>
            <td>{displayValue(record.pm2_5)}</td><td>{displayValue(record.china_aqi_estimate)}</td><td>{displayValue(record.relative_humidity)}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </details>
  )
}

export default function Dashboard() {
  const [state, setState] = useState<DashboardState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  const [range, setRange] = useState<DashboardRange>('all')
  const [type, setType] = useState<ObservationType>('all')
  const [filterTime, setFilterTime] = useState(Date.now)

  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setState({ status: 'loading' })
    async function load() {
      try {
        const records = await getSymptomRecords(controller.signal)
        if (!cancelled) {
          setFilterTime(Date.now())
          setState({ status: 'loaded', records })
        }
      } catch (error) {
        if (!cancelled) setState({
          status: 'error',
          message: controller.signal.aborted ? 'Loading dashboard data timed out. Check the backend and try again.'
            : error instanceof TypeError ? 'Could not reach the backend. Check that it is running, then try again.'
            : error instanceof Error ? error.message : 'Could not load dashboard data. Please try again.',
        })
      } finally {
        window.clearTimeout(timeout)
      }
    }
    void load()
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [attempt])

  const records = state.status === 'loaded' ? state.records : []
  const selected = filterDashboard(records, range, type, filterTime)
  const summary = summarizeDashboard(selected)
  const latest = summary.latest

  function resetFilters() {
    setRange('all'); setType('all'); setFilterTime(Date.now())
  }

  return (
    <main className="dashboard-page">
      <header className="dashboard-heading">
        <div><h1>Dashboard</h1>
          <p>Explore symptom observations and environmental snapshots over time.</p>
          <p className="dashboard-caption">Observation dates and times shown in {displayTimezone}.</p>
        </div>
        {state.status === 'loaded' && <button type="button" onClick={() => setAttempt(value => value + 1)}><Icon name="refresh" />Refresh observations</button>}
      </header>

      {state.status === 'loading' && <p className="dashboard-card" role="status">Loading dashboard data…</p>}
      {state.status === 'error' && <div className="dashboard-card dashboard-error" role="alert">
        <p>{state.message}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Retry loading dashboard</button>
      </div>}
      {state.status === 'loaded' && (records.length === 0 ? <section className="dashboard-card dashboard-empty">
        <p>No symptom observations are available yet.</p><a href="/log-symptoms">Log Symptoms</a>
      </section> : <>
        {summary.synthetic > 0 && <p className="dashboard-demo-notice" role="note">Includes synthetic development data. Synthetic observations are not real patient observations.</p>}
        {latest && <section className="dashboard-snapshot" aria-labelledby="latest-observation">
          <div className="snapshot-heading">
            <h2 id="latest-observation">Latest observation</h2>
            <p><time dateTime={latest.timestamp}>{formatDate(latest.timestamp)}, {formatTime(latest.timestamp)}</time><ObservationLabel synthetic={latest.is_synthetic} /></p>
          </div>
          <div className="dashboard-overview">
            <dl className="dashboard-metrics dashboard-latest">
              <div className="dashboard-metric"><dt><span className="metric-icon"><Icon name="person" /></span>Latest TNSS</dt><dd>{latest.tnss} <span>/ 12</span></dd></div>
              <div className="dashboard-metric"><dt><span className="metric-icon"><Icon name="chart" /></span>Overall severity</dt><dd>{latest.overall_severity} <span>/ 10</span></dd></div>
              <div className="dashboard-metric"><dt><span className="metric-icon"><Icon name="wind" /></span>Latest PM2.5</dt><dd className={latest.pm2_5 == null ? 'metric-unavailable' : ''}>{displayValue(latest.pm2_5)}{latest.pm2_5 != null && <span className="metric-unit">µg/m³</span>}</dd></div>
              <div className="dashboard-metric"><dt><span className="metric-icon"><Icon name="leaf" /></span>Latest China AQI (estimated)</dt><dd className={latest.china_aqi_estimate == null ? 'metric-unavailable' : ''}>{displayValue(latest.china_aqi_estimate)}</dd></div>
            </dl>
            <section className="dashboard-card dashboard-dataset" aria-labelledby="dataset-summary">
              <h2 id="dataset-summary"><Icon name="database" />Dataset summary</h2>
              <dl className="dashboard-summary">
                <div><dt>Total observations</dt><dd>{summary.total}</dd></div>
                <div><dt>Real</dt><dd>{summary.real}</dd></div>
                <div><dt>Synthetic</dt><dd>{summary.synthetic}</dd></div>
              </dl>
            </section>
          </div>
          <div className="snapshot-footnotes">
            <p className="dashboard-caption">Environmental values are raw stored snapshots. Relationship plots check time alignment separately.</p>
            <p className="dashboard-caption">Missing: PM2.5 <strong>{summary.missingPm25}</strong> · China AQI (estimated) <strong>{summary.missingAqi}</strong> · Humidity <strong>{summary.missingHumidity}</strong></p>
          </div>
        </section>}
        <section className="dashboard-filters" aria-label="Dashboard filters">
          <fieldset>
            <legend>Time range</legend>
            <div className="dashboard-options">{timeRanges.map(option => <label key={option.value} className={range === option.value ? 'is-selected' : ''}>
              <input type="radio" name="dashboard-range" value={option.value} checked={range === option.value}
                onChange={() => { setRange(option.value); setFilterTime(Date.now()) }} />{option.label}
            </label>)}</div>
          </fieldset>
          <fieldset>
            <legend>Observation type</legend>
            <div className="dashboard-options">{observationTypes.map(option => <label key={option.value} className={type === option.value ? 'is-selected' : ''}>
              <input type="radio" name="dashboard-type" value={option.value} checked={type === option.value}
                onChange={() => { setType(option.value); setFilterTime(Date.now()) }} />{option.label}
            </label>)}</div>
          </fieldset>
          <div className="dashboard-filter-context">
            <p className="dashboard-count" role="status">Showing {selected.length} of {records.length} observations.</p>
            {latest && <p className="dashboard-caption">Date range: {formatDate(summary.firstTimestamp!)} – {formatDate(summary.lastTimestamp!)}</p>}
          </div>
          <p className="dashboard-caption dashboard-filter-note">All panels use these filters. Recent ranges cover elapsed 24-hour periods; only available observations are shown.</p>
        </section>
        {!latest ? <section className="dashboard-card dashboard-empty">
          <p>No observations match these filters.</p><button type="button" onClick={resetFilters}>Show all data</button>
        </section> : <>
          <ChartLegend />
          <TrendChart records={selected} metric="tnss" title="Symptom Severity Over Time" subtitle="TNSS longitudinal trend" />
          <p className="dashboard-caption dashboard-chart-note">Points retain individual observations. Trend lines are straight visual guides and break at missing values, changes of observation type, and gaps longer than 24 hours. No daily averaging or smoothing is applied.</p>
          <section aria-labelledby="exposure-trends">
            <h2 id="exposure-trends">Environmental exposure trends</h2>
            <p className="dashboard-caption">Raw stored environmental snapshots, plotted at the associated symptom timestamps. Source times may differ or be incompatible; these raw values are not necessarily contemporaneous exposures or exact personal exposure measurements.</p>
            <div className="dashboard-chart-grid dashboard-exposure-grid">{exposureMetrics.map(metric =>
              <TrendChart key={metric.key} records={selected} metric={metric.key} title={metric.title} subtitle="Environmental snapshots" />)}</div>
          </section>
          <section aria-labelledby="relationships">
            <h2 id="relationships">Symptoms vs environment</h2>
            <p className="dashboard-caption">Exploratory visualisation of temporally aligned pairs. No correlation coefficients or fitted lines are shown.</p>
            <details className="dashboard-method-note"><summary>How environmental pairs are selected</summary>
              <p className="dashboard-caption">Observed relationship patterns use analytic contemporaneous exposures only. The same record's source valid time must be within the preceding 3 hours, never after the symptom time, with retrieval at or after source time. Retrieval may follow symptom submission. Backdated, stale or unverified pairs are excluded; raw snapshots remain stored. Missing numerical pairs and temporal exclusions are counted separately.</p>
            </details>
            <div className="dashboard-chart-grid dashboard-relationship-grid">{exposureMetrics.map(metric =>
              <RelationshipChart key={metric.key} records={selected} metric={metric.key} />)}</div>
          </section>
          <ObservationTable records={selected} />
        </>}
      </>)}
      <ChinaAqiNote />
      <p className="dashboard-disclaimer">Dashboard visualisations are exploratory and do not establish causal relationships. Synthetic observations are used for development and demonstration.</p>
    </main>
  )
}

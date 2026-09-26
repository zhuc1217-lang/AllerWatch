import { useEffect, useState } from 'react'
import { getLaggedAnalysis } from '../api/analysis'
import { formatPValue, formatStatistic, statusLabels, variableLabels } from '../analysis'
import { lagCellBackground, lagExposures, lagHours } from '../laggedAnalysis'
import type { DatasetMetadata, LaggedResponse } from '../types/analysis'

type LagState = { status: 'loading' } | { status: 'error'; message: string } | { status: 'loaded'; data: LaggedResponse }

export default function LaggedAssociations({ dataset }: { dataset: DatasetMetadata }) {
  const [state, setState] = useState<LagState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    setState({ status: 'loading' })
    void getLaggedAnalysis(dataset.dataset_mode, controller.signal).then(data => {
      const keys: (keyof DatasetMetadata)[] = ['record_count', 'real_count', 'synthetic_count', 'date_start', 'date_end']
      if (keys.some(key => data[key] !== dataset[key])) {
        throw new Error('The dataset changed while loading. Use Refresh analysis above to refresh all results.')
      }
      if (!cancelled) setState({ status: 'loaded', data })
    }).catch((error: unknown) => {
      if (!cancelled) setState({ status: 'error', message: controller.signal.aborted
        ? 'Loading lagged associations timed out. Please try again.'
        : error instanceof TypeError ? 'Could not reach the backend for lagged associations. Please try again.'
        : error instanceof Error ? error.message : 'Could not load lagged associations. Please try again.' })
    }).finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [dataset, attempt])
  const data = state.status === 'loaded' && state.data.dataset_mode === dataset.dataset_mode ? state.data : null
  return <section className="analysis-card lagged-section" aria-labelledby="lagged-title">
    <h2 id="lagged-title">Lagged Environmental Associations</h2>
    <p className="analysis-caption">This exploratory analysis compares TNSS with environmental observations measured at different approximate time lags before symptom reporting.</p>
    <p className="analysis-caption">Research question: Do environmental exposures measured before symptom reporting show different associations with allergic rhinitis symptom severity?</p>
    {(dataset.dataset_mode === 'synthetic_only' || dataset.synthetic_count > 0) && <p className="analysis-notice" role="note">
      {dataset.dataset_mode === 'synthetic_only'
        ? 'These lagged results are based on synthetic development data and are not clinical findings.'
        : 'These lagged results include synthetic development data and are not clinical findings.'}
    </p>}
    {state.status === 'loading' && <p role="status">Loading lagged associations…</p>}
    {state.status === 'error' && <div className="analysis-error lagged-error" role="alert">
      <p>{state.message}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Retry lagged associations</button>
    </div>}
    {data && <>
      <p className="analysis-caption">{data.record_count} symptom observations considered: {data.real_count} real, {data.synthetic_count} synthetic. Counts below are valid pairs for each exposure and lag.</p>
      <div className="analysis-table-scroll" role="region" aria-label="Lagged association matrix, scroll horizontally for all lags" tabIndex={0}>
        <table className="lagged-matrix">
          <caption>Approximate lag comparison — Spearman rho (ρ); n and p-values shown in every cell</caption>
          <thead><tr><th scope="col">Exposure</th>{lagHours.map(lag => <th key={lag} scope="col">{lag}h</th>)}</tr></thead>
          <tbody>{lagExposures.map(variable => <tr key={variable}>
            <th scope="row">{variableLabels[variable]}</th>
            {lagHours.map(lag => {
              const item = data.results.find(result => result.variable === variable && result.lag_hours === lag)!
              const rho = item.status === 'ok' ? item.spearman_rho : null
              return <td key={lag} data-lag-cell={`${variable}-${lag}`} style={{ backgroundColor: lagCellBackground(rho) }}>
                <strong>{formatStatistic(rho, 3)}</strong>
                <span>n = {item.n} · missing = {item.missing_pairs}</span>
                <span>p = {formatPValue(item.p_value)}</span>
                <span>{statusLabels[item.status]}</span>
              </td>
            })}
          </tr>)}</tbody>
        </table>
      </div>
      <p className="analysis-caption lagged-legend">
        <span style={{ backgroundColor: lagCellBackground(-1) }}>−1 negative</span>
        <span style={{ backgroundColor: lagCellBackground(0) }}>0</span>
        <span style={{ backgroundColor: lagCellBackground(1) }}>+1 positive</span>
        Colour intensity represents |rho| on a fixed scale, not significance or risk.
      </p>
      {!data.results.some(item => item.status === 'ok') && <p>No lagged coefficients are available for this dataset. At least {data.minimum_pairs} complete pairs and variation in both variables are required.</p>}
      <details className="lagged-details">
        <summary>View matching coverage and actual time offsets</summary>
        <div className="analysis-table-scroll" role="region" aria-label="Lag matching coverage table" tabIndex={0}>
          <table><caption>Actual offset = symptom time minus matched source valid time, in hours</caption>
            <thead><tr>{['Exposure', 'Lag', 'Real pairs', 'Synthetic pairs', 'Distinct source records', 'Min hours', 'Median hours', 'Max hours'].map(label => <th key={label} scope="col">{label}</th>)}</tr></thead>
            <tbody>{data.results.map(item => <tr key={`${item.variable}-${item.lag_hours}`}>
              <th scope="row">{variableLabels[item.variable]}</th><td>{item.lag_hours}h</td><td>{item.real_pairs}</td><td>{item.synthetic_pairs}</td>
              <td>{item.distinct_source_records}</td><td>{formatStatistic(item.actual_lag_hours_min)}</td>
              <td>{formatStatistic(item.actual_lag_hours_median)}</td><td>{formatStatistic(item.actual_lag_hours_max)}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </details>
    </>}
    <div className="analysis-caption lagged-method">
      <p><strong>Approximate snapshot matching, not exact hourly exposure.</strong> Only symptom-time snapshots are stored. Environmental measurements represent estimated ambient conditions rather than true individual exposure.</p>
      <p>In UTC, target = symptom time − lag. For 6/12/24h, choose the latest available source valid time in [target − 3 hours, target]. The source report and retrieval must also be at or before target. Later or more distant snapshots are not used. Air-quality source times apply to PM2.5/China AQI (estimated); weather source times apply to humidity. Missing source times or values stay missing.</p>
      <p>0h uses only the same report’s snapshot, with source valid time within the previous 3 hours. Its download can finish after symptom validation; that completion time is not an exposure time. Source valid times after symptom reporting are excluded. This is a contemporaneous comparison, not a prediction using information already available at reporting time.</p>
      <p>Nominal 6/12/24h therefore spans actual offsets of 6–9/12–15/24–27h. Real and synthetic records never supply exposure to each other. Nonzero matches also require the same known monitoring coordinates for real records; fictional synthetic records may share an unknown location.</p>
      <p>Different lags may use different subsets, and a source snapshot can be reused. Compare direction, magnitude and coverage together. A larger |rho| does not identify a confirmed delay. This pattern is exploratory and does not demonstrate a delayed causal effect.</p>
      <p>Multiple exposure-lag combinations are explored, so individual p-values should be interpreted cautiously. Repeated observations and reused snapshots are dependent; p-values are unadjusted, approximate and not confirmatory evidence.</p>
    </div>
  </section>
}

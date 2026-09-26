import ChinaAqiNote from '../components/ChinaAqiNote'
import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getAnalysis } from '../api/analysis'
import LaggedAssociations from '../components/LaggedAssociations'
import DailyHealthAssociations from '../components/DailyHealthAssociations'
import RiskModel from '../components/RiskModel'
import { usePublicDemo } from '../components/AppConfig'
import { coefficientChartData, datasetOptions, formatPValue, formatStatistic, statusLabels, variableKeys, variableLabels } from '../analysis'
import { displayTimezone, formatDate, formatTime } from '../history'
import type { AnalysisResponse, AssociationResult, DatasetMode, DescriptiveSummary } from '../types/analysis'
import './Analysis.css'

type LoadState = { status: 'loading' } | { status: 'error'; message: string } |
  { status: 'loaded'; mode: DatasetMode; data: AnalysisResponse }
const summaryFields: (keyof Omit<DescriptiveSummary, 'n' | 'missing'>)[] = ['mean', 'median', 'std', 'min', 'q1', 'q3', 'max']

function CoefficientChart({ results }: { results: AssociationResult[] }) {
  const data = coefficientChartData(results)
  return <section className="analysis-card" aria-labelledby="coefficient-title">
    <h2 id="coefficient-title">Exploratory association summary</h2>
    <p className="analysis-caption">Spearman coefficients with TNSS. Unavailable results are omitted; the table above gives every paired sample count and status.</p>
    {data.length === 0 ? <p className="analysis-chart-empty">No coefficients are available for this dataset.</p> :
      <div className="analysis-chart" role="group" aria-label="Spearman coefficients from minus one to plus one; exact values in the associations table">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 12, right: 22, bottom: 30, left: 0 }} accessibilityLayer>
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]}
              tick={{ fontSize: 12 }} label={{ value: 'Spearman rho (ρ)', position: 'bottom', offset: 10 }} />
            <YAxis type="category" dataKey="label" width={155} tick={{ fontSize: 11 }} tickLine={false} />
            <Tooltip formatter={value => [formatStatistic(typeof value === 'number' ? value : null, 3), 'Spearman rho']}
              contentStyle={{ fontSize: 13, borderColor: 'var(--border-strong)' }} cursor={false} />
            <ReferenceLine x={0} stroke="var(--ink)" strokeWidth={2} />
            <Bar dataKey="rho" name="Spearman rho" fill="var(--chart-sage)" barSize={24} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>}
  </section>
}

export default function Analysis() {
  const publicDemo = usePublicDemo()
  const [mode, setMode] = useState<DatasetMode>('real_only')
  useEffect(() => { if (publicDemo === true) setMode('synthetic_only') }, [publicDemo])
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState<LoadState>({ status: 'loading' })
  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    setState({ status: 'loading' })
    void getAnalysis(mode, controller.signal).then(data => {
      if (!cancelled) setState({ status: 'loaded', mode, data })
    }).catch((error: unknown) => {
      if (!cancelled) setState({ status: 'error', message: controller.signal.aborted
        ? 'Loading analysis timed out. Check the backend and try again.'
        : error instanceof TypeError ? 'Could not reach the backend. Check that it is running, then try again.'
        : error instanceof Error ? error.message : 'Could not load analysis. Please try again.' })
    }).finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [mode, attempt])
  // Never render the previous dataset under the newly selected label.
  const data = state.status === 'loaded' && state.mode === mode ? state.data : null
  const summary = data?.descriptive
  const selectedLabel = datasetOptions.find(option => option.value === mode)!.label
  return <main className="analysis-page">
    <header className="analysis-heading">
      <h1>Analysis</h1><p>Descriptive statistics and exploratory environmental associations.</p>
    </header>
    <fieldset className="analysis-selector">
      <legend>Dataset</legend><div className="analysis-options">{datasetOptions.map(option =>
        <label key={option.value} className={mode === option.value ? 'is-selected' : ''}>
          <input type="radio" name="analysis-dataset" checked={mode === option.value}
            onChange={() => setMode(option.value)} />{option.label}
        </label>)}</div>
    </fieldset>
    <p className="analysis-caption">{publicDemo ? 'Public demo defaults to synthetic observations; no real health dataset is provided.' : 'Real data is the default, even with few observations.'} All stored dates are included; Dashboard filters do not apply here.</p>
    {mode === 'synthetic_only' && <p className="analysis-notice" role="note">Development dataset: synthetic observations. These are not real patient observations.</p>}
    {mode === 'all' && summary?.includes_synthetic && <p className="analysis-notice" role="note">Includes synthetic development data. Synthetic observations are not real patient observations.</p>}
    {(state.status === 'loading' || (state.status === 'loaded' && !data)) && <p className="analysis-card" role="status">Loading analysis…</p>}
    {state.status === 'error' && <div className="analysis-card analysis-error" role="alert">
      <p>{state.message}</p><button onClick={() => setAttempt(value => value + 1)}>Retry loading analysis</button>
    </div>}
    {data && summary && <>
      <section className="analysis-card" aria-labelledby="analysis-overview">
        <h2 id="analysis-overview">Dataset overview</h2>
        <dl className="analysis-overview">
          <div><dt>Selected dataset</dt><dd>{selectedLabel}</dd></div>
          <div><dt>Observations</dt><dd>{summary.record_count}</dd></div>
          <div><dt>Real observations</dt><dd>{summary.real_count}</dd></div>
          <div><dt>Synthetic observations</dt><dd>{summary.synthetic_count}</dd></div>
          <div className="analysis-dates"><dt>Observation date range ({displayTimezone})</dt><dd>
            {summary.date_start && summary.date_end ?
              `${formatDate(summary.date_start)}, ${formatTime(summary.date_start)} – ${formatDate(summary.date_end)}, ${formatTime(summary.date_end)}` : 'Unavailable'}
          </dd></div>
        </dl>
        <p className="analysis-caption">This is an exploratory within-person observation-level analysis. The unit is one recorded symptom observation. Multiple observations on the same day remain separate, so days with more reports receive more observation-level weight. A DailyHealthRecord may be reused for several same-date symptom observations; counts are not independent people or days.</p>
        {summary.record_count === 0 && <p role="status">No symptom observations are available for this dataset.</p>}
        <button type="button" onClick={() => setAttempt(value => value + 1)}>Refresh analysis</button>
      </section>
      <section className="analysis-card" aria-labelledby="descriptive-title">
        <h2 id="descriptive-title">Descriptive statistics</h2>
        <div className="analysis-table-scroll" role="region" aria-label="Descriptive statistics, scroll horizontally for all columns" tabIndex={0}>
          <table><caption>{selectedLabel} — non-missing values; environmental summaries use raw stored snapshots</caption>
            <thead><tr>{['Variable', 'n', 'Missing', 'Mean', 'Median', 'SD', 'Min', 'Q1', 'Q3', 'Max'].map(label =>
              <th key={label} scope="col">{label}</th>)}</tr></thead>
            <tbody>{variableKeys.map(variable => {
              const item = summary.variables[variable]
              return <tr key={variable} data-variable={variable}><th scope="row">{variableLabels[variable]}</th>
                <td>{item.n}</td><td>{item.missing}</td>{summaryFields.map(field => <td key={field}>{formatStatistic(item[field])}</td>)}
              </tr>
            })}</tbody>
          </table>
        </div>
        <p className="analysis-caption">SD is the sample standard deviation (n − 1); unavailable for fewer than two values. Q1 and Q3 are the 25th and 75th percentiles (linear quantile method). Missing values are excluded, never filled with zero.</p>
      </section>
      <section className="analysis-card" aria-labelledby="associations-title">
        <h2 id="associations-title">Environmental associations</h2>
        <div className="analysis-table-scroll" role="region" aria-label="Environmental associations, scroll horizontally for all columns" tabIndex={0}>
          <table><caption>{selectedLabel} — {data.associations.record_count} symptom observations; analytic contemporaneous exposures only</caption>
            <thead><tr>{['Environmental variable', 'Aligned pairs (n)', 'Temporally excluded', 'Missing pairs', 'Spearman rho', 'p-value', 'Status'].map(label =>
              <th key={label} scope="col">{label}</th>)}</tr></thead>
            <tbody>{data.associations.associations.map(item => <tr key={item.variable} data-association={item.variable}>
              <th scope="row">{variableLabels[item.variable]}</th><td>{item.n}</td><td>{item.temporally_excluded_pairs}</td><td>{item.missing_pairs}</td>
              <td>{formatStatistic(item.spearman_rho, 3)}</td><td>{formatPValue(item.p_value)}</td><td>{statusLabels[item.status]}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="analysis-caption">At least {data.associations.minimum_pairs} temporally aligned complete pairs and variation in both variables are required. This threshold does not guarantee reliable estimates. For each exposure, total observations = aligned pairs + temporally excluded + missing pairs. Missing numerical values are counted first; otherwise missing or incompatible time metadata counts as temporally excluded.</p>
        <p className="analysis-caption">Source valid time must be within the {data.associations.temporal_tolerance_hours} hours preceding the symptom time, including both boundaries. Retrieval must exist and be at or after source time; it may follow symptom submission. No historical exposure is inferred or substituted.</p>
      </section>
      <CoefficientChart results={data.associations.associations} />
      <ChinaAqiNote />
      <LaggedAssociations dataset={summary} />
      <DailyHealthAssociations dataset={summary} />
      <RiskModel dataset={summary} />
    </>}
    <section className="analysis-methodology" aria-labelledby="methodology-title">
      <h2 id="methodology-title">Methodology and limitations</h2>
      <p>Spearman rank correlation is used to explore monotonic associations between TNSS and environmental variables. Analyses use paired non-missing observations. These exploratory associations do not establish causal relationships.</p>
      <p>P-values are exploratory and are not evidence of causality. Multiple environmental variables are being examined, so results should be interpreted cautiously.</p>
      <p>The displayed p-values are unadjusted, two-sided asymptotic estimates. Repeated observations within one person are not independent, and small samples and tied ranks limit the approximation. These p-values are not confirmatory or clinical evidence.</p>
      <p>Raw stored snapshots are ambient estimates, not exact personal exposure. Co-storage does not establish alignment: a backdated symptom may have a later snapshot. Ordinary associations and lag-0 require the same contemporaneous time eligibility; incompatible snapshots remain unchanged in History and raw descriptive summaries. The lagged section uses the documented approximate matching rule; there is no daily aggregation, imputation, or automatic outlier removal.</p>
      {mode !== 'real_only' && <p>Synthetic observations are fictional development data. Associations in those records describe simulation assumptions, not patient findings.</p>}
    </section>
  </main>
}

import { useEffect, useState } from 'react'
import { getDailyAssociations } from '../api/analysis'
import { formatPValue, formatStatistic, statusLabels } from '../analysis'
import { dailyLabels } from '../types/dailyHealth'
import type { DailyAssociationsResponse } from '../types/dailyHealth'
import type { DatasetMetadata } from '../types/analysis'

export default function DailyHealthAssociations({ dataset }: { dataset: DatasetMetadata }) {
  const [data, setData] = useState<DailyAssociationsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    setData(null); setError(null)
    void getDailyAssociations(dataset.dataset_mode, controller.signal).then(result => {
      const keys: (keyof DatasetMetadata)[] = ['record_count', 'real_count', 'synthetic_count', 'date_start', 'date_end']
      if (keys.some(key => result[key] !== dataset[key])) throw new Error('Symptoms changed while loading. Use Refresh analysis to refresh all results.')
      if (!cancelled) setData(result)
    }).catch((failure: unknown) => {
      if (!cancelled) setError(controller.signal.aborted ? 'Daily health analysis timed out. Please retry.'
        : failure instanceof TypeError ? 'Could not reach the backend. Please retry.'
        : failure instanceof Error ? failure.message : 'Could not load daily health associations.')
    }).finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [dataset, attempt])
  return <section className="analysis-card daily-associations" aria-labelledby="daily-associations-title">
    <h2 id="daily-associations-title">Daily Health Associations</h2>
    <p className="analysis-caption">Exploratory within-person, observation-level associations between TNSS and same-date self-reported sleep, stress and activity. Each symptom observation receives one unit of weight; a daily summary may be reused for multiple observations. No daily averaging is applied.</p>
    {(dataset.dataset_mode === 'synthetic_only' || dataset.synthetic_count > 0) && <p className="analysis-notice" role="note">
      {dataset.dataset_mode === 'synthetic_only' ? 'These daily health results are based on synthetic development data and are not clinical findings.'
        : 'These daily health results include synthetic development data and are not clinical findings.'}
    </p>}
    {!data && !error && <p role="status">Loading daily health associations…</p>}
    {error && <div className="analysis-error lagged-error" role="alert"><p>{error}</p>
      <button onClick={() => setAttempt(n => n + 1)}>Retry daily health analysis</button></div>}
    {data && data.dataset_mode === dataset.dataset_mode && <>
      <p className="analysis-caption">Study calendar: {data.calendar_timezone}. {data.matched_symptom_count} of {data.record_count} symptom observations matched to {data.matched_daily_records} daily summaries; {data.missing_daily_symptom_count} symptom observations have no compatible daily summary.</p>
      <p className="analysis-caption">Selected daily records: {data.daily_record_count} ({data.real_daily_count} real, {data.synthetic_daily_count} synthetic). {data.daily_records_without_symptoms} daily records have no matching symptom observations.</p>
      <div className="analysis-table-scroll" role="region" aria-label="Daily health associations, scroll horizontally" tabIndex={0}>
        <table><caption>TNSS and same-date daily health — paired non-missing observations</caption>
          <thead><tr>{['Variable', 'n', 'Missing pairs', 'Daily summaries', 'Spearman rho', 'p-value', 'Status'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
          <tbody>{data.associations.map(item => <tr key={item.variable} data-daily-association={item.variable}>
            <th scope="row">{dailyLabels[item.variable]}</th><td>{item.n}</td><td>{item.missing_pairs}</td><td>{item.distinct_daily_records}</td>
            <td>{formatStatistic(item.spearman_rho, 3)}</td><td>{formatPValue(item.p_value)}</td><td>{statusLabels[item.status]}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p className="analysis-caption">At least {data.minimum_pairs} complete pairs and variation in both variables are required. This threshold is not a guarantee of reliable estimates.</p>
    </>}
    <p className="analysis-caption">Each symptom timestamp is converted to the fixed study calendar date and matched only to a daily summary of the same real/synthetic type. Unmatched symptoms remain missing, never zero. Multiple same-day symptoms reuse a daily summary, so n is not a count of independent days.</p>
    <p className="analysis-caption">Sleep duration is manually entered and is not equivalent to clinically measured sleep. Stress is subjective. Confounding and repeated observations limit interpretation; same-day associations do not establish temporal direction or causality. P-values are unadjusted exploratory approximations across multiple variables. Synthetic patterns describe the simulation assumptions, not lifestyle effects.</p>
  </section>
}

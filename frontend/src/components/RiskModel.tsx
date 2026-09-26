import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getRiskModel } from '../api/riskModel'
import { formatStatistic } from '../analysis'
import { modelFeatureLabels } from '../types/riskModel'
import type { ClassBalance, ModelPeriod, RiskModelResponse } from '../types/riskModel'
import type { DatasetMetadata } from '../types/analysis'
import './RiskModel.css'

function utcDate(value: string | null) {
  return value ? new Date(value).toLocaleString('en-GB', { timeZone: 'UTC', year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : 'Unavailable'
}
function dates(period: ModelPeriod) { return period.n ? `${utcDate(period.target_start)} – ${utcDate(period.target_end)}` : 'Unavailable' }
function ClassCounts({ data }: { data: ClassBalance }) {
  return <>{data.positive} high ({formatStatistic(data.positive_percent, 1)}%), {data.negative} low ({formatStatistic(data.negative_percent, 1)}%)</>
}
function Coefficients({ data }: { data: RiskModelResponse }) {
  const chartData = data.coefficients.map(c => ({ label: modelFeatureLabels[c.feature],
    positive: c.coefficient >= 0 ? c.coefficient : null, negative: c.coefficient < 0 ? c.coefficient : null }))
  const limit = Math.max(1, ...data.coefficients.map(c => Math.abs(c.coefficient)))
  return <>
    <h3>Model coefficients</h3>
    <p className="analysis-caption">Coefficient direction reflects the fitted model and does not establish a causal relationship. Values are log-odds coefficients per training standard deviation, not Spearman correlations. Correlated environmental inputs can make coefficients unstable.</p>
    <div className="risk-coefficient-chart" style={{ height: Math.max(310, chartData.length * 38 + 65) }} role="group" aria-label="Signed model coefficients; exact values in the table below">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ top: 8, right: 18, bottom: 28, left: 0 }} accessibilityLayer>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" domain={[-limit, limit]} tick={{ fontSize: 11 }} label={{ value: 'Model coefficient', position: 'bottom', offset: 8 }} />
          <YAxis type="category" dataKey="label" width={145} tick={{ fontSize: 11 }} tickLine={false} />
          <Tooltip formatter={(value, name) => [formatStatistic(typeof value === 'number' ? value : null, 3), name]} cursor={false} />
          <ReferenceLine x={0} stroke="var(--ink)" strokeWidth={2} />
          <Bar dataKey="positive" name="Positive model coefficient" stackId="coefficient" fill="var(--chart-blue)" barSize={20} isAnimationActive={false} />
          <Bar dataKey="negative" name="Negative model coefficient" stackId="coefficient" fill="var(--chart-ochre)" barSize={20} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
    <div className="analysis-table-scroll" role="region" aria-label="Model coefficients and missingness, scroll horizontally" tabIndex={0}>
      <table><caption>Signed model coefficients; missing counts are before training-median imputation</caption>
        <thead><tr>{['Feature', 'Model coefficient', 'Training missing', 'Test missing'].map(k => <th scope="col" key={k}>{k}</th>)}</tr></thead>
        <tbody>{data.coefficients.map(c => <tr key={c.feature} data-model-coefficient={c.feature}>
          <th scope="row">{modelFeatureLabels[c.feature]}</th><td>{formatStatistic(c.coefficient, 3)}</td><td>{c.train_missing}</td><td>{c.test_missing}</td>
        </tr>)}</tbody>
      </table>
    </div>
    <p className="analysis-caption">Intercept: {formatStatistic(data.intercept, 3)}. {data.feature_count} predictors fitted. Entirely missing training columns were excluded: {data.omitted_features.map(k => modelFeatureLabels[k]).join(', ') || 'None'}.</p>
  </>
}

export default function RiskModel({ dataset }: { dataset: DatasetMetadata }) {
  const [data, setData] = useState<RiskModelResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    setData(null); setError(null)
    if (dataset.dataset_mode === 'all') return
    const controller = new AbortController(); let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    void getRiskModel(dataset.dataset_mode, controller.signal).then(result => {
      const keys: (keyof DatasetMetadata)[] = ['record_count', 'real_count', 'synthetic_count', 'date_start', 'date_end']
      if (keys.some(k => result[k] !== dataset[k])) throw new Error('Symptoms changed while loading. Use Refresh analysis to refresh all results.')
      if (!cancelled) setData(result)
    }).catch((failure: unknown) => {
      if (!cancelled) setError(controller.signal.aborted ? 'Experimental model request timed out. Please retry.'
        : failure instanceof TypeError ? 'Could not reach the backend. Please retry.'
        : failure instanceof Error ? failure.message : 'Could not load the experimental model.')
    }).finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [dataset, attempt])
  const visible = data?.dataset_mode === dataset.dataset_mode ? data : null
  const m = visible?.metrics
  const matrix = m?.confusion_matrix
  return <section className="analysis-card risk-model-section" aria-labelledby="risk-model-title">
    <h2 id="risk-model-title">Experimental Symptom Risk Model</h2>
    <p className="analysis-notice" role="note"><strong>Research prototype only. This model is not intended for medical diagnosis or clinical decision-making.</strong></p>
    {dataset.dataset_mode === 'synthetic_only' && <p className="analysis-notice" role="note">This model is trained on synthetic development data. Performance metrics are demonstrations of the modelling pipeline, not clinical findings.</p>}
    <p className="analysis-caption">Prediction target: the next symptom observation has TNSS ≥ 6. This is an operational research threshold, not a validated clinical cutoff. It predicts the next recorded observation, with a variable time interval.</p>
    {dataset.dataset_mode === 'all' ? <p className="risk-disabled" role="status">Model training is disabled for All data. Select Real data or Synthetic data above; real and synthetic observations are never mixed for training.</p> : <>
      {!visible && !error && <p role="status">Loading experimental model…</p>}
      {error && <div className="analysis-error lagged-error" role="alert"><p>{error}</p><button onClick={() => setAttempt(n => n + 1)}>Retry experimental model</button></div>}
      {visible && <>
        <p className="analysis-caption">{visible.model_row_count} usable pairs from {visible.record_count} selected symptom observations. Excluded pairs: {Object.values(visible.excluded_pair_counts).reduce((a, b) => a + b, 0)}.</p>
        {visible.status !== 'ok' && <div className="risk-unavailable" role="status"><h3>{visible.status === 'insufficient_data' ? 'Insufficient data for model training' : 'Model unavailable'}</h3><ul>{visible.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul></div>}
        {visible.status === 'ok' && m && matrix && <>
          <dl className="analysis-overview risk-summary">
            <div><dt>Training observations</dt><dd>{visible.training.n}</dd></div>
            <div><dt>Test observations</dt><dd>{visible.testing.n}</dd></div>
            <div><dt>High-symptom prevalence (all model targets)</dt><dd>{formatStatistic(visible.class_balance.positive_percent, 1)}%</dd></div>
            <div><dt>Predictors used</dt><dd>{visible.feature_count}</dd></div>
            <div className="analysis-dates"><dt>Training target period (UTC)</dt><dd>{dates(visible.training)}</dd></div>
            <div className="analysis-dates"><dt>Test target period (UTC)</dt><dd>{dates(visible.testing)}</dd></div>
            <div className="analysis-dates"><dt>First test prediction point (UTC)</dt><dd>{utcDate(visible.first_test_prediction_time)}</dd></div>
          </dl>
          <p className="analysis-caption">All targets: <ClassCounts data={visible.class_balance} />. Training: <ClassCounts data={visible.training} />. Testing: <ClassCounts data={visible.testing} />.</p>
          <p className="analysis-caption">Prediction-to-target intervals: {formatStatistic(visible.horizon_hours.min, 2)}–{formatStatistic(visible.horizon_hours.max, 2)} hours; median {formatStatistic(visible.horizon_hours.median, 2)} hours.</p>
          <div className="analysis-table-scroll" role="region" aria-label="Temporal test metrics" tabIndex={0}>
            <table><caption>Temporal test-set performance; fixed classification threshold 0.5</caption><thead><tr><th scope="col">Measure</th><th scope="col">Value</th></tr></thead>
              <tbody><tr data-model-metric="baseline_accuracy"><th scope="row">Training-majority baseline accuracy</th><td>{formatStatistic(visible.baseline_accuracy, 3)}</td></tr>
                {(['accuracy', 'precision', 'recall', 'f1', 'roc_auc'] as const).map(key => <tr key={key} data-model-metric={key}>
                  <th scope="row">{{ accuracy: 'Logistic Regression accuracy', precision: 'Precision', recall: 'Recall', f1: 'F1', roc_auc: 'ROC-AUC' }[key]}</th><td>{formatStatistic(m[key], 3)}</td>
                </tr>)}
              </tbody></table>
          </div>
          <p className="analysis-caption">Baseline always predicts the training majority: {visible.baseline_class === 1 ? 'high' : 'low'} symptom burden. Baseline and model are evaluated on the same held-out targets.</p>
          {Object.entries(m.unavailable_reasons).map(([key, reason]) => <p className="analysis-caption" key={key}>{reason}</p>)}
          <h3>Confusion matrix</h3>
          <div className="analysis-table-scroll" role="region" aria-label="Confusion matrix" tabIndex={0}>
            <table className="risk-confusion"><caption>Actual and predicted test targets</caption><thead><tr><th scope="col">Actual / predicted</th><th scope="col">Predicted low</th><th scope="col">Predicted high</th></tr></thead>
              <tbody><tr><th scope="row">Actual low</th><td data-confusion="tn">{matrix.true_negatives}</td><td data-confusion="fp">{matrix.false_positives}</td></tr>
                <tr><th scope="row">Actual high</th><td data-confusion="fn">{matrix.false_negatives}</td><td data-confusion="tp">{matrix.true_positives}</td></tr></tbody></table>
          </div>
          <Coefficients data={visible} />
        </>}
        <details className="lagged-details"><summary>Feature availability and excluded pairs</summary>
          <p className="analysis-caption">Daily candidates checked: {Object.entries(visible.daily_candidate_counts).map(([reason, count]) => `${reason.replaceAll('_', ' ')}: ${count}`).join('; ') || 'No model pairs'}.</p>
          <p className="analysis-caption">Pair exclusions: {Object.entries(visible.excluded_pair_counts).map(([reason, count]) => `${reason.replaceAll('_', ' ')}: ${count}`).join('; ') || 'None'}.</p>
        </details>
      </>}
    </>}
    <h3>Modelling method and limitations</h3>
    <p className="analysis-caption">Consecutive observations are paired within the selected real or synthetic dataset. Predictors come from the previous report after snapshot completion and any known server receipt time, strictly before the next observation. Unknown legacy receipt times are not invented. Target-observation symptoms and environment are never predictors. Stale, future or untimed exposure values remain missing.</p>
    <p className="analysis-caption">The oldest approximately 80% of pairs train one fixed logistic regression; the newest approximately 20% test it. No random train/test shuffling was used. Median imputation and standardisation are fitted on training data only. Entirely missing training columns are omitted, never filled with zero. The frozen model evaluates sequential next-observation predictions, so an earlier observed test symptom can inform a later test prediction; there is no test-set refitting.</p>
    <p className="analysis-caption">The model has seven environmental/symptom candidate predictors (entirely missing training columns are omitted): previous TNSS, previous overall severity, PM2.5, PM10, China AQI (estimated), humidity and temperature. Previous-day sleep, quality, stress and exercise remain excluded: historical availability cannot be safely established. Server last-edit timestamps are now recorded prospectively, but do not reconstruct earlier diary versions or enable these four candidates. Medication is excluded because timing is ambiguous.</p>
    <p className="analysis-caption">Small N-of-1 datasets contain dependent repeated observations and self-report measurement error. Ambient conditions are exposure estimates. Historical availability is limited to recorded report/retrieval timestamps. Coefficients and prediction performance do not establish causality, and performance may not generalise to another person. This experiment has no clinical validation, calibration assessment or individual prediction display.</p>
  </section>
}

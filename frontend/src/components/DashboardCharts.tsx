import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { exposureMetrics, relationshipData, makeTrendData, metricDomain, metricValue, displayValue } from '../dashboard'
import type { ExposureKey, MetricKey } from '../dashboard'
import { formatChartTime, formatDate, formatTime } from '../history'
import type { SymptomRecord } from '../types/symptoms'

const realColour = 'var(--chart-sage)'
const syntheticColour = 'var(--chart-synthetic)'
const metricColour = (metric: MetricKey) => metric === 'us_aqi' ? 'var(--chart-ochre)'
  : metric === 'relative_humidity' ? 'var(--chart-blue)' : 'var(--chart-sage)'
const tick = { fontSize: 11, fill: 'var(--muted)' }
const margin = { top: 12, right: 16, left: 0, bottom: 14 }

export function ObservationLabel({ synthetic }: { synthetic: boolean }) {
  return <span className="dashboard-type">{synthetic ? '◇ Synthetic — development data' : '○ Real observation'}</span>
}

export function ChartLegend() {
  return <p className="dashboard-legend"><span>○ Real: circles / solid lines</span><span>◇ Synthetic: diamonds / dashed lines</span></p>
}

type DotProps = {
  cx?: number; cy?: number; value?: unknown
  colour?: string
  payload?: { record?: SymptomRecord | null }
}
function ObservationDot({ cx, cy, payload, value, colour }: DotProps) {
  const record = payload?.record
  if (cx == null || cy == null || !Number.isFinite(cx) || !Number.isFinite(cy) || !record || value === null) return <g />
  const common = { className: 'dashboard-point', 'data-record-id': record.id,
    'data-synthetic': String(record.is_synthetic), strokeWidth: 1.5, fill: 'var(--surface)' }
  return record.is_synthetic
    ? <path {...common} d={`M ${cx} ${cy - 4} L ${cx + 4} ${cy} L ${cx} ${cy + 4} L ${cx - 4} ${cy} Z`} stroke={colour ?? syntheticColour} />
    : <circle {...common} cx={cx} cy={cy} r={3.5} stroke={colour ?? realColour} />
}

type TooltipProps = {
  active?: boolean
  payload?: readonly { payload?: { record?: SymptomRecord | null } }[]
  metric: MetricKey
}
function ObservationTooltip({ active, payload, metric }: TooltipProps) {
  const record = payload?.find(entry => entry.payload?.record)?.payload?.record
  if (!active || !record) return null
  const exposure = exposureMetrics.find(item => item.key === metric)
  return (
    <div className="dashboard-tooltip">
      <p><time dateTime={record.timestamp}>{formatDate(record.timestamp)}, {formatTime(record.timestamp)}</time></p>
      <p><ObservationLabel synthetic={record.is_synthetic} /></p>
      <dl>
        <div><dt>TNSS</dt><dd>{record.tnss} / 12</dd></div>
        {exposure ? <div><dt>{exposure.label}</dt><dd>{displayValue(metricValue(record, metric), exposure.unit)}</dd></div> : <>
          <div><dt>Overall severity</dt><dd>{record.overall_severity} / 10</dd></div>
          <div><dt>Medication taken</dt><dd>{record.medication_taken ? 'Yes' : 'No'}</dd></div>
        </>}
      </dl>
    </div>
  )
}

export function TrendChart({ records, metric, title, subtitle }: {
  records: SymptomRecord[]; metric: MetricKey; title: string; subtitle: string
}) {
  const data = makeTrendData(records, metric)
  const available = records.filter(record => metricValue(record, metric) !== null)
  const first = data[0]?.timestamp ?? 0
  const last = data.at(-1)?.timestamp ?? first
  const domain = first === last ? [first - 3600000, last + 3600000] : [first, last]
  const exposure = exposureMetrics.find(item => item.key === metric)
  const label = metric === 'tnss' ? 'TNSS' : exposure!.axis
  return (
    <section className="dashboard-card dashboard-chart-card" aria-labelledby={`trend-${metric}`} data-chart={`trend-${metric}`}>
      <h3 id={`trend-${metric}`}>{title}</h3>
      <p className="dashboard-caption">{subtitle}</p>
      {available.length === 0 ? <p className="dashboard-chart-empty">No {exposure?.label ?? 'TNSS'} values are available for these observations.</p> : (
        <div className="dashboard-chart" role="group" aria-label={`${title}. Exact values are in the selected observations table.`}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={data} margin={margin} accessibilityLayer>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis type="number" dataKey="timestamp" scale="time" domain={domain}
                tickFormatter={formatChartTime} tick={tick} tickCount={3} minTickGap={22} height={60}
                label={{ value: 'Observation date / time', position: 'insideBottom', offset: -5, ...tick }} />
              <YAxis domain={metricDomain(records, metric)} ticks={metric === 'tnss' ? [0, 3, 6, 9, 12] : undefined}
                allowDecimals={metric === 'pm2_5'} width={55} tick={tick}
                label={{ value: label, angle: -90, position: 'insideLeft', ...tick }} />
              <Tooltip content={<ObservationTooltip metric={metric} />} isAnimationActive={false} />
              {available.some(record => !record.is_synthetic) && <Line name="Real" type="linear" dataKey="real" stroke={metricColour(metric)}
                strokeWidth={1.5} dot={<ObservationDot colour={metricColour(metric)} />} activeDot={false} connectNulls={false} isAnimationActive={false} />}
              {available.some(record => record.is_synthetic) && <Line name="Synthetic" type="linear" dataKey="synthetic" stroke={metricColour(metric)}
                strokeDasharray="5 4" strokeWidth={1.5} dot={<ObservationDot colour={metricColour(metric)} />} activeDot={false} connectNulls={false} isAnimationActive={false} />}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="dashboard-caption">{available.length} observations with {exposure?.label ?? 'TNSS'} values; {records.length - available.length} missing.</p>
    </section>
  )
}

export function RelationshipChart({ records, metric }: { records: SymptomRecord[]; metric: ExposureKey }) {
  const exposure = exposureMetrics.find(item => item.key === metric)!
  const { points: data, total, missingPairs, temporallyExcludedPairs } = relationshipData(records, metric)
  const title = `TNSS vs ${metric === 'relative_humidity' ? 'Relative Humidity' : exposure.label}`
  const real = data.filter(point => !point.record.is_synthetic)
  const synthetic = data.filter(point => point.record.is_synthetic)
  return (
    <section className="dashboard-card dashboard-chart-card" aria-labelledby={`scatter-${metric}`} data-chart={`scatter-${metric}`}>
      <h3 id={`scatter-${metric}`}>{title}</h3>
      <p className="dashboard-caption">Exploratory visualisation — temporally aligned pairs only</p>
      {data.length < 2 ? <p className="dashboard-chart-empty">Not enough paired observations to display this relationship.</p> : (
        <div className="dashboard-chart" role="group" aria-label={`${title}. Exact values are in the selected observations table.`}>
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <ScatterChart margin={margin} accessibilityLayer>
              <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
              <XAxis type="number" dataKey="x" domain={metricDomain(data.map(point => point.record), metric)} name={exposure.label} tickCount={4}
                tick={tick} height={60} label={{ value: exposure.axis, position: 'insideBottom', offset: -5, ...tick }} />
              <YAxis type="number" dataKey="y" name="TNSS" domain={[0, 12]} ticks={[0, 3, 6, 9, 12]} tick={tick} width={42}
                label={{ value: 'TNSS', angle: -90, position: 'insideLeft', ...tick }} />
              <Tooltip content={<ObservationTooltip metric={metric} />} isAnimationActive={false} cursor={{ strokeDasharray: '3 3' }} />
              {real.length > 0 && <Scatter name="Real observations" data={real} shape={<ObservationDot />} line={false} isAnimationActive={false} />}
              {synthetic.length > 0 && <Scatter name="Synthetic development data" data={synthetic} shape={<ObservationDot />} line={false} isAnimationActive={false} />}
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
      <p className="dashboard-caption">{total} symptom observations: {data.length} temporally aligned pairs; {temporallyExcludedPairs} temporally excluded; {missingPairs} missing pairs.</p>
    </section>
  )
}

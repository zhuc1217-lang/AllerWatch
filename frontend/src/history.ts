import type { SymptomRecord } from './types/symptoms'

export type HistoryFilter = '7' | '30' | 'all'

export const historyFilters: { value: HistoryFilter; label: string }[] = [
  { value: '7', label: 'Last 7 days' },
  { value: '30', label: 'Last 30 days' },
  { value: 'all', label: 'All records' },
]

const dayInMilliseconds = 24 * 60 * 60 * 1000

export function filterHistory(records: SymptomRecord[], filter: HistoryFilter | '90', now: number): SymptomRecord[] {
  const earliest = now - Number(filter) * dayInMilliseconds
  return records.filter((record) => {
    if (filter === 'all') return true
    const timestamp = Date.parse(record.timestamp)
    return timestamp >= earliest && timestamp <= now
  }).sort((left, right) => Date.parse(right.timestamp) - Date.parse(left.timestamp) || right.id - left.id)
}

export type HistoryPoint = {
  timestamp: number
  tnss: number | null
  syntheticTnss: number | null
}

export function makeHistoryChartData(records: SymptomRecord[]): HistoryPoint[] {
  const chronological = [...records].sort((left, right) =>
    Date.parse(left.timestamp) - Date.parse(right.timestamp) || left.id - right.id)
  const points: HistoryPoint[] = []

  for (const record of chronological) {
    const timestamp = Date.parse(record.timestamp)
    const previous = points.at(-1)
    if (previous && timestamp - previous.timestamp > dayInMilliseconds) {
      // A null marker breaks the line; it is not an observation or an imputed zero.
      points.push({ timestamp: previous.timestamp + (timestamp - previous.timestamp) / 2, tnss: null, syntheticTnss: null })
    }
    // Use only the API's TNSS; synthetic and real observations are separate series.
    points.push({ timestamp, tnss: record.is_synthetic ? null : record.tnss, syntheticTnss: record.is_synthetic ? record.tnss : null })
  }
  return points
}

const dateFormatter = new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
const timeFormatter = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })
const chartFormatter = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })

export const displayTimezone = dateFormatter.resolvedOptions().timeZone
export const formatDate = (timestamp: string | number) => dateFormatter.format(new Date(timestamp))
export const formatTime = (timestamp: string | number) => timeFormatter.format(new Date(timestamp))
export const formatChartTime = (timestamp: number) => chartFormatter.format(new Date(timestamp))

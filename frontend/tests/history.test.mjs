import assert from 'node:assert/strict'
import test from 'node:test'
import { filterHistory, makeHistoryChartData } from '../src/history.ts'

const now = Date.parse('2026-09-18T12:00:00Z')
const day = 86400000
const record = (id, timestamp, tnss = 6, is_synthetic = false) => ({
  id, timestamp: typeof timestamp === 'string' ? timestamp : new Date(timestamp).toISOString(),
  nasal_congestion: 1, sneezing: 2, runny_nose: 3, nasal_itching: 0, eye_symptoms: 3,
  overall_severity: 7, medication_taken: false, notes: null, tnss, is_synthetic,
})

for (const days of [7, 30]) {
  test(`${days}-day window includes both endpoints and excludes older/future records`, () => {
    const records = [
      record(1, now - days * day - 1), record(2, now - days * day),
      record(3, now - 1), record(4, now), record(5, now + 1),
    ]
    assert.deepEqual(filterHistory(records, String(days), now).map((row) => row.id), [4, 3, 2])
  })
}

test('all records has no time restriction and sorting does not mutate the API array', () => {
  const records = [record(1, now - 100 * day), record(2, now + day), record(3, now)]
  const snapshot = structuredClone(records)
  assert.deepEqual(filterHistory(records, 'all', now).map((row) => row.id), [2, 3, 1])
  assert.deepEqual(records, snapshot)
})

test('timezone offsets denote absolute instants; ties use descending IDs without merging', () => {
  const records = [
    record(1, '2026-09-11T20:00:00+08:00'),
    record(2, '2026-09-11T12:00:00Z'),
    record(3, '2026-09-11T11:59:59.999Z'),
  ]
  assert.deepEqual(filterHistory(records, '7', now).map((row) => row.id), [2, 1])
})

test('filters use elapsed hours across daylight-saving transitions', () => {
  const end = Date.parse('2026-03-09T12:00:00-04:00')
  const records = [record(1, '2026-03-02T11:00:00-05:00'), record(2, '2026-03-02T10:59:59.999-05:00')]
  assert.deepEqual(filterHistory(records, '7', end).map((row) => row.id), [1])
})

test('chart preserves returned TNSS, zero values, chronology, and multiple same-time observations', () => {
  // Deliberately independent returned TNSS proves no frontend sum is substituted.
  const records = [record(4, now, 12), record(2, now - 3600000, 0), record(3, now, 8)]
  const snapshot = structuredClone(records)
  assert.deepEqual(makeHistoryChartData(records), [
    { timestamp: now - 3600000, tnss: 0, syntheticTnss: null },
    { timestamp: now, tnss: 8, syntheticTnss: null },
    { timestamp: now, tnss: 12, syntheticTnss: null },
  ])
  assert.deepEqual(records, snapshot)
})

test('gaps longer than 24 hours insert a null break, never an invented score', () => {
  const points = makeHistoryChartData([record(1, now - 3 * day, 4), record(2, now, 7)])
  assert.equal(points.length, 3)
  assert.deepEqual(points[1], { timestamp: now - 1.5 * day, tnss: null, syntheticTnss: null })
  assert.deepEqual(points.filter((point) => point.tnss !== null).map((point) => point.tnss), [4, 7])
  assert.equal(makeHistoryChartData([record(1, now - day), record(2, now)]).length, 2)
})

test('synthetic and real observations are not joined into one series', () => {
  assert.deepEqual(makeHistoryChartData([record(1, now - 60000, 5, true), record(2, now, 6)]), [
    { timestamp: now - 60000, tnss: null, syntheticTnss: 5 },
    { timestamp: now, tnss: 6, syntheticTnss: null },
  ])
})

test('empty filters and a single observation stay empty or single, without fabrication', () => {
  assert.deepEqual(filterHistory([record(1, now - 40 * day)], '30', now), [])
  assert.deepEqual(makeHistoryChartData([]), [])
  assert.deepEqual(makeHistoryChartData([record(1, now, 0)]), [{ timestamp: now, tnss: 0, syntheticTnss: null }])
})

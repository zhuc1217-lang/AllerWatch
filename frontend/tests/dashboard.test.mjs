import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { displayValue, filterDashboard, makePairedData, makeTrendData, metricDomain, relationshipData, summarizeDashboard } from '../src/dashboard.ts'

const now = Date.parse('2026-09-19T12:00:00Z')
const day = 86400000
const record = (id, timestamp, extras = {}) => ({
  id, timestamp: typeof timestamp === 'string' ? timestamp : new Date(timestamp).toISOString(),
  nasal_congestion: 1, sneezing: 1, runny_nose: 1, nasal_itching: 1, eye_symptoms: 3,
  tnss: 8, overall_severity: 7, medication_taken: false, is_synthetic: false,
  notes: null, pm2_5: 10, us_aqi: 40, relative_humidity: 50,
  environment_time_eligible: { pm2_5: true, pm10: true, us_aqi: true, relative_humidity: true, temperature_c: true }, ...extras,
})

for (const days of [7, 30, 90]) {
  test(`shared ${days}-day filter is inclusive, uses absolute time, and excludes future rows`, () => {
    const rows = [record(1, now-days*day-1), record(2, now-days*day), record(3, now), record(4, now+1)]
    assert.deepEqual(filterDashboard(rows, String(days), 'all', now).map(r => r.id), [3, 2])
    assert.deepEqual(rows.map(r => r.id), [1, 2, 3, 4])
  })
}

test('time and real/synthetic filters intersect without changing source rows', () => {
  const rows = [record(1, now, { is_synthetic: true }), record(2, now-day), record(3, now-50*day, { is_synthetic: true })]
  const copy = structuredClone(rows)
  assert.deepEqual(filterDashboard(rows, '7', 'real', now).map(r => r.id), [2])
  assert.deepEqual(filterDashboard(rows, '7', 'synthetic', now).map(r => r.id), [1])
  assert.deepEqual(filterDashboard(rows, 'all', 'synthetic', now).map(r => r.id), [1, 3])
  assert.deepEqual(filterDashboard(rows, 'all', 'all', now).map(r => r.id), [1, 2, 3])
  assert.deepEqual(rows, copy)
})

test('timezone offsets, DST and stable timestamp ties retain every observation', () => {
  const time = Date.parse('2026-03-09T12:00:00-04:00')
  const rows = [record(1, '2026-03-02T11:00:00-05:00'), record(2, '2026-03-02T16:00:00Z'), record(3, '2026-03-02T10:59:59-05:00')]
  assert.deepEqual(filterDashboard(rows, '7', 'all', time).map(r => r.id), [2, 1])
  assert.equal(summarizeDashboard(rows).latest.id, 2)
})

test('summary counts missing fields separately and never treats measured zero as missing', () => {
  const rows = [
    record(3, now, { pm2_5: null, us_aqi: 0, relative_humidity: undefined }),
    record(1, now-day, { pm2_5: 0, us_aqi: null, relative_humidity: 0, is_synthetic: true }),
    record(2, now-day/2, { is_synthetic: true }),
  ]
  const summary = summarizeDashboard(rows)
  assert.deepEqual({ ...summary, latest: null }, {
    total: 3, real: 1, synthetic: 2, latest: null,
    firstTimestamp: rows[1].timestamp, lastTimestamp: rows[0].timestamp,
    missingPm25: 1, missingAqi: 1, missingHumidity: 1,
  })
  assert.equal(summary.latest.id, 3)
  assert.equal(summary.latest.pm2_5, null) // No fallback to an older non-missing reading.
})

test('filtered summary and latest observation follow the selection', () => {
  const rows = [record(1, now, { is_synthetic: true }), record(2, now-day)]
  assert.equal(summarizeDashboard(filterDashboard(rows, 'all', 'real', now)).latest.id, 2)
  assert.equal(summarizeDashboard(filterDashboard(rows, 'all', 'synthetic', now)).real, 0)
})

test('empty and unmatched datasets have no latest observation or chart data', () => {
  const empty = filterDashboard([record(1, now-100*day)], '90', 'all', now)
  assert.equal(summarizeDashboard(empty).total, 0)
  assert.equal(summarizeDashboard(empty).latest, null)
  assert.equal(summarizeDashboard(empty).firstTimestamp, null)
  assert.deepEqual(makeTrendData(empty, 'tnss'), [])
  assert.deepEqual(makePairedData(empty, 'pm2_5'), [])
})

for (const key of ['pm2_5', 'us_aqi', 'relative_humidity']) {
  test(`${key} eligible scatter keeps zeros, drops its own missing pairs and retains provenance`, () => {
    const rows = [record(1, now-2000, { [key]: null }), record(2, now-1000, { [key]: undefined }),
      record(3, now, { [key]: 0, is_synthetic: true }), record(4, now, { [key]: 25 })]
    const points = makePairedData(rows, key)
    assert.deepEqual(points.map(p => [p.record.id, p.x, p.y]), [[3, 0, 8], [4, 25, 8]])
    assert.equal(points[0].record.is_synthetic, true)
    assert.equal(points[1].record.is_synthetic, false)
    assert.equal(points.length, 2) // Duplicate timestamps are not deduplicated.
    const onlyMissing = rows.slice(0, 2)
    assert.deepEqual(makePairedData(onlyMissing, key), [])
    const other = key === 'pm2_5' ? 'us_aqi' : 'pm2_5'
    assert.equal(makePairedData([record(8, now, { [key]: 5, [other]: null })], key).length, 1)
  })
}

test('TNSS chart preserves backend values without calculating from symptom or eye scores', () => {
  const rows = [record(1, now, { tnss: 0 }), record(3, now+2000, { tnss: 12 }), record(2, now+1000, { tnss: 7 })]
  assert.deepEqual(makeTrendData(rows, 'tnss').map(p => p.real), [0, 7, 12])
})

test('missing trend measurements remain null points and do not become zero or get dropped', () => {
  const rows = [record(1, now-2000, { pm2_5: 12 }), record(2, now-1000, { pm2_5: null }), record(3, now, { pm2_5: 0 })]
  const points = makeTrendData(rows, 'pm2_5')
  assert.deepEqual(points.map(p => p.real), [12, null, 0])
  assert.deepEqual(points.map(p => p.record.id), [1, 2, 3])
})

test('real and synthetic trend series cannot join across observation types', () => {
  const rows = [record(1, now-2000), record(2, now-1000, { is_synthetic: true }), record(3, now)]
  const points = makeTrendData(rows, 'tnss')
  assert.deepEqual(points.map(p => p.real), [8, null, 8])
  assert.deepEqual(points.map(p => p.synthetic), [null, 8, null])
})

test('gaps longer than 24 hours break all trend series without creating a record', () => {
  const points = makeTrendData([record(1, now-3*day), record(2, now)], 'us_aqi')
  assert.equal(points.length, 3)
  assert.deepEqual(points[1], { timestamp: now-1.5*day, real: null, synthetic: null, record: null })
  assert.equal(makeTrendData([record(1, now-day), record(2, now)], 'tnss').length, 2)
})

test('single observations and constant zeros have valid axis domains without invented data', () => {
  const rows = [record(1, now, { tnss: 0, pm2_5: 0, us_aqi: 0 })]
  assert.equal(makeTrendData(rows, 'tnss').length, 1)
  assert.equal(makePairedData(rows, 'pm2_5').length, 1)
  assert.deepEqual(metricDomain(rows, 'tnss'), [0, 12])
  assert.deepEqual(metricDomain(rows, 'relative_humidity'), [0, 100])
  assert.deepEqual(metricDomain(rows, 'pm2_5'), [0, 1])
  assert.deepEqual(metricDomain([], 'us_aqi'), [0, 1])
})

test('null/undefined display as unavailable and actual zeros keep their units', () => {
  assert.equal(displayValue(null, 'µg/m³'), 'Unavailable')
  assert.equal(displayValue(undefined), 'Unavailable')
  assert.equal(displayValue(0, 'µg/m³'), '0 µg/m³')
  assert.equal(displayValue(0), '0')
})

test('summary and chart preparation do not mutate records or supplied ordering', () => {
  const rows = Object.freeze([
    Object.freeze(record(3, now, { is_synthetic: true, us_aqi: null })),
    Object.freeze(record(1, now-day)), Object.freeze(record(2, now-day/2)),
  ])
  const copy = structuredClone(rows)
  summarizeDashboard(rows)
  makeTrendData(rows, 'us_aqi')
  makePairedData(rows, 'relative_humidity')
  metricDomain(rows, 'pm2_5')
  assert.deepEqual(rows, copy)
})

// These API-shaped fixtures are also checked against the actual Python eligibility
// helper by test_environment_timing.py, so client flags cannot drift from the rule.
const timingRecords = JSON.parse(readFileSync(new URL('./fixtures/contemporaneous-records.json', import.meta.url), 'utf8'))
for (const key of ['pm2_5', 'us_aqi', 'relative_humidity']) {
  test(`${key} excludes backdated, future, stale and unverified snapshots without changing raw values`, () => {
    const before = structuredClone(timingRecords)
    const result = relationshipData(timingRecords, key)
    const ids = key === 'relative_humidity' ? [1, 7, 8] : [1, 7]
    assert.deepEqual(result.points.map(point => point.record.id).sort((a, b) => a-b), ids)
    assert.equal(result.total, 9)
    assert.equal(result.missingPairs, 1)
    assert.equal(result.temporallyExcludedPairs, 8 - ids.length)
    assert.equal(result.total, result.points.length + result.missingPairs + result.temporallyExcludedPairs)
    assert.equal(result.points.find(point => point.record.id === 7).x, 0)
    assert.equal(makeTrendData(timingRecords, key).filter(point => point.record?.id === 2)[0].synthetic, 21)
    assert.equal(summarizeDashboard(timingRecords).total, 9)
    assert.deepEqual(timingRecords, before)
  })
}

test('older API responses without time eligibility fail closed for relationships, remain readable as raw data', () => {
  const raw = record(1, now, { environment_time_eligible: undefined })
  assert.deepEqual(makePairedData([raw], 'pm2_5'), [])
  assert.equal(relationshipData([raw], 'pm2_5').temporallyExcludedPairs, 1)
  assert.equal(makeTrendData([raw], 'pm2_5')[0].real, 10)
})

test('a missing numerical outcome is counted once as missing, not as a temporal exclusion', () => {
  const raw = record(1, now, { tnss: null, environment_time_eligible: undefined })
  const result = relationshipData([raw], 'pm2_5')
  assert.equal(result.missingPairs, 1)
  assert.equal(result.temporallyExcludedPairs, 0)
  assert.deepEqual(result.points, [])
})

test('an entirely backdated dataset yields no relationship points but retains raw history/trend data', () => {
  const backdated = timingRecords.filter(record => record.id === 2)
  for (const key of ['pm2_5', 'us_aqi', 'relative_humidity']) {
    assert.deepEqual(makePairedData(backdated, key), [])
    assert.equal(relationshipData(backdated, key).temporallyExcludedPairs, 1)
    assert.equal(makeTrendData(backdated, key)[0].synthetic, 21)
  }
})

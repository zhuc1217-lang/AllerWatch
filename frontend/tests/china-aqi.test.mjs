import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { getCurrentEnvironment } from '../src/api/environment.ts'
import { exposureKeys, variableLabels } from '../src/analysis.ts'
import { exposureMetrics, summarizeDashboard, makePairedData } from '../src/dashboard.ts'
import { lagExposures } from '../src/laggedAnalysis.ts'
import { modelFeatureLabels } from '../src/types/riskModel.ts'

const complete = {
  timestamp: '2026-09-18T10:30:00Z', weather_timestamp: '2026-09-18T10:15:00Z',
  air_quality_timestamp: '2026-09-18T10:00:00Z', status: 'available', latitude: 51.5, longitude: -0.12,
  temperature_c: 20, relative_humidity: 50, pm2_5: 0, pm10: 0, nitrogen_dioxide: 0,
  sulfur_dioxide: 0, carbon_monoxide: 7500, ozone: 0, china_aqi_estimate: 75, china_aqi_primary_pollutant: 'CO',
}

test('all active chart, analysis, lag and model keys use the estimated China metric', () => {
  for (const keys of [exposureKeys, lagExposures, Object.keys(modelFeatureLabels), exposureMetrics.map(r => r.key)]) {
    assert.ok(keys.includes('china_aqi_estimate'))
    assert.ok(!keys.includes('us_aqi'))
  }
  assert.match(variableLabels.china_aqi_estimate, /China AQI \(estimated\)/)
  assert.equal(modelFeatureLabels.china_aqi_estimate, 'China AQI (estimated)')
  assert.ok(exposureKeys.includes('pm2_5') && exposureKeys.includes('pm10'))
  const note = readFileSync(new URL('../src/components/ChinaAqiNote.tsx', import.meta.url), 'utf8')
  assert.match(note, /HJ 633—2026/)
  assert.match(note, /not an official monitoring-station AQI/)
  for (const file of ['pages/Dashboard.tsx', 'pages/Analysis.tsx', 'pages/History.tsx', 'components/EnvironmentalExposure.tsx']) {
    const source = readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8')
    assert.match(source, /<ChinaAqiNote/)
    assert.doesNotMatch(source, /US AQI|\.us_aqi/)
  }
})

test('current environmental API retains raw CO units and authoritative estimated AQI', async context => {
  context.mock.method(globalThis, 'fetch', async () => Response.json(complete))
  const result = await getCurrentEnvironment(new AbortController().signal)
  assert.equal(result.china_aqi_estimate, 75)
  assert.equal(result.carbon_monoxide, 7500)
  assert.equal(result.pm2_5, 0)
})

test('one missing gas keeps raw PM but requires a null full AQI', async context => {
  const partial = { ...complete, ozone: null, status: 'partial', china_aqi_estimate: null, china_aqi_primary_pollutant: null }
  context.mock.method(globalThis, 'fetch', async () => Response.json(partial))
  assert.equal((await getCurrentEnvironment(new AbortController().signal)).china_aqi_estimate, null)
  context.mock.method(globalThis, 'fetch', async () => Response.json({ ...partial, china_aqi_estimate: 0 }))
  await assert.rejects(getCurrentEnvironment(new AbortController().signal), /unavailable/)
})

test('legacy US index is never used as a fallback for missing China AQI', () => {
  const record = { id: 1, timestamp: complete.timestamp, tnss: 4, overall_severity: 4, is_synthetic: true,
    medication_taken: false, pm2_5: 0, us_aqi: 88, china_aqi_estimate: null, relative_humidity: 50,
    environment_time_eligible: { pm2_5: true, china_aqi_estimate: true, relative_humidity: true } }
  assert.equal(summarizeDashboard([record]).missingAqi, 1)
  assert.equal(makePairedData([record], 'china_aqi_estimate').length, 0)
  assert.equal(makePairedData([{ ...record, china_aqi_estimate: 0 }], 'china_aqi_estimate').length, 1)
  assert.equal(makePairedData([{ ...record, china_aqi_estimate: 75,
    environment_time_eligible: { ...record.environment_time_eligible, china_aqi_estimate: false } }], 'china_aqi_estimate').length, 0)
})

test('invalid and legacy current responses fail closed', async context => {
  for (const value of [-1, 501, 75.5, '75']) {
    context.mock.method(globalThis, 'fetch', async () => Response.json({ ...complete, china_aqi_estimate: value }))
    await assert.rejects(getCurrentEnvironment(new AbortController().signal), /unavailable/)
  }
  const legacy = { ...complete, us_aqi: 75 }; delete legacy.china_aqi_estimate
  context.mock.method(globalThis, 'fetch', async () => Response.json(legacy))
  await assert.rejects(getCurrentEnvironment(new AbortController().signal), /unavailable/)
})

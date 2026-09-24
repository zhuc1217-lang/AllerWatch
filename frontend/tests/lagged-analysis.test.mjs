import test from 'node:test'
import assert from 'node:assert/strict'
import { getLaggedAnalysis, isLaggedResponse } from '../src/api/analysis.ts'
import { lagCellBackground, lagExposures, lagHours } from '../src/laggedAnalysis.ts'

function fixture(mode = 'synthetic_only') {
  return {
    dataset_mode: mode, record_count: 12, real_count: mode === 'real_only' ? 12 : 0,
    synthetic_count: mode === 'real_only' ? 0 : 12, includes_synthetic: mode !== 'real_only',
    data_notice: 'Test data', date_start: '2026-09-01T00:00:00Z', date_end: '2026-09-02T00:00:00Z',
    observation_unit: 'individual_observation', outcome: 'tnss', minimum_pairs: 10,
    p_value_method: 'two_sided_asymptotic_unadjusted', lags_hours: [0, 6, 12, 24],
    matching: { approximate: true, tolerance_hours: 3, timezone: 'UTC',
      method: 'same_record_0h_backward_source_time_other_lags',
      exposure_time_fields: { pm2_5: 'air_quality_timestamp', us_aqi: 'air_quality_timestamp', relative_humidity: 'weather_timestamp' },
      nonzero_source_record_and_retrieval_before_target: true, cross_provenance_matching: false, zero_lag_note: 'Own snapshot' },
    results: lagExposures.flatMap(variable => lagHours.map(lag_hours => ({
      variable, lag_hours, n: 10, missing_pairs: 2, spearman_rho: 0.2, p_value: 0.3, status: 'ok',
      real_pairs: mode === 'real_only' ? 10 : 0, synthetic_pairs: mode === 'real_only' ? 0 : 10,
      distinct_source_records: 8, actual_lag_hours_min: lag_hours,
      actual_lag_hours_median: lag_hours + 1, actual_lag_hours_max: lag_hours + 3,
    }))),
  }
}

for (const mode of ['real_only', 'synthetic_only', 'all']) {
  test(`validates all 12 cells and provenance in ${mode}`, () => {
    assert.equal(isLaggedResponse(fixture(mode), mode), true)
    assert.equal(isLaggedResponse(fixture(mode), 'wrong'), false)
  })
}

test('missing cells and genuine zero coefficients have different neutral fills', () => {
  assert.notEqual(lagCellBackground(null), lagCellBackground(0))
  assert.equal(lagCellBackground(NaN), lagCellBackground(null))
  assert.equal(lagCellBackground(Infinity), lagCellBackground(null))
  assert.notEqual(lagCellBackground(-1), lagCellBackground(1))
  assert.equal(lagCellBackground(0), 'rgb(255, 255, 255)')
})

test('rejects future or out-of-tolerance offsets, naive dates and unsupported matching rules', () => {
  for (const update of [
    data => { data.results[0].actual_lag_hours_min = -1 },
    data => { data.results[1].actual_lag_hours_max = 10 },
    data => { data.date_start = '2026-09-01T00:00:00' },
    data => { data.matching.tolerance_hours = 12 },
    data => { data.matching.approximate = false },
    data => { data.matching.cross_provenance_matching = true },
  ]) {
    const data = fixture(); update(data)
    assert.equal(isLaggedResponse(data, 'synthetic_only'), false)
  }
})

test('rejects missing/duplicate combinations, extra windows and invalid pair counts', () => {
  for (const update of [
    data => { data.results.pop() },
    data => { data.results[1] = data.results[0] },
    data => { data.lags_hours.push(48) },
    data => { data.results[0].missing_pairs = 0 },
    data => { data.results[0].real_pairs = 10; data.results[0].synthetic_pairs = 0 },
    data => { data.results[0].distinct_source_records = 11 },
  ]) {
    const data = fixture(); update(data)
    assert.equal(isLaggedResponse(data, 'synthetic_only'), false)
  }
})

test('unavailable and constant cells retain counts but must have null estimates', () => {
  const data = fixture()
  Object.assign(data.results[0], { status: 'insufficient_data', n: 0, missing_pairs: 12, synthetic_pairs: 0,
    distinct_source_records: 0, spearman_rho: null, p_value: null, actual_lag_hours_min: null,
    actual_lag_hours_median: null, actual_lag_hours_max: null })
  Object.assign(data.results[1], { status: 'insufficient_variation', spearman_rho: null, p_value: null })
  assert.equal(isLaggedResponse(data, 'synthetic_only'), true)
  data.results[0].spearman_rho = 0
  assert.equal(isLaggedResponse(data, 'synthetic_only'), false)
})

test('rejects nonfinite results instead of displaying NaN or Infinity', () => {
  for (const key of ['spearman_rho', 'p_value', 'actual_lag_hours_median']) {
    const data = fixture(); data.results[0][key] = Infinity
    assert.equal(isLaggedResponse(data, 'synthetic_only'), false)
  }
})

test('fetches read-only lag endpoint with selected mode and cancellation signal', async context => {
  const signal = new AbortController().signal
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/analysis/lagged-associations?dataset=synthetic_only')
    assert.equal(options.signal, signal); assert.equal(options.cache, 'no-store')
    assert.equal(options.method, undefined)
    return Response.json(fixture())
  })
  assert.deepEqual(await getLaggedAnalysis('synthetic_only', signal), fixture())
})

test('API failure gives a readable message', async context => {
  context.mock.method(globalThis, 'fetch', async () => new Response('', { status: 503 }))
  await assert.rejects(getLaggedAnalysis('real_only', new AbortController().signal), /Could not load lagged/)
})

test('malformed response is rejected', async context => {
  context.mock.method(globalThis, 'fetch', async () => Response.json({ results: [] }))
  await assert.rejects(getLaggedAnalysis('real_only', new AbortController().signal), /unexpected lagged-analysis/)
})

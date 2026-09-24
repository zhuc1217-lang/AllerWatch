import test from 'node:test'
import assert from 'node:assert/strict'
import { coefficientChartData, exposureKeys, formatPValue, formatStatistic, variableKeys } from '../src/analysis.ts'
import { getAnalysis, isAssociationsResponse, isDescriptiveResponse } from '../src/api/analysis.ts'

function responses(mode = 'synthetic_only') {
  const meta = { dataset_mode: mode, record_count: 12, real_count: mode === 'real_only' ? 12 : 0,
    synthetic_count: mode === 'real_only' ? 0 : 12, includes_synthetic: mode !== 'real_only',
    data_notice: 'Test fixture', date_start: '2026-09-01T08:00:00Z', date_end: '2026-09-02T08:00:00Z',
    observation_unit: 'individual_observation' }
  return {
    descriptive: { ...meta, standard_deviation: 'sample_ddof_1', percentile_method: 'linear',
      variables: Object.fromEntries(variableKeys.map(key => [key, { n: 12, missing: 0, mean: 3, median: 3,
        std: 1, min: 0, q1: 2, q3: 4, max: 6 }])) },
    associations: { ...meta, outcome: 'tnss', minimum_pairs: 10, temporal_tolerance_hours: 3, p_value_method: 'two_sided_asymptotic_unadjusted',
      associations: exposureKeys.map(variable => ({ variable, n: 12, missing_pairs: 0, temporally_excluded_pairs: 0, spearman_rho: 0.3, p_value: 0.12, status: 'ok' })) },
  }
}

test('missing and non-finite estimates display Unavailable; true zero stays zero', () => {
  for (const value of [null, undefined, NaN, Infinity, -Infinity]) {
    assert.equal(formatStatistic(value), 'Unavailable')
    assert.equal(formatPValue(value), 'Unavailable')
  }
  assert.equal(formatStatistic(0), '0.00')
  assert.equal(formatStatistic(-0.0001, 3), '-1.00e-4')
  assert.equal(formatPValue(0.00012435), '1.24e-4')
  assert.equal(formatPValue(0), '< 0.0001')
  assert.equal(formatPValue(0.0768), '0.077')
})

test('chart preserves signed and zero coefficients, omits unavailable estimates, and does not mutate', () => {
  const rows = responses().associations.associations
  rows[0].spearman_rho = -0.4
  rows[1].spearman_rho = 0
  rows[2] = { ...rows[2], status: 'insufficient_data', spearman_rho: null, p_value: null }
  rows[3] = { ...rows[3], status: 'insufficient_variation', spearman_rho: null, p_value: null }
  rows[4].spearman_rho = NaN
  const original = structuredClone(rows)
  assert.deepEqual(coefficientChartData(rows).map(r => r.rho), [-0.4, 0])
  assert.deepEqual(rows, original)
})

for (const mode of ['real_only', 'synthetic_only', 'all']) {
  test(`accepts correctly labelled ${mode} responses and rejects wrong dataset`, () => {
    const { descriptive, associations } = responses(mode)
    assert.equal(isDescriptiveResponse(descriptive, mode), true)
    assert.equal(isAssociationsResponse(associations, mode), true)
    assert.equal(isDescriptiveResponse(descriptive, 'invalid'), false)
    assert.equal(isAssociationsResponse(associations, 'invalid'), false)
  })
}

test('rejects silently mixed provenance and incorrect counts', () => {
  const { descriptive, associations } = responses('real_only')
  descriptive.synthetic_count = 1
  associations.real_count = 0
  assert.equal(isDescriptiveResponse(descriptive, 'real_only'), false)
  assert.equal(isAssociationsResponse(associations, 'real_only'), false)
})

test('rejects non-finite statistics, coefficients, invalid p-values and unzoned dates', () => {
  for (const value of [NaN, Infinity, -Infinity]) {
    const { descriptive, associations } = responses()
    descriptive.variables.pm2_5.mean = value
    associations.associations[0].spearman_rho = value
    assert.equal(isDescriptiveResponse(descriptive, 'synthetic_only'), false)
    assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
  }
  const { descriptive, associations } = responses()
  associations.associations[0].p_value = 1.1
  descriptive.date_start = '2026-09-01T08:00:00'
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
  assert.equal(isDescriptiveResponse(descriptive, 'synthetic_only'), false)
})

test('accepts missing summaries and insufficient-data/variation statuses without fabricated zeros', () => {
  const { descriptive, associations } = responses()
  descriptive.variables.pm2_5 = { n: 0, missing: 12, mean: null, median: null, std: null, min: null, q1: null, q3: null, max: null }
  associations.associations[0] = { variable: 'pm2_5', n: 0, missing_pairs: 12, temporally_excluded_pairs: 0, status: 'insufficient_data', spearman_rho: null, p_value: null }
  associations.associations[1] = { variable: 'pm10', n: 12, missing_pairs: 0, temporally_excluded_pairs: 0, status: 'insufficient_variation', spearman_rho: null, p_value: null }
  assert.equal(isDescriptiveResponse(descriptive, 'synthetic_only'), true)
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), true)
  assert.equal(coefficientChartData(associations.associations).length, 3)
})

test('rejects duplicated exposures and insufficient-pair successful estimates', () => {
  const { associations } = responses()
  associations.associations[0].n = 9
  associations.associations[0].missing_pairs = 3
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
  associations.associations[0] = associations.associations[1]
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
})

test('API client requests both endpoints with selected mode, signal, and no cache', async context => {
  const data = responses('synthetic_only'), calls = []
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push([url, options])
    return Response.json(url.includes('descriptive') ? data.descriptive : data.associations)
  })
  const signal = new AbortController().signal
  assert.deepEqual(await getAnalysis('synthetic_only', signal), data)
  assert.equal(calls.length, 2)
  assert.ok(calls.every(([url, options]) => url.endsWith('?dataset=synthetic_only') && options.signal === signal && options.cache === 'no-store'))
})

test('API client rejects inconsistent snapshots instead of combining them', async context => {
  const data = responses('all')
  data.associations.date_end = '2026-09-03T08:00:00Z'
  context.mock.method(globalThis, 'fetch', async url => Response.json(url.includes('descriptive') ? data.descriptive : data.associations))
  await assert.rejects(getAnalysis('all', new AbortController().signal), /dataset changed/)
})

test('API failures produce a readable error', async context => {
  context.mock.method(globalThis, 'fetch', async () => new Response('', { status: 503 }))
  await assert.rejects(getAnalysis('real_only', new AbortController().signal), /Could not load analysis/)
})

test('temporal exclusions form a separate, exhaustive partition from missing numerical pairs', () => {
  const { associations } = responses()
  const row = associations.associations[0]
  Object.assign(row, { n: 0, missing_pairs: 2, temporally_excluded_pairs: 10,
    status: 'insufficient_data', spearman_rho: null, p_value: null })
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), true)
  row.temporally_excluded_pairs = 9
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
  row.temporally_excluded_pairs = undefined
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
})

test('old unrestricted association responses are rejected rather than silently displayed', () => {
  const { associations } = responses()
  delete associations.temporal_tolerance_hours
  assert.equal(isAssociationsResponse(associations, 'synthetic_only'), false)
})

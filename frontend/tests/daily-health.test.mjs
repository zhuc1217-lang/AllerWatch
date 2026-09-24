import test from 'node:test'
import assert from 'node:assert/strict'
import { blankDailyDraft, dailyDateError, dailyPayload, isCalendarDate, validateDailyDraft } from '../src/dailyHealth.ts'
import { DailyHealthError, getDailyRecord, isDailyRecord, saveDailyRecord } from '../src/api/dailyHealth.ts'
import { isDailyAssociationsResponse } from '../src/api/analysis.ts'
import { dailyLabels } from '../src/types/dailyHealth.ts'

const record = { id: 1, date: '2026-09-21', sleep_duration_hours: 6.5, sleep_quality: 4, stress_level: 3,
  exercise_minutes: 0, notes: null, is_synthetic: false, created_at: '2026-09-21T08:00:00Z' }
const draft = { sleep: '6.5', quality: 4, stress: 3, exercise: '0', notes: '  ' }

test('real date guard uses server study-calendar today, including both sides of midnight', () => {
  assert.equal(dailyDateError('2026-09-22', '2026-09-22'), null)
  assert.match(dailyDateError('2026-09-23', '2026-09-22'), /today or an earlier/)
  assert.equal(dailyDateError('2026-09-23', '2026-09-23'), null)
  assert.equal(dailyDateError('2026-09-22', '2026-09-23'), null)
  assert.match(dailyDateError('2026-09-24', '2026-09-23'), /UTC\+08:00/)
  assert.match(dailyDateError('2026-09-23T00:00:00+08:00', '2026-09-23'), /valid calendar/)
  assert.match(dailyDateError('2026-09-23', undefined), /Load the study calendar/)
})

test('unknown legacy edit time remains accepted but malformed provenance is rejected', () => {
  assert.equal(isDailyRecord({ ...record, updated_at: null }), true)
  assert.equal(isDailyRecord({ ...record, updated_at: '2026-09-23T00:00:00Z' }), true)
  assert.equal(isDailyRecord({ ...record, updated_at: '2026-09-23T00:00:00' }), false)
  assert.equal(isDailyRecord({ ...record, updated_at: 'unknown' }), false)
})

test('calendar dates remain literal dates; invalid dates and timestamps are rejected', () => {
  for (const date of ['2026-09-21', '2024-02-29', '2000-02-29']) assert.equal(isCalendarDate(date), true)
  for (const date of ['2026-02-29', '1900-02-29', '2026-04-31', '2026-00-01', '0000-01-01', '2026-09-21T00:00:00Z', '', null]) {
    assert.equal(isCalendarDate(date), false)
  }
})

test('empty fields do not become zero; decimal sleep and true zero exercise are valid', () => {
  assert.equal(Object.keys(validateDailyDraft(blankDailyDraft())).length, 4)
  assert.throws(() => dailyPayload(blankDailyDraft()))
  assert.deepEqual(dailyPayload(draft), { sleep_duration_hours: 6.5, sleep_quality: 4, stress_level: 3, exercise_minutes: 0, notes: null })
  for (const invalid of [{ sleep: 'NaN' }, { sleep: '24.1' }, { quality: 0 }, { stress: 5.5 }, { exercise: '1.5' }, { exercise: '1441' }]) {
    assert.ok(Object.keys(validateDailyDraft({ ...draft, ...invalid })).length)
  }
})

test('record validation rejects non-finite numbers, invalid scores and missing provenance', () => {
  assert.equal(isDailyRecord(record), true)
  for (const invalid of [{ sleep_duration_hours: Infinity }, { exercise_minutes: null }, { sleep_quality: 0 },
    { is_synthetic: undefined }, { created_at: '2026-09-21T08:00:00' }, { date: '2026-02-30' }]) {
    assert.equal(isDailyRecord({ ...record, ...invalid }), false)
  }
})

test('real diary creates with false provenance then updates by literal date without relabelling', async context => {
  const calls = []
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, ...options, body: JSON.parse(options.body) })
    return Response.json(record, { status: options.method === 'POST' ? 201 : 200 })
  })
  const signal = new AbortController().signal, values = dailyPayload(draft)
  await saveDailyRecord(record.date, values, false, signal)
  await saveDailyRecord(record.date, values, true, signal)
  assert.equal(calls[0].url, '/api/daily-health')
  assert.equal(calls[0].method, 'POST')
  assert.deepEqual(calls[0].body, { ...values, date: record.date, is_synthetic: false })
  assert.equal(calls[1].url, '/api/daily-health/2026-09-21')
  assert.equal(calls[1].method, 'PUT')
  assert.deepEqual(calls[1].body, values)
  assert.equal(calls[1].signal, signal)
})

test('duplicate and validation responses fail clearly without changing submitted values', async context => {
  const values = dailyPayload(draft), original = structuredClone(values)
  context.mock.method(globalThis, 'fetch', async () => Response.json({ detail: 'duplicate' }, { status: 409 }))
  await assert.rejects(saveDailyRecord(record.date, values, false, new AbortController().signal), error =>
    error instanceof DailyHealthError && error.status === 409 && error.message.includes('entries have been kept'))
  context.mock.method(globalThis, 'fetch', async () => Response.json({ detail: [{ loc: ['body', 'stress_level'], msg: 'Must be at most 5' }] }, { status: 422 }))
  await assert.rejects(saveDailyRecord(record.date, values, false, new AbortController().signal), error => error.fields.stress_level === 'Must be at most 5')
  assert.deepEqual(values, original)
})

test('loading an absent date is distinct from failure or a synthetic record', async context => {
  const signal = new AbortController().signal
  context.mock.method(globalThis, 'fetch', async () => Response.json({}, { status: 404 }))
  assert.equal(await getDailyRecord(record.date, signal), null)
  context.mock.method(globalThis, 'fetch', async () => Response.json({ ...record, is_synthetic: true }))
  await assert.rejects(getDailyRecord(record.date, signal), /Unexpected/)
  context.mock.method(globalThis, 'fetch', async () => Response.json({}, { status: 503 }))
  await assert.rejects(getDailyRecord(record.date, signal), /Retry before editing/)
})

function response(mode = 'synthetic_only') {
  const real = mode === 'real_only'
  return { dataset_mode: mode, record_count: 12, real_count: real ? 12 : 0, synthetic_count: real ? 0 : 12,
    includes_synthetic: !real, data_notice: 'Fixture', date_start: '2026-09-01T08:00:00Z', date_end: '2026-09-12T08:00:00Z',
    observation_unit: 'individual_observation', outcome: 'tnss', minimum_pairs: 10, p_value_method: 'two_sided_asymptotic_unadjusted',
    calendar_timezone: 'UTC+08:00', join_method: 'study_date_and_same_provenance', daily_record_count: 12,
    real_daily_count: real ? 12 : 0, synthetic_daily_count: real ? 0 : 12, matched_symptom_count: 12,
    missing_daily_symptom_count: 0, matched_daily_records: 12, daily_records_without_symptoms: 0,
    associations: Object.keys(dailyLabels).map(variable => ({ variable, n: 12, missing_pairs: 0, spearman_rho: -.2, p_value: .2,
      status: 'ok', real_pairs: real ? 12 : 0, synthetic_pairs: real ? 0 : 12, distinct_daily_records: 12 })) }
}

for (const mode of ['real_only', 'synthetic_only', 'all']) test(`daily results validate ${mode} and reject incompatible provenance`, () => {
  const body = response(mode)
  assert.equal(isDailyAssociationsResponse(body, mode), true)
  body.associations[0].real_pairs = 6; body.associations[0].synthetic_pairs = 6
  assert.equal(isDailyAssociationsResponse(body, mode), false)
})

test('missing daily pairs stay null, true zero stays valid, NaN cannot reach the UI', () => {
  const body = response()
  Object.assign(body, { matched_symptom_count: 0, missing_daily_symptom_count: 12, matched_daily_records: 0, daily_records_without_symptoms: 12 })
  body.associations.forEach(item => Object.assign(item, { n: 0, missing_pairs: 12, spearman_rho: null, p_value: null,
    status: 'insufficient_data', synthetic_pairs: 0, distinct_daily_records: 0 }))
  assert.equal(isDailyAssociationsResponse(body, 'synthetic_only'), true)
  const complete = response()
  complete.associations[0].spearman_rho = 0
  assert.equal(isDailyAssociationsResponse(complete, 'synthetic_only'), true)
  complete.associations[0].spearman_rho = NaN
  assert.equal(isDailyAssociationsResponse(complete, 'synthetic_only'), false)
})

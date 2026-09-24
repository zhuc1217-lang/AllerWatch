import test from 'node:test'
import assert from 'node:assert/strict'
import { apiUrl } from '../src/api/base.ts'
import { getDailyRecord, saveDailyRecord } from '../src/api/dailyHealth.ts'

test('API URL retains localhost Vite proxy fallback and supports a configured backend', () => {
  assert.equal(apiUrl('/health'), '/api/health')
  assert.equal(apiUrl('/health', ''), '/api/health')
  assert.equal(apiUrl('/symptoms', 'https://backend.example/'), 'https://backend.example/symptoms')
  assert.equal(apiUrl('/analysis/associations?dataset=synthetic_only', 'https://backend.example'), 'https://backend.example/analysis/associations?dataset=synthetic_only')
  assert.equal(apiUrl('/health', 'http://127.0.0.1:8000'), 'http://127.0.0.1:8000/health')
})

test('API URL rejects credentials and malformed configuration', () => {
  for (const base of ['file:///secret', 'https://u:p@example.com', 'https://example.com?key=123', 'https://example.com#fragment']) {
    assert.throws(() => apiUrl('/health', base))
  }
  assert.throws(() => apiUrl('//example.com'))
})

test('public daily form reads and updates only synthetic responses', async context => {
  const values = { sleep_duration_hours: 7, sleep_quality: 4, stress_level: 2, exercise_minutes: 0, notes: null }
  const record = { ...values, id: 1, date: '2025-01-01', is_synthetic: true, created_at: '2025-01-01T00:00:00Z' }
  const calls = [], signal = new AbortController().signal
  context.mock.method(globalThis, 'fetch', async (url, options) => {
    calls.push({ url, ...options })
    return Response.json(record)
  })
  assert.equal((await getDailyRecord(record.date, signal, true)).is_synthetic, true)
  await saveDailyRecord(record.date, values, false, signal, true)
  await saveDailyRecord(record.date, values, true, signal, true)
  assert.equal(calls[0].url, '/api/daily-health/2025-01-01?is_synthetic=true')
  assert.equal(JSON.parse(calls[1].body).is_synthetic, true)
  assert.equal(calls[2].url, '/api/daily-health/2025-01-01?is_synthetic=true')
  context.mock.method(globalThis, 'fetch', async () => Response.json({ ...record, is_synthetic: false }))
  await assert.rejects(getDailyRecord(record.date, signal, true), /Unexpected/)
  await assert.rejects(saveDailyRecord(record.date, values, true, signal, true), /could not be confirmed/)
})

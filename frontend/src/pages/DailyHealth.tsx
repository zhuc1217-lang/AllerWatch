import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import ChoiceField from '../components/ChoiceField'
import { usePublicDemo } from '../components/AppConfig'
import { DailyHealthError, getDailyList, getDailyRecord, saveDailyRecord } from '../api/dailyHealth'
import { blankDailyDraft, dailyDateError, dailyPayload, isCalendarDate, validateDailyDraft } from '../dailyHealth'
import type { DailyDraft } from '../dailyHealth'
import { qualityOptions, stressOptions } from '../types/dailyHealth'
import type { DailyList, DailyRecord } from '../types/dailyHealth'
import './LogSymptoms.css'
import './DailyHealth.css'

export default function DailyHealth() {
  const publicDemo = usePublicDemo()
  const [list, setList] = useState<DailyList | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [listAttempt, setListAttempt] = useState(0)
  const [date, setDate] = useState('')
  const [loadAttempt, setLoadAttempt] = useState(0)
  const [loadStatus, setLoadStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [loadError, setLoadError] = useState<string | null>(null)
  const [existing, setExisting] = useState<DailyRecord | null>(null)
  const [draft, setDraft] = useState<DailyDraft>(blankDailyDraft)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saveError, setSaveError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [saving, setSaving] = useState(false)
  const busy = useRef(false)
  const form = useRef<HTMLFormElement>(null)
  const saveAbort = useRef<AbortController | null>(null)
  useEffect(() => () => saveAbort.current?.abort(), [])

  useEffect(() => {
    const controller = new AbortController(); let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setListError(null)
    void getDailyList(controller.signal).then(data => {
      if (!cancelled) { setList(data); setDate(current => current || data.today) }
    }).catch(() => { if (!cancelled) setListError('Could not load daily health records. Check that the backend is running, then retry.') })
      .finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [listAttempt])

  useEffect(() => {
    if (!isCalendarDate(date) || publicDemo === null) return
    const controller = new AbortController(); let cancelled = false
    const timeout = window.setTimeout(() => controller.abort(), 10000)
    setLoadStatus('loading'); setLoadError(null); setSuccess(false); setSaveError(null); setErrors({})
    void getDailyRecord(date, controller.signal, publicDemo).then(record => {
      if (cancelled) return
      setExisting(record)
      if (record) setList(current => current ? { ...current, records: [record, ...current.records.filter(item => item.id !== record.id)]
        .sort((a, b) => b.date.localeCompare(a.date) || Number(a.is_synthetic) - Number(b.is_synthetic)) } : current)
      setDraft(record ? { sleep: String(record.sleep_duration_hours), quality: record.sleep_quality,
        stress: record.stress_level, exercise: String(record.exercise_minutes), notes: record.notes ?? '' } : blankDailyDraft())
      setLoadStatus('ready')
    }).catch(error => {
      if (!cancelled) { setLoadStatus('error'); setLoadError(error instanceof Error ? error.message : 'Could not load this date.') }
    }).finally(() => window.clearTimeout(timeout))
    return () => { cancelled = true; controller.abort(); window.clearTimeout(timeout) }
  }, [date, loadAttempt, publicDemo])

  function change<K extends keyof DailyDraft>(key: K, value: DailyDraft[K]) {
    setDraft(current => ({ ...current, [key]: value })); setSuccess(false); setSaveError(null)
  }
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy.current || loadStatus !== 'ready' || !isCalendarDate(date) || publicDemo === null) return
    const invalid = validateDailyDraft(draft)
    const invalidDate = dailyDateError(date, list?.today)
    if (invalidDate) invalid.date = invalidDate
    setErrors(invalid); setSaveError(null); setSuccess(false)
    if (Object.keys(invalid).length) {
      setSaveError('Please correct the highlighted fields.')
      form.current?.querySelector<HTMLInputElement>(`[name="${Object.keys(invalid)[0]}"]`)?.focus()
      return
    }
    busy.current = true; setSaving(true)
    const controller = new AbortController(); saveAbort.current = controller
    const timeout = window.setTimeout(() => controller.abort(), 15000)
    try {
      const saved = await saveDailyRecord(date, dailyPayload(draft), existing !== null, controller.signal, publicDemo)
      setExisting(saved); setSuccess(true)
      setList(current => current ? { ...current, records: [saved, ...current.records.filter(item => item.id !== saved.id)]
        .sort((a, b) => b.date.localeCompare(a.date) || Number(a.is_synthetic) - Number(b.is_synthetic)) } : current)
    } catch (error) {
      setSaveError(error instanceof DailyHealthError ? error.message : 'Saving could not be confirmed. Your entries have been kept. Load the saved record to check before retrying.')
      if (error instanceof DailyHealthError) setErrors(error.fields)
    } finally { busy.current = false; setSaving(false); window.clearTimeout(timeout); saveAbort.current = null }
  }
  const dateError = dailyDateError(date, list?.today)
  const disabled = saving || loadStatus !== 'ready' || dateError !== null || publicDemo === null
  return <main className="log-page daily-page">
    <header className="log-heading"><h1>Daily Health</h1><p>{publicDemo ? 'Try a fictional daily summary of sleep, stress and activity. It will be stored as synthetic demonstration data.' : 'Record one real daily summary of sleep, stress and activity.'}</p></header>
    {listError && <div className="daily-alert" role="alert"><p>{listError}</p><button onClick={() => setListAttempt(n => n + 1)}>Retry daily history</button></div>}
    {!list && !listError && <p role="status">Loading daily health…</p>}
    {list && <>
      <p className="daily-note">Study calendar: <strong>{list.calendar_timezone}</strong>. Dates are stored exactly as selected. This fixed study calendar is independent of your browser timezone.</p>
      <div className="daily-date"><label htmlFor="daily-date">Date</label>
        <input id="daily-date" name="date" type="date" max={list.today} value={date} disabled={saving}
          aria-invalid={Boolean(dateError || errors.date)} aria-describedby="daily-date-error"
          onChange={event => { setLoadStatus('loading'); setDate(event.target.value) }} />
      </div>
      <p id="daily-date-error" className="field-error">{dateError || errors.date}</p>
      <p className="daily-note">Future dates are not accepted. Today is {list.today} in the server study calendar; reload this page after study-calendar midnight.</p>
      {loadStatus === 'loading' && isCalendarDate(date) && <p role="status">Loading the selected date…</p>}
      {loadStatus === 'error' && <div className="daily-alert" role="alert"><p>{loadError}</p><button onClick={() => setLoadAttempt(n => n + 1)}>Retry selected date</button></div>}
      {loadStatus === 'ready' && <p className="daily-note">{publicDemo
        ? existing ? 'Existing synthetic demo record loaded. Saving updates this shared demonstration record.' : 'No demo record exists for this date. Saving creates a synthetic record.'
        : existing ? 'Existing real record loaded. Saving will update this record.' : 'No real record exists for this date. Saving will create one.'}</p>}
      {success && <p className="daily-success" role="status">Daily health record saved successfully.</p>}
      <form ref={form} className="symptom-form" onSubmit={submit} noValidate>
        <p className="form-instruction">Sleep refers to the main sleep ending on this date. Stress and exercise summarize this calendar day; today may still be incomplete.</p>
        <fieldset className="daily-fields" disabled={disabled}>
          <legend className="daily-visually-hidden">Daily health values</legend>
          <div className="daily-number"><label htmlFor="sleep-duration">Sleep duration <span>(hours)</span></label>
            <input id="sleep-duration" name="sleep_duration_hours" type="number" min="0" max="24" step="any" inputMode="decimal" value={draft.sleep}
              onChange={event => change('sleep', event.target.value)} aria-invalid={Boolean(errors.sleep_duration_hours)} aria-describedby="sleep-duration-error" required />
            <p id="sleep-duration-error" className="field-error">{errors.sleep_duration_hours}</p>
          </div>
          <ChoiceField name="sleep_quality" label="Sleep quality" value={draft.quality} options={qualityOptions}
            onChange={value => change('quality', value)} error={errors.sleep_quality} disabled={disabled} />
          <ChoiceField name="stress_level" label="Stress level" value={draft.stress} options={stressOptions}
            onChange={value => change('stress', value)} error={errors.stress_level} disabled={disabled} />
          <div className="daily-number"><label htmlFor="exercise-minutes">Exercise <span>(minutes)</span></label>
            <input id="exercise-minutes" name="exercise_minutes" type="number" min="0" max="1440" step="1" inputMode="numeric" value={draft.exercise}
              onChange={event => change('exercise', event.target.value)} aria-invalid={Boolean(errors.exercise_minutes)} aria-describedby="exercise-error" required />
            <p id="exercise-error" className="field-error">{errors.exercise_minutes}</p>
          </div>
          <div className="notes-field"><label htmlFor="daily-notes">Notes <span>(optional)</span></label>
            <textarea id="daily-notes" name="notes" value={draft.notes} onChange={event => change('notes', event.target.value)} />
          </div>
        </fieldset>
        {saveError && <div className="daily-alert" role="alert"><p>{saveError}</p>
          <button type="button" disabled={saving} onClick={() => setLoadAttempt(n => n + 1)}>Load saved record (replaces form entries)</button>
        </div>}
        <button className="primary-button daily-save" type="submit" disabled={disabled}>{saving ? 'Saving…' : existing ? 'Update daily health' : 'Save daily health'}</button>
      </form>
      <section className="daily-history" aria-labelledby="daily-history-title"><h2 id="daily-history-title">Recent Daily Health</h2>
        <p className="daily-note">{publicDemo ? 'Latest 14 shared synthetic summaries, newest first. Use fictional values only.' : 'Latest 14 summaries, newest first. Synthetic development records are read-only and separate from your real diary.'}</p>
        {list.records.length === 0 ? <p>No daily health records yet.</p> : <div className="daily-table-scroll" role="region" aria-label="Recent daily health records, scroll horizontally" tabIndex={0}>
          <table><thead><tr>{['Date', 'Type', 'Sleep (h)', 'Quality / 5', 'Stress / 5', 'Exercise (min)', 'Action'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead>
            <tbody>{list.records.slice(0, 14).map(record => <tr key={record.id}>
              <th scope="row">{record.date}</th><td>{record.is_synthetic ? 'Synthetic demo' : 'Real'}</td><td>{record.sleep_duration_hours}</td>
              <td>{record.sleep_quality}</td><td>{record.stress_level}</td><td>{record.exercise_minutes}</td>
              <td>{record.is_synthetic && !publicDemo ? 'Read-only' : <button type="button" disabled={saving || publicDemo === null} onClick={() => { setDate(record.date); setLoadAttempt(n => n + 1) }}>Edit {record.date}</button>}</td>
            </tr>)}</tbody></table>
        </div>}
      </section>
    </>}
    <p className="daily-note">These variables are self-reported. Manually entered sleep duration is not clinically measured sleep, and stress is subjective. Same-day associations may be confounded and do not establish temporal direction or causality.</p>
  </main>
}

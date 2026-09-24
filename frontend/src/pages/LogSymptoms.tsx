import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { saveSymptomRecord, SymptomSubmissionError } from '../api/symptoms'
import ChoiceField from '../components/ChoiceField'
import { usePublicDemo } from '../components/AppConfig'
import { fieldLabels, symptomLabels } from '../types/symptoms'
import type { FieldErrors, FormField, SavedSymptomRecord, SymptomField, SymptomRecordInput } from '../types/symptoms'
import './LogSymptoms.css'

const symptomFields = Object.keys(symptomLabels) as SymptomField[]
const symptomOptions = ['None', 'Mild', 'Moderate', 'Severe']
  .map((label, value) => ({ value, label, score: String(value) }))
const overallOptions = Array.from({ length: 11 }, (_, value) => ({ value, label: String(value) }))
const medicationOptions = [{ value: 1, label: 'Yes' }, { value: 0, label: 'No' }]

function blankScores(): Record<SymptomField, number | null> {
  return { nasal_congestion: null, sneezing: null, runny_nose: null, nasal_itching: null, eye_symptoms: null }
}

function validScore(value: number | null, maximum: number): boolean {
  return value !== null && Number.isInteger(value) && value >= 0 && value <= maximum
}

export default function LogSymptoms() {
  const publicDemo = usePublicDemo()
  const [scores, setScores] = useState(blankScores)
  const [overall, setOverall] = useState<number | null>(null)
  const [medication, setMedication] = useState<boolean | null>(null)
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<SavedSymptomRecord | null>(null)
  const requestInProgress = useRef(false)
  const formRef = useRef<HTMLFormElement>(null)
  const errorRef = useRef<HTMLDivElement>(null)
  const headingRef = useRef<HTMLHeadingElement>(null)
  const successRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (saved) successRef.current?.focus()
  }, [saved])

  function clearFieldError(field: FormField) {
    setErrors((current) => {
      const next = { ...current }
      delete next[field]
      return next
    })
    setSubmitError(null)
  }

  function focusFirstError(fieldErrors: FieldErrors) {
    const field = Object.keys(fieldErrors)[0]
    window.requestAnimationFrame(() => {
      if (field) {
        formRef.current?.querySelector<HTMLInputElement | HTMLTextAreaElement>(`[name="${field}"]`)?.focus()
      } else {
        errorRef.current?.focus()
      }
    })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (requestInProgress.current || publicDemo === null) return

    const nextErrors: FieldErrors = {}
    for (const field of symptomFields) {
      if (!validScore(scores[field], 3)) nextErrors[field] = `Choose a score from 0 to 3 for ${symptomLabels[field].toLowerCase()}.`
    }
    if (!validScore(overall, 10)) nextErrors.overall_severity = 'Choose an overall severity from 0 to 10.'
    if (medication === null) nextErrors.medication_taken = 'Choose Yes or No for medication taken.'
    setErrors(nextErrors)
    setSubmitError(null)
    if (Object.keys(nextErrors).length > 0) {
      setSubmitError('Please complete the highlighted fields before saving.')
      focusFirstError(nextErrors)
      return
    }

    // Required values have been checked above. No ID, timestamp, or TNSS is sent.
    const payload: SymptomRecordInput = {
      nasal_congestion: scores.nasal_congestion!,
      sneezing: scores.sneezing!,
      runny_nose: scores.runny_nose!,
      nasal_itching: scores.nasal_itching!,
      eye_symptoms: scores.eye_symptoms!,
      overall_severity: overall!,
      medication_taken: medication!,
      notes: notes.trim() || null,
      is_synthetic: publicDemo,
    }

    requestInProgress.current = true
    setSaving(true)
    try {
      setSaved(await saveSymptomRecord(payload))
    } catch (error) {
      const failure = error instanceof SymptomSubmissionError
        ? error
        : new SymptomSubmissionError('Saving could not be confirmed. Your entries have been kept. Please try again.')
      setSubmitError(failure.message)
      setErrors(failure.fieldErrors)
      focusFirstError(failure.fieldErrors)
    } finally {
      requestInProgress.current = false
      setSaving(false)
    }
  }

  function startAnotherRecord() {
    setScores(blankScores())
    setOverall(null)
    setMedication(null)
    setNotes('')
    setErrors({})
    setSubmitError(null)
    setSaved(null)
    window.requestAnimationFrame(() => headingRef.current?.focus())
  }

  return (
    <main className="log-page">

      <header className="log-heading">
        <h1 ref={headingRef} tabIndex={-1}>Log Symptoms</h1>
        <p>{publicDemo ? 'Try a fictional symptom observation. It will be stored as synthetic demonstration data.' : 'Record your symptoms as they are now.'} This form uses the server's current observation time and does not submit a device timestamp or allow future scheduling.</p>
      </header>

      {saved ? (
        <section className="save-confirmation" aria-labelledby="save-title">
          <p className="confirmation-label">Observation saved</p>
          <h2 id="save-title" ref={successRef} tabIndex={-1}>Symptom record saved successfully.</h2>
          <p className="saved-tnss">TNSS: {saved.tnss} / 12</p>
          <p className="confirmation-note">TNSS covers the four nasal symptoms. Eye symptoms are recorded separately.</p>
          <button className="primary-button" type="button" onClick={startAnotherRecord}>
            Start another symptom record
          </button>
        </section>
      ) : (
        <form className="symptom-form" ref={formRef} onSubmit={handleSubmit} noValidate aria-busy={saving}>
          <p className="form-instruction">Choose one answer for each field. Only notes are optional.</p>

          {submitError && (
            <div className="form-error" role="alert" ref={errorRef} tabIndex={-1}>
              <p>{submitError}</p>
              {Object.keys(errors).length > 0 && (
                <ul>{Object.entries(errors).map(([field, message]) => (
                  <li key={field}>{fieldLabels[field as FormField]}: {message}</li>
                ))}</ul>
              )}
            </div>
          )}

          <section className="form-section" aria-labelledby="symptoms-title">
            <h2 id="symptoms-title">Symptoms</h2>
            <p className="section-description">0 = None · 1 = Mild · 2 = Moderate · 3 = Severe</p>
            {symptomFields.map((field) => (
              <ChoiceField
                key={field}
                name={field}
                label={symptomLabels[field]}
                value={scores[field]}
                options={symptomOptions}
                error={errors[field]}
                disabled={saving || publicDemo === null}
                onChange={(value) => {
                  setScores((current) => ({ ...current, [field]: value }))
                  clearFieldError(field)
                }}
              />
            ))}
          </section>

          <section className="form-section" aria-label="Overall severity and medication">
            <ChoiceField
              name="overall_severity"
              label="Overall severity"
              hint="0 = None · 10 = Most severe"
              value={overall}
              options={overallOptions}
              layout="scale"
              error={errors.overall_severity}
              disabled={saving || publicDemo === null}
              onChange={(value) => { setOverall(value); clearFieldError('overall_severity') }}
            />
            <ChoiceField
              name="medication_taken"
              label="Medication taken"
              value={medication === null ? null : Number(medication)}
              options={medicationOptions}
              layout="binary"
              error={errors.medication_taken}
              disabled={saving || publicDemo === null}
              onChange={(value) => { setMedication(value === 1); clearFieldError('medication_taken') }}
            />
            <div className="notes-field">
              <label htmlFor="notes">Notes <span>(optional)</span></label>
              <textarea
                id="notes" name="notes" rows={4} value={notes} disabled={saving || publicDemo === null}
                onChange={(event) => { setNotes(event.target.value); clearFieldError('notes') }}
                aria-invalid={Boolean(errors.notes)}
                aria-describedby={errors.notes ? 'notes-error' : undefined}
              />
              {errors.notes && <p className="field-error" id="notes-error">{errors.notes}</p>}
            </div>
          </section>

          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={saving || publicDemo === null}>
              {saving ? 'Saving…' : 'Save symptom record'}
            </button>
            <p>TNSS will be shown after your record is saved.</p>
          </div>
        </form>
      )}
    </main>
  )
}

type ChoiceOption = {
  value: number
  label: string
  score?: string
}

type ChoiceFieldProps = {
  name: string
  label: string
  value: number | null
  options: readonly ChoiceOption[]
  onChange: (value: number) => void
  error?: string
  hint?: string
  layout?: 'symptom' | 'scale' | 'binary'
  disabled?: boolean
}

export default function ChoiceField({
  name, label, value, options, onChange, error, hint, layout = 'symptom', disabled,
}: ChoiceFieldProps) {
  const description = [hint ? `${name}-hint` : '', error ? `${name}-error` : '']
    .filter(Boolean).join(' ') || undefined

  return (
    <fieldset className="choice-field" id={`${name}-field`} disabled={disabled}>
      <legend>{label}</legend>
      {hint && <p className="field-hint" id={`${name}-hint`}>{hint}</p>}
      <div className={`choice-grid choice-grid--${layout}`}>
        {options.map((option) => (
          <label className={`score-choice${value === option.value ? ' is-selected' : ''}`} key={option.value}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              required
              aria-label={option.score ? `${option.score} = ${option.label}` : option.label}
              aria-invalid={Boolean(error)}
              aria-describedby={description}
            />
            <span className="choice-text">
              {option.score && <span className="choice-score">{option.score}</span>}
              <span>{option.label}</span>
            </span>
          </label>
        ))}
      </div>
      {error && <p className="field-error" id={`${name}-error`}>{error}</p>}
    </fieldset>
  )
}

import { useEffect, useState } from 'react'
import { fetchMasterKind, type MasterListItem } from '../../api/client'
import type { FormModeField, FormModePayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './FormModeCard.module.css'

interface FormModeCardProps {
  payload: FormModePayload
  onCheckCr: (crNumber: string) => void
  onSkipCr: () => void
  onSaveField: (key: string, value: string) => Promise<boolean>
  onCallMe: () => void
}

function optionLabel(item: MasterListItem): string {
  if ('label' in item && item.label) return item.label
  if ('name' in item && item.name) return item.name
  return item.id
}

function FieldRow({
  field,
  onSave,
}: {
  field: FormModeField
  onSave: (key: string, value: string) => Promise<boolean>
}) {
  const [value, setValue] = useState('')
  const [options, setOptions] = useState<MasterListItem[]>([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputId = `form-mode-${field.key}`

  useEffect(() => {
    if (field.kind !== 'select' || !field.master_kind) return
    let cancelled = false
    void fetchMasterKind(field.master_kind).then((items) => {
      if (!cancelled) setOptions(items)
    })
    return () => {
      cancelled = true
    }
  }, [field.kind, field.master_kind])

  const save = async () => {
    if (!value.trim()) return
    setSaving(true)
    setError(null)
    const ok = await onSave(field.key, value.trim())
    setSaving(false)
    if (!ok) setError("That doesn't look right. Check it and try again.")
  }

  return (
    <div className={styles.fieldRow} data-testid={`form-mode-field-${field.key}`}>
      <label className={styles.fieldLabel} htmlFor={inputId}>
        {field.label}
      </label>
      <div className={styles.fieldControls}>
        {field.kind === 'select' ? (
          <select
            id={inputId}
            className={styles.input}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={saving}
          >
            <option value="">Select…</option>
            {options.map((item) => (
              <option key={item.id} value={item.id}>
                {optionLabel(item)}
              </option>
            ))}
          </select>
        ) : (
          <input
            id={inputId}
            className={styles.input}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void save()
            }}
            disabled={saving}
          />
        )}
        <button
          type="button"
          className={shared.secondaryBtn}
          onClick={() => void save()}
          disabled={saving || !value.trim()}
        >
          Save
        </button>
      </div>
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

/** Shown while the assistant is unavailable: finish the inquiry from the cards (L3 §3.14). */
export function FormModeCard({
  payload,
  onCheckCr,
  onSkipCr,
  onSaveField,
  onCallMe,
}: FormModeCardProps) {
  const [cr, setCr] = useState('')

  if (!payload.active) {
    return (
      <div className={`${shared.shellPad} ${styles.layout}`} data-testid="form-mode-card">
        <p className={styles.back}>{payload.message}</p>
      </div>
    )
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="form-mode-card">
      <h2 className={styles.title}>Finish your inquiry here</h2>
      <p className={styles.message}>{payload.message}</p>

      {payload.next_step === 'cr' ? (
        <div className={styles.fieldRow}>
          <label className={styles.fieldLabel} htmlFor="form-mode-cr">
            CR number
          </label>
          <div className={styles.fieldControls}>
            <input
              id="form-mode-cr"
              className={styles.input}
              inputMode="numeric"
              value={cr}
              onChange={(e) => setCr(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && cr.trim()) onCheckCr(cr.trim())
              }}
            />
            <button
              type="button"
              className={shared.primaryBtn}
              onClick={() => onCheckCr(cr.trim())}
              disabled={!cr.trim()}
            >
              Check CR
            </button>
          </div>
          {payload.can_skip_cr ? (
            <button type="button" className={shared.textLink} onClick={onSkipCr}>
              Skip for now
            </button>
          ) : null}
        </div>
      ) : null}

      {payload.fields.length > 0 ? (
        <div className={styles.fields}>
          {payload.fields.map((field) => (
            <FieldRow key={field.key} field={field} onSave={onSaveField} />
          ))}
        </div>
      ) : null}

      <div className={styles.footer}>
        <span className={styles.footerText}>Prefer to talk to someone?</span>
        <button type="button" className={shared.secondaryBtn} onClick={onCallMe}>
          Ask us to call you
        </button>
      </div>
    </div>
  )
}

import { useState } from 'react'
import type { DraftChecks, ReviewPayload } from '../../types/contracts'
import { SourceBadge } from '../draft/SourceBadge'
import { canSubmitWithConsent, submitBlockerHint } from './blockerHint'
import shared from './cards.module.css'
import styles from './ReviewCard.module.css'

interface ReviewCardProps {
  payload: ReviewPayload
  onEditField: (key: string, value: string) => void
  onSubmit: () => void
}

function checkRows(checks: DraftChecks, consent: boolean) {
  const unconfirmed = checks.unconfirmed
  const suggestedOk = unconfirmed === 0 && checks.required_filled >= checks.required_total
  return [
    {
      ok: suggestedOk,
      label:
        unconfirmed > 0
          ? `${unconfirmed} suggested value${unconfirmed === 1 ? '' : 's'} to confirm`
          : 'All suggested values confirmed',
    },
    {
      ok: checks.otp_verified,
      label: checks.otp_verified ? 'Phone and email verified' : 'Phone and email not verified yet',
    },
    {
      ok: checks.required_docs_uploaded >= checks.required_docs_total,
      label: `${checks.required_docs_uploaded} of ${checks.required_docs_total} required documents uploaded`,
    },
    {
      ok: consent || checks.terms_accepted,
      label: consent || checks.terms_accepted ? 'Terms accepted' : 'Terms not accepted yet',
    },
  ]
}

export function ReviewCard({ payload, onEditField, onSubmit }: ReviewCardProps) {
  const [consent, setConsent] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  const submitEnabled = canSubmitWithConsent(payload.blockers, consent)
  const hint = submitBlockerHint(payload.blockers, consent)

  const startEdit = (key: string, current: string | null) => {
    setEditingKey(key)
    setEditValue(current ?? '')
  }

  const cancelEdit = () => {
    setEditingKey(null)
    setEditValue('')
  }

  const saveEdit = () => {
    if (!editingKey) return
    onEditField(editingKey, editValue)
    cancelEdit()
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="review-card">
      <h2 className={styles.title}>Review your inquiry</h2>
      {payload.groups.map((group) => (
        <div key={group.title} className={styles.group}>
          <span className={styles.groupTitle}>{group.title}</span>
          {group.rows.map((row) => (
            <div key={row.key} className={styles.row}>
              <span className={styles.rowLabel}>{row.label}</span>
              {editingKey === row.key ? (
                <div className={styles.editRow}>
                  <input
                    className={styles.editInput}
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') saveEdit()
                      if (e.key === 'Escape') cancelEdit()
                    }}
                  />
                  <button type="button" className={shared.primaryBtn} onClick={saveEdit}>
                    Save
                  </button>
                  <button type="button" className={shared.secondaryBtn} onClick={cancelEdit}>
                    Cancel
                  </button>
                </div>
              ) : (
                <>
                  <span className={row.display ? styles.rowValue : styles.rowValueEmpty}>
                    {row.display ?? 'Not yet collected'}
                  </span>
                  <SourceBadge source={row.source} confirmed={row.confirmed} />
                  <button
                    type="button"
                    className={shared.textLink}
                    onClick={() => startEdit(row.key, row.display)}
                  >
                    Edit
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      ))}
      <div className={styles.checks}>
        <span className={styles.groupTitle}>Documents and checks</span>
        {checkRows(payload.checks, consent).map((c) => (
          <div key={c.label} className={styles.checkRow}>
            <span className={c.ok ? styles.dotOk : styles.dotNo} aria-hidden="true" />
            <span>{c.label}</span>
          </div>
        ))}
      </div>
      <label className={styles.consent}>
        <input
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
        />
        <span>
          I agree to the <a href="#">terms &amp; conditions</a> and{' '}
          <a href="#">privacy policy</a>.
        </span>
      </label>
      <button
        type="button"
        className={shared.primaryBtnFull}
        disabled={!submitEnabled}
        onClick={onSubmit}
      >
        Submit inquiry
      </button>
      {!submitEnabled && hint ? <p className={styles.hint}>{hint}</p> : null}
    </div>
  )
}

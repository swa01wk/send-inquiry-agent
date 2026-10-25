import { useEffect, useState } from 'react'
import { fetchMasterKind, type MasterListItem } from '../../api/client'
import type { DraftChecks, ReviewPayload } from '../../types/contracts'
import { SourceBadge } from '../draft/SourceBadge'
import { canSubmitWithConsent, submitBlockerHint } from './blockerHint'
import shared from './cards.module.css'
import styles from './ReviewCard.module.css'

interface ReviewCardProps {
  payload: ReviewPayload
  onEditField: (key: string, value: string) => Promise<boolean>
  onSubmit: () => void
}

const MASTER_KIND_BY_FIELD: Record<string, string> = {
  unit_type: 'unit_types',
  sales_category: 'sales_categories',
  lease_period: 'lease_periods',
  rent_period: 'rent_periods',
}

/** Review row key → draft field key for master-backed selects. */
function draftFieldKey(rowKey: string): string | null {
  if (rowKey in MASTER_KIND_BY_FIELD) return rowKey
  if (rowKey === 'lease') return 'lease_period'
  if (rowKey === 'rent') return 'rent_period'
  return null
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
      ok: checks.contact_verified,
      label: checks.contact_verified ? 'Contact verified' : 'Contact not verified yet',
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

function optionLabel(item: MasterListItem): string {
  if ('label' in item && item.label) return item.label
  if ('name' in item && item.name) return item.name
  return item.id
}

export function ReviewCard({ payload, onEditField, onSubmit }: ReviewCardProps) {
  const [consent, setConsent] = useState(false)
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [masterOptions, setMasterOptions] = useState<MasterListItem[]>([])
  const [editError, setEditError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const submitEnabled = canSubmitWithConsent(payload.blockers, consent)
  const hint = submitBlockerHint(payload.blockers, consent)

  const fieldKeyForEdit = editingKey ? draftFieldKey(editingKey) : null
  const masterKind = fieldKeyForEdit ? MASTER_KIND_BY_FIELD[fieldKeyForEdit] : null

  useEffect(() => {
    if (!masterKind) {
      setMasterOptions([])
      return
    }
    let cancelled = false
    void fetchMasterKind(masterKind).then((items) => {
      if (!cancelled) setMasterOptions(items)
    })
    return () => {
      cancelled = true
    }
  }, [masterKind])

  const startEdit = (rowKey: string, current: string | null) => {
    if (rowKey === 'malls') return
    setEditError(null)
    setEditingKey(rowKey)
    setEditValue(current ?? '')
  }

  const cancelEdit = () => {
    setEditingKey(null)
    setEditValue('')
    setEditError(null)
  }

  const saveEdit = async () => {
    if (!editingKey) return
    const fieldKey = draftFieldKey(editingKey) ?? editingKey
    setSaving(true)
    setEditError(null)
    const ok = await onEditField(fieldKey, editValue)
    setSaving(false)
    if (!ok) {
      setEditError("Couldn't save that change. Try again or pick another value.")
      return
    }
    cancelEdit()
  }

  const isMallsRow = (key: string) => key === 'malls'
  const usesSelect = (rowKey: string) => draftFieldKey(rowKey) !== null

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
                  {usesSelect(row.key) ? (
                    <select
                      className={styles.editInput}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      disabled={saving || masterOptions.length === 0}
                    >
                      <option value="">Select…</option>
                      {masterOptions.map((item) => (
                        <option key={item.id} value={item.id}>
                          {optionLabel(item)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className={styles.editInput}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') void saveEdit()
                        if (e.key === 'Escape') cancelEdit()
                      }}
                    />
                  )}
                  <button
                    type="button"
                    className={shared.primaryBtn}
                    onClick={() => void saveEdit()}
                    disabled={saving}
                  >
                    Save
                  </button>
                  <button type="button" className={shared.secondaryBtn} onClick={cancelEdit}>
                    Cancel
                  </button>
                  {editError ? <p className={styles.hint}>{editError}</p> : null}
                </div>
              ) : (
                <>
                  <span className={row.display ? styles.rowValue : styles.rowValueEmpty}>
                    {row.display ?? 'Not yet collected'}
                  </span>
                  <SourceBadge source={row.source} confirmed={row.confirmed} />
                  {isMallsRow(row.key) ? (
                    <span className={styles.mallHint}>Change the mall in the chat</span>
                  ) : (
                    <button
                      type="button"
                      className={shared.textLink}
                      onClick={() => startEdit(row.key, row.display)}
                    >
                      Edit
                    </button>
                  )}
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

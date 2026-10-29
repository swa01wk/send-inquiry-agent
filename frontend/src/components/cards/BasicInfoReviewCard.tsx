import { useState } from 'react'
import type { BasicInfoReviewPayload } from '../../types/contracts'
import { SourceBadge } from '../draft/SourceBadge'
import shared from './cards.module.css'
import styles from './BasicInfoReviewCard.module.css'

interface BasicInfoReviewCardProps {
  payload: BasicInfoReviewPayload
  onEditField: (key: string, value: string) => void
  onProceed: () => void
}

export function BasicInfoReviewCard({ payload, onEditField, onProceed }: BasicInfoReviewCardProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const done = payload.proceeded

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
    onEditField(editingKey, editValue.trim())
    cancelEdit()
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="basic-info-review-card">
      <h2 className={styles.title}>{payload.title}</h2>
      {payload.started_by ? (
        <p className={styles.startedBy}>Started by {payload.started_by}</p>
      ) : null}
      {done ? <p className={styles.doneLine}>Basic information confirmed</p> : null}
      {payload.rows.map((row) => (
        <div key={row.key} className={styles.row}>
          <span className={styles.rowLabel}>{row.label}</span>
          {editingKey === row.key && !done ? (
            <div className={styles.editRow}>
              <input
                className={styles.editInput}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') saveEdit()
                  if (e.key === 'Escape') cancelEdit()
                }}
                aria-label={row.label}
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
                {row.display ?? '—'}
              </span>
              <SourceBadge source={row.source} confirmed={row.confirmed} />
              {!done ? (
                <button
                  type="button"
                  className={shared.textLink}
                  onClick={() => startEdit(row.key, row.display)}
                >
                  Edit
                </button>
              ) : null}
            </>
          )}
        </div>
      ))}
      {!done && payload.missing.length > 0 ? (
        <p className={styles.missing}>Still needed: {payload.missing.join(', ')}</p>
      ) : null}
      {!done ? (
        <button
          type="button"
          className={shared.primaryBtnFull}
          disabled={!payload.can_proceed}
          onClick={onProceed}
        >
          Proceed
        </button>
      ) : null}
    </div>
  )
}

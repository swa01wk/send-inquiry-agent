import { useState } from 'react'
import type { ConfirmFieldRow, ConfirmFieldsPayload } from '../../types/contracts'
import { SourceBadge } from '../draft/SourceBadge'
import shared from './cards.module.css'
import styles from './ConfirmFieldsCard.module.css'
import { parseEvidence } from './formatEvidence'

interface ConfirmFieldsCardProps {
  cardId: string
  payload: ConfirmFieldsPayload
  /** One row's value button (18 Nov B1, M27): sends `confirm_field` for that key only. */
  onConfirmField: (key: string) => void
  /** Change: sends `edit_field` with the typed value. */
  onEditField: (key: string, value: string) => void
}

function EvidenceLine({ evidence }: { evidence: string }) {
  const parsed = parseEvidence(evidence)
  if (parsed.kind === 'document') {
    return (
      <span className={styles.evidence}>
        from: {parsed.label}, {parsed.fileName}
        {parsed.uploadedAt ? (
          <span className={styles.evidenceTime}> · {parsed.uploadedAt}</span>
        ) : null}
      </span>
    )
  }
  return <span className={styles.evidence}>from: &apos;{parsed.text}&apos;</span>
}

function waitsForTap(field: ConfirmFieldRow): boolean {
  return !field.confirmed && Boolean(field.display)
}

/**
 * Values the agent derived or a record prefilled, each confirmed on its own: the value is the
 * button ("Use Sara Ali"), Change edits it. There is no card-level confirm (18 Nov B1, NG3).
 */
export function ConfirmFieldsCard({
  cardId,
  payload,
  onConfirmField,
  onEditField,
}: ConfirmFieldsCardProps) {
  const [editingKey, setEditingKey] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')
  const [tapped, setTapped] = useState<Set<string>>(() => new Set())

  const startEdit = (field: ConfirmFieldRow) => {
    setEditingKey(field.key)
    setEditValue(field.display ?? '')
  }
  const cancelEdit = () => {
    setEditingKey(null)
    setEditValue('')
  }
  const saveEdit = () => {
    if (!editingKey || !editValue.trim()) return
    onEditField(editingKey, editValue.trim())
    cancelEdit()
  }
  const confirm = (key: string) => {
    setTapped((prev) => new Set(prev).add(key))
    onConfirmField(key)
  }

  return (
    <div className={shared.shellRows} data-testid={`confirm-fields-${cardId}`}>
      {payload.fields.map((field, index) => {
        const open = waitsForTap(field)
        return (
          <div
            key={field.key}
            className={`${styles.row} ${index < payload.fields.length - 1 ? shared.rowDivider : ''}`}
          >
            <span className={styles.label}>{field.label}</span>
            {editingKey === field.key ? (
              <div className={styles.editRow}>
                <input
                  className={styles.editInput}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveEdit()
                    if (e.key === 'Escape') cancelEdit()
                  }}
                  aria-label={field.label}
                  dir="auto"
                />
                <button type="button" className={shared.primaryBtn} onClick={saveEdit}>
                  Save
                </button>
                <button type="button" className={shared.secondaryBtn} onClick={cancelEdit}>
                  Cancel
                </button>
              </div>
            ) : open ? (
              <span className={styles.actions}>
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  data-testid={`confirm-field-${field.key}`}
                  aria-label={`Confirm ${field.label}: ${field.display ?? ''}`}
                  disabled={tapped.has(field.key)}
                  onClick={() => confirm(field.key)}
                >
                  Use <bdi className={styles.buttonValue}>{field.value_label ?? field.display}</bdi>
                </button>
                <button
                  type="button"
                  className={shared.textLink}
                  data-testid={`edit-field-${field.key}`}
                  aria-label={`Change ${field.label}`}
                  onClick={() => startEdit(field)}
                >
                  Change
                </button>
              </span>
            ) : (
              <span className={styles.value}>
                {field.confirmed && field.display ? (
                  <span className={styles.tick} aria-label="Confirmed">
                    ✓{' '}
                  </span>
                ) : null}
                <bdi>{field.display ?? '—'}</bdi>
              </span>
            )}
            {field.evidence ? <EvidenceLine evidence={field.evidence} /> : null}
            <SourceBadge source={field.source} confirmed={field.confirmed} />
          </div>
        )
      })}
    </div>
  )
}

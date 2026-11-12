import type { ContactRow, ContactsPayload } from '../../types/contracts'
import { SourceBadge } from '../draft/SourceBadge'
import shared from './cards.module.css'
import { contactBlockerLabel } from './contactBlockerLabel'
import styles from './ContactsCard.module.css'

interface ContactsCardProps {
  payload: ContactsPayload
  onSubmit: () => void
}

function contactDisplay(row: ContactRow): string {
  const name = [row.first_name, row.last_name].filter(Boolean).join(' ')
  const parts = [name, row.email, row.phone].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : 'Not added yet'
}

function approvalLabel(approval: NonNullable<ContactRow['approval']>): string {
  if (approval === 'pending') return 'Waiting for Cenomi'
  if (approval === 'approved') return 'Approved'
  return 'Needs a change'
}

function visibleRows(payload: ContactsPayload): ContactRow[] {
  const roles = payload.roles ?? []
  if (roles.length === 0) return payload.rows
  const allowed = new Set(roles)
  return payload.rows.filter((row) => allowed.has(row.role))
}

export function ContactsCard({ payload, onSubmit }: ContactsCardProps) {
  const labelByRole = Object.fromEntries(payload.rows.map((r) => [r.role, r.label]))
  const rows = visibleRows(payload)
  const stillNeeded = rows.filter((row) => row.required && !row.email).map((row) => row.label)

  return (
    <div className={`${shared.shell} ${styles.shell}`} data-testid="contacts-card">
      <div className={styles.header}>
        <span className={styles.title}>Company contacts</span>
        {payload.remarks ? <p className={styles.remarks}>{payload.remarks}</p> : null}
      </div>
      {rows.map((row) => (
        <div key={row.role} className={styles.row} data-testid={`contact-row-${row.role}`}>
          <div className={styles.labelRow}>
            <span className={styles.roleLabel}>{row.label}</span>
            {row.required ? <span className={styles.tagRequired}>Required</span> : null}
            <SourceBadge source={row.source} confirmed={row.confirmed} />
            {row.approval ? (
              <span
                className={`${styles.approvalChip} ${styles[`approval_${row.approval}`]}`}
                data-testid={`contact-approval-${row.role}`}
              >
                {approvalLabel(row.approval)}
                {row.approval === 'rejected' && row.approval_remarks
                  ? `: ${row.approval_remarks}`
                  : null}
              </span>
            ) : null}
          </div>
          <span className={styles.detail}>{contactDisplay(row)}</span>
          {row.same_as_primary ? (
            <span className={styles.sameAs}>Same as primary contact</span>
          ) : null}
        </div>
      ))}
      {stillNeeded.length > 0 ? (
        <p className={styles.stillNeeded} data-testid="contacts-still-needed">
          Still needed: {stillNeeded.join(', ')}
        </p>
      ) : null}
      {payload.blockers.length > 0 ? (
        <div className={styles.blockers} data-testid="contacts-blockers">
          <p className={styles.blockersTitle}>Before you can send</p>
          <ul className={styles.blockersList}>
            {payload.blockers.map((code) => (
              <li key={code}>{contactBlockerLabel(code, labelByRole[code.split(':')[1] ?? ''])}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className={styles.footer}>
        <button
          type="button"
          className={shared.primaryBtnFull}
          disabled={!payload.can_submit}
          onClick={onSubmit}
        >
          Send contacts
        </button>
      </div>
    </div>
  )
}

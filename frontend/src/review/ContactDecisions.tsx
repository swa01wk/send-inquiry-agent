import { useState } from 'react'
import type { BriefContact, ReviewAction } from '../api/review'
import styles from './review.module.css'

function ApprovalTag({ contact }: { contact: BriefContact }) {
  const testId = `contact-approval-${contact.role}`
  if (contact.approval === 'approved')
    return (
      <span className={styles.tagDone} data-testid={testId}>
        Approved
      </span>
    )
  if (contact.approval === 'rejected')
    return (
      <span className={styles.tagApplicant} data-testid={testId}>
        Rejected{contact.approval_remarks ? `: ${contact.approval_remarks}` : ''}
      </span>
    )
  // Flow v2 (V7): with per-contact approval off the brief sends no approval.
  if (!contact.approval) return null
  return (
    <span className={styles.tag} data-testid={testId}>
      Waiting for approval
    </span>
  )
}

interface ContactRowProps {
  contact: BriefContact
  canDecide: boolean
  busy: boolean
  onAct: (action: ReviewAction, payload: Record<string, unknown>) => void
}

/** One tenant contact; the first-level reviewer approves or rejects it (demo feedback §3.5). */
function ContactRow({ contact, canDecide, busy, onAct }: ContactRowProps) {
  const [remarks, setRemarks] = useState('')
  const pending = canDecide && contact.approval === 'pending' && Boolean(contact.contact_id)
  return (
    <li className={styles.decisionRow} data-testid={`contact-row-${contact.role}`}>
      <div className={styles.buttonRow}>
        <span>
          {contact.label}: {contact.name ?? '—'}, {contact.email ?? '—'}, {contact.phone ?? '—'}
          {contact.same_as_primary ? ' (primary contact)' : ''}
        </span>
        <ApprovalTag contact={contact} />
      </div>
      {pending ? (
        <div className={styles.decisionForm}>
          <label className={styles.label} htmlFor={`contact-remarks-${contact.role}`}>
            Remarks (needed to reject)
          </label>
          <input
            id={`contact-remarks-${contact.role}`}
            className={styles.input}
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
          />
          <div className={styles.buttonRow}>
            <button
              type="button"
              className={styles.primaryBtn}
              data-testid={`contact-approve-${contact.role}`}
              disabled={busy}
              onClick={() => onAct('approve_contact', { contact_id: contact.contact_id })}
            >
              Approve
            </button>
            <button
              type="button"
              className={styles.dangerBtn}
              data-testid={`contact-reject-${contact.role}`}
              disabled={busy || !remarks.trim()}
              onClick={() =>
                onAct('reject_contact', { contact_id: contact.contact_id, remarks: remarks.trim() })
              }
            >
              Reject
            </button>
          </div>
        </div>
      ) : null}
    </li>
  )
}

interface ContactDecisionsProps {
  contacts: BriefContact[]
  canDecide: boolean
  busy: boolean
  onAct: (action: ReviewAction, payload: Record<string, unknown>) => void
}

/** Tenant contacts with approval chips; buttons only for the role that decides. */
export function ContactDecisions({ contacts, canDecide, busy, onAct }: ContactDecisionsProps) {
  return (
    <ul className={styles.decisionList} data-testid="contact-decisions">
      {contacts.map((contact) => (
        <ContactRow
          key={`${contact.role}-${contact.contact_id ?? ''}`}
          contact={contact}
          canDecide={canDecide}
          busy={busy}
          onAct={onAct}
        />
      ))}
    </ul>
  )
}

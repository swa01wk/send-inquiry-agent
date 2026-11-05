import { useState } from 'react'
import type { BriefDocument, ExpiryStatus, ReviewAction } from '../api/review'
import styles from './review.module.css'

/** `2026-10-06` → "6 Oct 2026" (dates without a time zone). */
function formatDay(iso: string): string {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function expiryText(status: ExpiryStatus, expiry: string | null | undefined): string {
  if (status === 'unknown' || !expiry) return 'Expiry not known'
  if (status === 'expired') return `Expired on ${formatDay(expiry)}`
  if (status === 'expiring_soon') return `Expiring soon: ${formatDay(expiry)}`
  return `Valid until ${formatDay(expiry)}`
}

const EXPIRY_STYLE: Record<ExpiryStatus, string> = {
  expired: styles.tagApplicant,
  expiring_soon: styles.tagReviewer,
  valid: styles.tagDone,
  unknown: styles.tag,
}

function ApprovalTag({ doc }: { doc: BriefDocument }) {
  if (!doc.approval) return null
  if (doc.approval === 'approved')
    return (
      <span className={styles.tagDone} data-testid={`doc-approval-${doc.doc_type}`}>
        Approved
      </span>
    )
  if (doc.approval === 'rejected')
    return (
      <span className={styles.tagApplicant} data-testid={`doc-approval-${doc.doc_type}`}>
        Rejected{doc.approval_remarks ? `: ${doc.approval_remarks}` : ''}
      </span>
    )
  return (
    <span className={styles.tag} data-testid={`doc-approval-${doc.doc_type}`}>
      Waiting for a decision
    </span>
  )
}

interface DocumentRowProps {
  doc: BriefDocument
  canDecide: boolean
  busy: boolean
  onAct: (action: ReviewAction, payload: Record<string, unknown>) => void
  onOpen: (doc: BriefDocument) => void
}

/** One document: viewer link, expiry chip and date, Approve and Reject (demo feedback §3.4). */
function DocumentRow({ doc, canDecide, busy, onAct, onOpen }: DocumentRowProps) {
  const [expiryDate, setExpiryDate] = useState(doc.expiry ?? '')
  // An expired document preselects Reject with its remark; the reviewer still presses it.
  const [remarks, setRemarks] = useState(doc.suggested_reject_remarks ?? '')
  const status = doc.expiry_status ?? null
  const pending = canDecide && doc.approval === 'pending' && Boolean(doc.file_id)
  const blockedByExpiry =
    Boolean(doc.expiry_tracked) && (status === 'expired' || status === 'unknown')
  const ids = { doc_type: doc.doc_type, file_id: doc.file_id }

  return (
    <li className={styles.decisionRow} data-testid={`doc-row-${doc.doc_type}`}>
      <div className={styles.buttonRow}>
        <span>
          {doc.label}
          {doc.required ? ' (required)' : ''}:
        </span>
        {doc.uploaded && doc.file_id ? (
          <button type="button" className={styles.secondaryBtn} onClick={() => onOpen(doc)}>
            {doc.file_name}
          </button>
        ) : (
          <span className={styles.muted}>not uploaded</span>
        )}
        {doc.replaced_versions > 0 ? (
          <span className={styles.muted}>replaced {doc.replaced_versions}×</span>
        ) : null}
        {doc.expiry_tracked && status ? (
          <span className={EXPIRY_STYLE[status]} data-testid={`doc-expiry-status-${doc.doc_type}`}>
            {expiryText(status, doc.expiry)}
          </span>
        ) : null}
        <ApprovalTag doc={doc} />
      </div>
      {doc.review_status === 'pending' ? (
        <p className={styles.muted}>The document check didn’t answer: confirm the expiry date.</p>
      ) : null}
      {doc.decided_by && doc.approval !== 'pending' ? (
        <p className={styles.muted}>Decided by {doc.decided_by}</p>
      ) : null}
      {pending ? (
        <div className={styles.decisionForm}>
          {doc.expiry_tracked ? (
            <div className={styles.buttonRow}>
              <label className={styles.label} htmlFor={`doc-expiry-${doc.doc_type}`}>
                Expiry date
              </label>
              <input
                id={`doc-expiry-${doc.doc_type}`}
                data-testid={`doc-expiry-${doc.doc_type}`}
                type="date"
                className={styles.input}
                value={expiryDate}
                onChange={(e) => setExpiryDate(e.target.value)}
              />
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={busy || !expiryDate || expiryDate === doc.expiry}
                onClick={() =>
                  onAct('confirm_document_expiry', { ...ids, expiry_date: expiryDate })
                }
              >
                Save date
              </button>
            </div>
          ) : null}
          <label className={styles.label} htmlFor={`doc-remarks-${doc.doc_type}`}>
            Remarks (needed to reject)
          </label>
          <textarea
            id={`doc-remarks-${doc.doc_type}`}
            className={styles.textarea}
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
          />
          <div className={styles.buttonRow}>
            <button
              type="button"
              className={styles.primaryBtn}
              data-testid={`doc-approve-${doc.doc_type}`}
              disabled={busy || blockedByExpiry}
              onClick={() => onAct('approve_document', ids)}
            >
              Approve
            </button>
            <button
              type="button"
              className={styles.dangerBtn}
              data-testid={`doc-reject-${doc.doc_type}`}
              disabled={busy || !remarks.trim()}
              onClick={() => onAct('reject_document', { ...ids, remarks: remarks.trim() })}
            >
              Reject
            </button>
          </div>
        </div>
      ) : null}
    </li>
  )
}

interface DocumentDecisionsProps {
  documents: BriefDocument[]
  canDecide: boolean
  busy: boolean
  onAct: (action: ReviewAction, payload: Record<string, unknown>) => void
  onOpen: (doc: BriefDocument) => void
}

/** The case's documents with their first-level decisions (demo feedback §3.4). */
export function DocumentDecisions({
  documents,
  canDecide,
  busy,
  onAct,
  onOpen,
}: DocumentDecisionsProps) {
  return (
    <ul className={styles.decisionList} data-testid="document-decisions">
      {documents.map((doc) => (
        <DocumentRow
          key={`${doc.doc_type}-${doc.file_id ?? 'none'}-${doc.expiry ?? ''}`}
          doc={doc}
          canDecide={canDecide}
          busy={busy}
          onAct={onAct}
          onOpen={onOpen}
        />
      ))}
    </ul>
  )
}

import { useEffect, useState } from 'react'
import {
  listYardiBrands,
  searchYardiCompanies,
  type CaseDetail,
  type ReviewAction,
  type YardiBrand,
  type YardiCompany,
} from '../api/review'
import styles from './review.module.css'

/** Applied when the reviewer clicks **Use** on an assistant suggestion (never submits). */
export interface ActionsPrefill {
  token: number
  reuploadRemarks?: string
  rejectRemarks?: string
  requestRemarks?: string
  yardiCompanies?: YardiCompany[]
  yardiCompanyId?: string
  yardiBrandId?: string
}

interface ActionsPanelProps {
  detail: CaseDetail
  reviewerId: string
  busy: boolean
  error: string | null
  onAct: (action: ReviewAction, payload: Record<string, unknown>) => void
  prefill?: ActionsPrefill
}

/** Shown in the console in this order; only the legal ones render (L4 §3.3). */
const ORDER: ReviewAction[] = [
  'approve_first',
  'request_reupload',
  'request_contacts',
  'request_sales_data',
  'withdraw_request',
  'relink_company',
  'relink_brand',
  'remove_contact',
  'approve',
  'reject',
]

const TITLES: Record<string, string> = {
  approve_first: 'Approve first level',
  request_reupload: 'Request re-upload',
  request_contacts: 'Request contacts',
  request_sales_data: 'Request sales data',
  withdraw_request: 'Withdraw a request',
  relink_company: 'Yardi company',
  relink_brand: 'Yardi brand',
  remove_contact: 'Remove a contact',
  approve: 'Approve',
  reject: 'Reject',
}

const REQUEST_LABELS: Record<string, string> = {
  contacts: 'Contacts',
  sales_data: 'Sales data',
  reupload: 'Re-upload',
}

function categoryLabel(category: string): string {
  const text = category.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** `missing_contact:billing_contact` → "Billing contact missing" (codes from approval_blockers). */
function blockerLabel(code: string): string {
  const [kind, subject = ''] = code.split(':')
  if (kind === 'missing_contact') return `${categoryLabel(subject)} missing`
  if (kind === 'open_request')
    return `${REQUEST_LABELS[subject] ?? categoryLabel(subject)} request still open`
  return categoryLabel(code)
}

/** Link the case to a Yardi company, then one of that company's brands (second review). */
function YardiLink({
  detail,
  reviewerId,
  busy,
  canCompany,
  canBrand,
  onAct,
  prefill,
}: {
  detail: CaseDetail
  reviewerId: string
  busy: boolean
  canCompany: boolean
  canBrand: boolean
  onAct: ActionsPanelProps['onAct']
  prefill?: ActionsPrefill
}) {
  const linkedCompany = detail.brief.yardi.company_id
  const [query, setQuery] = useState(detail.brief.company ?? '')
  const [companies, setCompanies] = useState<YardiCompany[] | null>(null)
  const [companyId, setCompanyId] = useState('')
  const [brands, setBrands] = useState<YardiBrand[]>([])
  const [brandId, setBrandId] = useState('')
  const [lookupError, setLookupError] = useState<string | null>(null)

  useEffect(() => {
    setBrandId('')
    if (!canBrand || !linkedCompany) {
      setBrands([])
      return
    }
    let cancelled = false
    listYardiBrands(reviewerId, linkedCompany)
      .then((rows) => {
        if (!cancelled) setBrands(rows)
      })
      .catch(() => {
        if (!cancelled) setLookupError('Could not load the company’s brands.')
      })
    return () => {
      cancelled = true
    }
  }, [canBrand, linkedCompany, reviewerId])

  useEffect(() => {
    if (!prefill) return
    if (prefill.yardiCompanies !== undefined) setCompanies(prefill.yardiCompanies)
    if (prefill.yardiCompanyId !== undefined) setCompanyId(prefill.yardiCompanyId)
    if (prefill.yardiBrandId !== undefined) setBrandId(prefill.yardiBrandId)
  }, [prefill?.token, prefill])

  const search = () => {
    setLookupError(null)
    setCompanyId('')
    searchYardiCompanies(reviewerId, query.trim())
      .then(setCompanies)
      .catch(() => setLookupError('Yardi search failed.'))
  }

  return (
    <div className={styles.action} data-testid="action-yardi">
      <h3 className={styles.actionTitle}>Yardi link</h3>
      <p className={styles.muted} data-testid="yardi-linked">
        Company: {linkedCompany ?? 'not linked'} · Brand:{' '}
        {detail.brief.yardi.brand_id ?? 'not linked'}
      </p>
      {lookupError ? (
        <p className={styles.error} role="alert">
          {lookupError}
        </p>
      ) : null}
      {canCompany ? (
        <>
          <label className={styles.label} htmlFor="yardi-search">
            Search Yardi companies
          </label>
          <div className={styles.buttonRow}>
            <input
              id="yardi-search"
              className={styles.input}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <button
              type="button"
              className={styles.secondaryBtn}
              disabled={busy || !query.trim()}
              onClick={search}
            >
              Search
            </button>
          </div>
          {companies !== null && companies.length === 0 ? (
            <p className={styles.muted}>No active company matches.</p>
          ) : null}
          {companies !== null && companies.length > 0 ? (
            <>
              <label className={styles.label} htmlFor="yardi-company">
                Company
              </label>
              <select
                id="yardi-company"
                className={styles.select}
                value={companyId}
                onChange={(e) => setCompanyId(e.target.value)}
              >
                <option value="">Select…</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.id})
                  </option>
                ))}
              </select>
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={busy || !companyId}
                onClick={() => onAct('relink_company', { company_id: companyId })}
              >
                Link company
              </button>
            </>
          ) : null}
        </>
      ) : null}
      {canBrand && linkedCompany ? (
        <>
          <label className={styles.label} htmlFor="yardi-brand">
            Brand
          </label>
          <select
            id="yardi-brand"
            className={styles.select}
            value={brandId}
            onChange={(e) => setBrandId(e.target.value)}
          >
            <option value="">Select…</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.source})
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.secondaryBtn}
            disabled={busy || !brandId}
            onClick={() => onAct('relink_brand', { brand_id: brandId })}
          >
            Link brand
          </button>
        </>
      ) : null}
    </div>
  )
}

export function ActionsPanel({
  detail,
  reviewerId,
  busy,
  error,
  onAct,
  prefill,
}: ActionsPanelProps) {
  const legal = ORDER.filter((a) => detail.legal_actions.includes(a))
  const [reuploadDocs, setReuploadDocs] = useState<string[]>([])
  const [reuploadRemarks, setReuploadRemarks] = useState('')
  const [rejectRemarks, setRejectRemarks] = useState('')
  const [rejectCategory, setRejectCategory] = useState('')
  const [requestRemarks, setRequestRemarks] = useState('')
  const openKinds = detail.brief.requests
    .filter((r) => r.status === 'open' && r.kind !== 'reupload')
    .map((r) => r.kind)
  const [withdrawKind, setWithdrawKind] = useState('')
  const [removeRole, setRemoveRole] = useState('')

  useEffect(() => {
    if (!prefill) return
    if (prefill.reuploadRemarks !== undefined) setReuploadRemarks(prefill.reuploadRemarks)
    if (prefill.rejectRemarks !== undefined) setRejectRemarks(prefill.rejectRemarks)
    if (prefill.requestRemarks !== undefined) setRequestRemarks(prefill.requestRemarks)
  }, [prefill?.token, prefill])

  const toggleDoc = (docType: string) =>
    setReuploadDocs((current) =>
      current.includes(docType) ? current.filter((d) => d !== docType) : [...current, docType],
    )

  const awaitingApproval = detail.brief.status === 'second_review' && !legal.includes('approve')

  return (
    <section className={styles.panel} aria-labelledby="actions-title" data-testid="actions-panel">
      <h2 id="actions-title" className={styles.panelTitle}>
        Actions
      </h2>
      {legal.length === 0 ? (
        <p className={styles.muted} data-testid="no-actions">
          No decisions are open on this case right now.
        </p>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {legal.includes('approve_first') ? (
        <div className={styles.action} data-testid="action-approve_first">
          <h3 className={styles.actionTitle}>{TITLES.approve_first}</h3>
          <p className={styles.muted}>
            Makes the inquiry a lead: the applicant gets a Tenant Central invitation and a contacts
            request.
          </p>
          <button
            type="button"
            className={styles.primaryBtn}
            disabled={busy}
            onClick={() => onAct('approve_first', {})}
          >
            Approve first level
          </button>
        </div>
      ) : null}

      {legal.includes('request_reupload') ? (
        <div className={styles.action} data-testid="action-request_reupload">
          <h3 className={styles.actionTitle}>{TITLES.request_reupload}</h3>
          <fieldset className={styles.fieldset}>
            <legend className={styles.legend}>Documents</legend>
            {detail.reupload_doc_types.map((d) => (
              <label key={d.doc_type} className={styles.checkRow}>
                <input
                  type="checkbox"
                  checked={reuploadDocs.includes(d.doc_type)}
                  onChange={() => toggleDoc(d.doc_type)}
                />
                {d.label}
              </label>
            ))}
          </fieldset>
          <label className={styles.label} htmlFor="reupload-remarks">
            Remarks for the applicant
          </label>
          <textarea
            id="reupload-remarks"
            className={styles.textarea}
            value={reuploadRemarks}
            onChange={(e) => setReuploadRemarks(e.target.value)}
          />
          <button
            type="button"
            className={styles.secondaryBtn}
            disabled={busy || reuploadDocs.length === 0 || !reuploadRemarks.trim()}
            onClick={() =>
              onAct('request_reupload', {
                doc_types: reuploadDocs,
                remarks: reuploadRemarks.trim(),
              })
            }
          >
            Request re-upload
          </button>
        </div>
      ) : null}

      {legal.includes('request_contacts') || legal.includes('request_sales_data') ? (
        <div className={styles.action} data-testid="action-requests">
          <h3 className={styles.actionTitle}>Ask the applicant</h3>
          <label className={styles.label} htmlFor="request-remarks">
            Note for the applicant (optional)
          </label>
          <textarea
            id="request-remarks"
            className={styles.textarea}
            value={requestRemarks}
            onChange={(e) => setRequestRemarks(e.target.value)}
          />
          <div className={styles.buttonRow}>
            {legal.includes('request_contacts') ? (
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={busy}
                onClick={() => onAct('request_contacts', { remarks: requestRemarks.trim() })}
              >
                {TITLES.request_contacts}
              </button>
            ) : null}
            {legal.includes('request_sales_data') ? (
              <button
                type="button"
                className={styles.secondaryBtn}
                disabled={busy}
                onClick={() => onAct('request_sales_data', { remarks: requestRemarks.trim() })}
              >
                {TITLES.request_sales_data}
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {legal.includes('withdraw_request') && openKinds.length > 0 ? (
        <div className={styles.action} data-testid="action-withdraw_request">
          <h3 className={styles.actionTitle}>{TITLES.withdraw_request}</h3>
          <label className={styles.label} htmlFor="withdraw-kind">
            Request
          </label>
          <select
            id="withdraw-kind"
            className={styles.select}
            value={withdrawKind}
            onChange={(e) => setWithdrawKind(e.target.value)}
          >
            <option value="">Select…</option>
            {openKinds.map((kind) => (
              <option key={kind} value={kind}>
                {REQUEST_LABELS[kind] ?? kind}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.secondaryBtn}
            disabled={busy || !withdrawKind}
            onClick={() => onAct('withdraw_request', { kind: withdrawKind })}
          >
            Withdraw
          </button>
        </div>
      ) : null}

      {legal.includes('relink_company') || legal.includes('relink_brand') ? (
        <YardiLink
          detail={detail}
          reviewerId={reviewerId}
          busy={busy}
          canCompany={legal.includes('relink_company')}
          canBrand={legal.includes('relink_brand')}
          onAct={onAct}
          prefill={prefill}
        />
      ) : null}

      {legal.includes('remove_contact') && detail.brief.contacts.length > 0 ? (
        <div className={styles.action} data-testid="action-remove_contact">
          <h3 className={styles.actionTitle}>{TITLES.remove_contact}</h3>
          <label className={styles.label} htmlFor="remove-contact">
            Contact
          </label>
          <select
            id="remove-contact"
            className={styles.select}
            value={removeRole}
            onChange={(e) => setRemoveRole(e.target.value)}
          >
            <option value="">Select…</option>
            {detail.brief.contacts.map((c) => (
              <option key={c.role} value={c.role}>
                {c.label}: {c.name ?? '—'}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.secondaryBtn}
            disabled={busy || !removeRole}
            onClick={() => {
              onAct('remove_contact', { role: removeRole })
              setRemoveRole('')
            }}
          >
            Remove
          </button>
        </div>
      ) : null}

      {legal.includes('approve') ? (
        <div className={styles.action} data-testid="action-approve">
          <h3 className={styles.actionTitle}>{TITLES.approve}</h3>
          <p className={styles.muted}>
            Final approval: contacts are invited and the lead goes to Yardi.
          </p>
          <button
            type="button"
            className={styles.primaryBtn}
            disabled={busy}
            onClick={() => onAct('approve', {})}
          >
            Approve
          </button>
        </div>
      ) : null}
      {awaitingApproval && detail.approval_blockers.length > 0 ? (
        <div className={styles.action} data-testid="approval-blockers">
          <h3 className={styles.actionTitle}>Before final approval</h3>
          <ul className={styles.list}>
            {detail.approval_blockers.map((b) => (
              <li key={b}>{blockerLabel(b)}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {legal.includes('reject') ? (
        <div className={styles.action} data-testid="action-reject">
          <h3 className={styles.actionTitle}>{TITLES.reject}</h3>
          <label className={styles.label} htmlFor="reject-category">
            Reason
          </label>
          <select
            id="reject-category"
            className={styles.select}
            value={rejectCategory}
            onChange={(e) => setRejectCategory(e.target.value)}
          >
            <option value="">Select…</option>
            {detail.rejection_categories.map((c) => (
              <option key={c} value={c}>
                {categoryLabel(c)}
              </option>
            ))}
          </select>
          <label className={styles.label} htmlFor="reject-remarks">
            Remarks for the applicant
          </label>
          <textarea
            id="reject-remarks"
            className={styles.textarea}
            value={rejectRemarks}
            onChange={(e) => setRejectRemarks(e.target.value)}
          />
          <button
            type="button"
            className={styles.dangerBtn}
            disabled={busy || !rejectRemarks.trim() || !rejectCategory}
            onClick={() =>
              onAct('reject', { remarks: rejectRemarks.trim(), reason_category: rejectCategory })
            }
          >
            Reject
          </button>
        </div>
      ) : null}
    </section>
  )
}

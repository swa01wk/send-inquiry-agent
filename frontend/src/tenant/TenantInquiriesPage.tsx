import { useEffect, useState } from 'react'
import { listMyInquiries, type MyInquiry } from '../api/tenant'
import { TenantLayout } from './TenantLayout'
import { useTenantId } from './tenantSession'
import styles from './tenant.module.css'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

function InquiryList() {
  const [tenantId] = useTenantId()
  const [rows, setRows] = useState<MyInquiry[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!tenantId) return
    let cancelled = false
    listMyInquiries(tenantId)
      .then((data) => {
        if (!cancelled) setRows(data)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your inquiries.')
      })
    return () => {
      cancelled = true
    }
  }, [tenantId])

  if (error) return <p className={styles.error}>{error}</p>
  if (rows === null) return <p className={styles.muted}>Loading…</p>
  if (rows.length === 0) {
    return (
      <p className={styles.muted} data-testid="my-inquiries-empty">
        No inquiries yet. Raise one from Leasing Opportunities.
      </p>
    )
  }
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table} data-testid="my-inquiries">
        <thead>
          <tr>
            <th scope="col">Reference</th>
            <th scope="col">Brand</th>
            <th scope="col">Mall</th>
            <th scope="col">Product line</th>
            <th scope="col">Stage</th>
            <th scope="col">Last change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.reference}>
              <td>
                <a className={styles.link} href={r.tracking_url}>
                  {r.reference}
                </a>
              </td>
              <td>{r.brand ?? '—'}</td>
              <td>{r.mall ?? '—'}</td>
              <td>{r.product_line ?? '—'}</td>
              <td>{r.stage_label}</td>
              <td>{formatDate(r.last_change)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** `/tenant/inquiries`: every inquiry for the company, newest first (§3.5). */
export function TenantInquiriesPage() {
  return <TenantLayout title="My inquiries">{() => <InquiryList />}</TenantLayout>
}

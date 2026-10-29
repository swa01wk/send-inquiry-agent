import { useEffect, useState } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { listTenants, type TenantSummary } from '../api/tenant'
import { PageShell } from '../components/layout/PageShell'
import { useTenantId } from './tenantSession'
import styles from './tenant.module.css'

/** `/tenant`: mock Tenant Central sign-in (assumption D3), then Leasing Opportunities. */
export function TenantHomePage() {
  const [tenantId, setTenantId] = useTenantId()
  const [params] = useSearchParams()
  const asTenant = params.get('as')
  const [tenants, setTenants] = useState<TenantSummary[]>([])
  const [choice, setChoice] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (asTenant) setTenantId(asTenant)
  }, [asTenant, setTenantId])

  useEffect(() => {
    let cancelled = false
    listTenants()
      .then((rows) => {
        if (!cancelled) setTenants(rows)
      })
      .catch(() => {
        if (!cancelled) setError('Tenant Central isn’t available here.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (tenantId) return <Navigate to="/tenant/opportunities" replace />

  return (
    <PageShell
      title="Tenant Central"
      intro="Sign in to raise an inquiry from Leasing Opportunities (simulated sign-in)."
      showPanels={false}
    >
      <div className={styles.page}>
        <div className={styles.panel} data-testid="tenant-sign-in">
          <label className={styles.label} htmlFor="tenant-picker">
            Company
          </label>
          <select
            id="tenant-picker"
            className={styles.select}
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
          >
            <option value="">Select a company…</option>
            {tenants.map((t) => (
              <option key={t.id} value={t.id}>
                {t.company_name} — {t.contact_name}
              </option>
            ))}
          </select>
          <div className={styles.buttonRow}>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={!choice}
              onClick={() => setTenantId(choice)}
            >
              Sign in
            </button>
          </div>
          {error ? <p className={styles.error}>{error}</p> : null}
        </div>
      </div>
    </PageShell>
  )
}

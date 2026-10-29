import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { listTenants, type TenantSummary } from '../api/tenant'
import { PageShell } from '../components/layout/PageShell'
import { useTenantId } from './tenantSession'
import styles from './tenant.module.css'

/** The signed-in frame: company, Leasing Opportunities | My inquiries, Sign out. */
export function TenantLayout({
  title,
  children,
}: {
  title: string
  children: (tenant: TenantSummary) => ReactNode
}) {
  const [tenantId, setTenantId] = useTenantId()
  const [tenant, setTenant] = useState<TenantSummary | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!tenantId) return
    let cancelled = false
    listTenants()
      .then((rows) => {
        if (!cancelled) setTenant(rows.find((t) => t.id === tenantId) ?? null)
      })
      .catch(() => {
        if (!cancelled) setTenant(null)
      })
    return () => {
      cancelled = true
    }
  }, [tenantId])

  if (!tenantId) {
    return (
      <PageShell title={title} intro={null} showPanels={false}>
        <p className={styles.muted}>
          <Link className={styles.link} to="/tenant">
            Sign in to Tenant Central
          </Link>{' '}
          first.
        </p>
      </PageShell>
    )
  }

  return (
    <PageShell title={title} intro={null} showPanels={false}>
      <div className={styles.page}>
        <div className={styles.bar}>
          <p className={styles.who} data-testid="tenant-signed-in">
            {tenant ? (
              <>
                <span className={styles.whoName}>{tenant.company_name}</span> ·{' '}
                {tenant.contact_name}
              </>
            ) : (
              'Loading…'
            )}
          </p>
          <nav className={styles.nav} aria-label="Tenant Central">
            <NavLink
              className={({ isActive }) => (isActive ? styles.navActive : styles.navLink)}
              to="/tenant/opportunities"
            >
              Leasing Opportunities
            </NavLink>
            <NavLink
              className={({ isActive }) => (isActive ? styles.navActive : styles.navLink)}
              to="/tenant/inquiries"
            >
              My inquiries
            </NavLink>
            <button
              type="button"
              className={styles.secondaryBtn}
              onClick={() => {
                setTenantId(null)
                navigate('/tenant')
              }}
            >
              Sign out
            </button>
          </nav>
        </div>
        {tenant ? children(tenant) : null}
      </div>
    </PageShell>
  )
}

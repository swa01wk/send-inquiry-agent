import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listOpportunities,
  raiseInquiry,
  type Opportunity,
  type TenantSummary,
} from '../api/tenant'
import { TenantLayout } from './TenantLayout'
import { useTenantId } from './tenantSession'
import styles from './tenant.module.css'

function OpportunityList({ tenant }: { tenant: TenantSummary }) {
  const [tenantId] = useTenantId()
  const navigate = useNavigate()
  const [items, setItems] = useState<Opportunity[] | null>(null)
  const [city, setCity] = useState('')
  const [unitType, setUnitType] = useState('')
  const [brandId, setBrandId] = useState(tenant.brands.length === 1 ? tenant.brands[0].id : '')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!tenantId) return
    let cancelled = false
    listOpportunities(tenantId)
      .then((rows) => {
        if (!cancelled) setItems(rows)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load Leasing Opportunities.')
      })
    return () => {
      cancelled = true
    }
  }, [tenantId])

  const cities = useMemo(
    () => [...new Map((items ?? []).map((o) => [o.city_id, o.city])).entries()],
    [items],
  )
  const unitTypes = useMemo(
    () => [...new Map((items ?? []).map((o) => [o.unit_type, o.unit_type_label])).entries()],
    [items],
  )
  const shown = (items ?? []).filter(
    (o) => (!city || o.city_id === city) && (!unitType || o.unit_type === unitType),
  )

  const raise = async (opportunity: Opportunity) => {
    if (!tenantId) return
    setBusy(opportunity.id)
    setError(null)
    try {
      const session = await raiseInquiry(tenantId, opportunity.id, brandId || undefined)
      navigate('/', { state: { resumed: session } })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the inquiry.')
      setBusy(null)
    }
  }

  return (
    <>
      <div className={styles.filters}>
        <label className={styles.label} htmlFor="filter-city">
          City
        </label>
        <select
          id="filter-city"
          className={styles.select}
          value={city}
          onChange={(e) => setCity(e.target.value)}
        >
          <option value="">All cities</option>
          {cities.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
        <label className={styles.label} htmlFor="filter-type">
          Product line
        </label>
        <select
          id="filter-type"
          className={styles.select}
          value={unitType}
          onChange={(e) => setUnitType(e.target.value)}
        >
          <option value="">All product lines</option>
          {unitTypes.map(([id, label]) => (
            <option key={id} value={id}>
              {label}
            </option>
          ))}
        </select>
        {tenant.brands.length > 1 ? (
          <>
            <label className={styles.label} htmlFor="filter-brand">
              For brand
            </label>
            <select
              id="filter-brand"
              className={styles.select}
              value={brandId}
              onChange={(e) => setBrandId(e.target.value)}
            >
              <option value="">Choose in the chat</option>
              {tenant.brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </>
        ) : null}
      </div>
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
      {items === null ? <p className={styles.muted}>Loading…</p> : null}
      {items !== null && shown.length === 0 ? (
        <p className={styles.muted} data-testid="opportunities-empty">
          No opportunities match these filters.
        </p>
      ) : null}
      <ul className={styles.cards} data-testid="opportunities">
        {shown.map((o) => (
          <li key={o.id} className={styles.card} data-testid={`opportunity-${o.id}`}>
            <span className={styles.cardTitle}>{o.mall}</span>
            <span className={styles.muted}>
              {o.city} · {o.unit_type_label} · unit {o.unit_ref}
            </span>
            <span className={styles.muted}>
              {o.area_min === o.area_max ? `${o.area_min}` : `${o.area_min}–${o.area_max}`} sqm
            </span>
            <button
              type="button"
              className={styles.primaryBtn}
              disabled={busy !== null}
              onClick={() => void raise(o)}
            >
              {busy === o.id ? 'Opening…' : 'Raise inquiry'}
            </button>
          </li>
        ))}
      </ul>
    </>
  )
}

/** `/tenant/opportunities`: Raise inquiry opens the chat in existing-tenant mode (§3.5). */
export function TenantOpportunitiesPage() {
  return (
    <TenantLayout title="Leasing Opportunities">
      {(tenant) => <OpportunityList tenant={tenant} />}
    </TenantLayout>
  )
}

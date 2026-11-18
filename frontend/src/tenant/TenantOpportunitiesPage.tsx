import { useEffect, useMemo, useState } from 'react'
import { listOpportunities, type Opportunity } from '../api/tenant'
import { TenantLayout } from './TenantLayout'
import { useTenantId } from './tenantSession'
import styles from './tenant.module.css'

function OpportunityList() {
  const [tenantId] = useTenantId()
  const [items, setItems] = useState<Opportunity[] | null>(null)
  const [city, setCity] = useState('')
  const [unitType, setUnitType] = useState('')
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
            {/* 18 Nov (Swaroop): the unit code and area aren't shown to the tenant. */}
            <span className={styles.muted}>
              {o.city} · {o.unit_type_label}
            </span>
          </li>
        ))}
      </ul>
    </>
  )
}

/** `/tenant/opportunities`: where a registered company lands after signing in (chart S3,
 * M13). Read-only: raising an inquiry here (R4) isn't on the chart. */
export function TenantOpportunitiesPage() {
  return <TenantLayout title="Leasing Opportunities">{() => <OpportunityList />}</TenantLayout>
}

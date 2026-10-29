import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  listHandoffs,
  listStaff,
  newInquiry,
  openHandoff,
  type HandoffItem,
  type StaffMember,
} from '../api/callcentre'
import { PageShell } from '../components/layout/PageShell'
import styles from './callCentre.module.css'
import { useStaffId } from './staffSession'

function unknownStaff(err: unknown): boolean {
  return (
    err instanceof Error &&
    'code' in err &&
    (err as Error & { code: string }).code === 'unknown_staff'
  )
}

function formatCreatedAt(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Mock sign-in, new inquiries and handoffs from the applicant chat (spec §15). */
export function CallCentrePage() {
  const [staffId, setStaffId] = useStaffId()
  const [staff, setStaff] = useState<StaffMember[]>([])
  const [choice, setChoice] = useState('')
  const [handoffs, setHandoffs] = useState<HandoffItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyNew, setBusyNew] = useState(false)
  const [busyCaseId, setBusyCaseId] = useState<string | null>(null)
  const [params, setParams] = useSearchParams()
  const asStaff = params.get('as')
  const navigate = useNavigate()

  useEffect(() => {
    if (!asStaff) return
    setStaffId(asStaff)
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('as')
        return next
      },
      { replace: true },
    )
  }, [asStaff, setStaffId, setParams])

  useEffect(() => {
    let cancelled = false
    listStaff()
      .then((rows) => {
        if (!cancelled) setStaff(rows)
      })
      .catch(() => {
        if (!cancelled) setError('The call-centre console is not available.')
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!staffId) return
    let cancelled = false
    setHandoffs(null)
    setError(null)
    listHandoffs(staffId)
      .then((rows) => {
        if (!cancelled) setHandoffs(rows)
      })
      .catch((err) => {
        if (cancelled) return
        if (unknownStaff(err)) {
          setStaffId(null)
          return
        }
        setError('Could not load handoffs.')
      })
    return () => {
      cancelled = true
    }
  }, [staffId, setStaffId])

  const me = staff.find((s) => s.id === staffId) ?? null

  const startNewInquiry = async () => {
    if (!staffId) return
    setBusyNew(true)
    setError(null)
    try {
      const session = await newInquiry(staffId)
      navigate('/', { state: { resumed: session } })
    } catch (err) {
      if (unknownStaff(err)) {
        setStaffId(null)
        return
      }
      setError(err instanceof Error ? err.message : 'Could not start a new inquiry.')
    } finally {
      setBusyNew(false)
    }
  }

  const openCase = async (caseId: string) => {
    if (!staffId) return
    setBusyCaseId(caseId)
    setError(null)
    try {
      const session = await openHandoff(staffId, caseId)
      navigate('/', { state: { resumed: session } })
    } catch (err) {
      if (unknownStaff(err)) {
        setStaffId(null)
        return
      }
      setError(err instanceof Error ? err.message : 'Could not open that handoff.')
    } finally {
      setBusyCaseId(null)
    }
  }

  if (!staffId || !me) {
    return (
      <PageShell
        title="Call centre"
        intro="Sign in as call-centre or Guest Service staff (simulated)."
        showPanels={false}
      >
        <div className={styles.page}>
          <div className={styles.panel} data-testid="callcentre-sign-in">
            <label className={styles.label} htmlFor="staff-picker">
              Staff member
            </label>
            <select
              id="staff-picker"
              className={styles.select}
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
            >
              <option value="">Select a staff member…</option>
              {staff.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} — {s.role_label}
                </option>
              ))}
            </select>
            <div className={styles.buttonRow}>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={!choice}
                onClick={() => setStaffId(choice)}
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

  return (
    <PageShell title="Call centre" intro={null} showPanels={false}>
      <div className={styles.page}>
        <div className={styles.bar}>
          <p className={styles.who} data-testid="callcentre-signed-in">
            Signed in as <span className={styles.whoName}>{me.name}</span>, {me.role_label}
          </p>
          <div className={styles.buttonRow}>
            <button
              type="button"
              className={styles.primaryBtn}
              data-testid="callcentre-new-inquiry"
              disabled={busyNew}
              onClick={() => void startNewInquiry()}
            >
              {busyNew ? 'Starting…' : 'New inquiry'}
            </button>
            <button type="button" className={styles.secondaryBtn} onClick={() => setStaffId(null)}>
              Switch user
            </button>
          </div>
        </div>
        {error ? <p className={styles.error}>{error}</p> : null}
        <div className={styles.card} data-testid="callcentre-handoffs">
          <h2 className={styles.sectionTitle}>Handoffs from applicant chat</h2>
          {handoffs === null ? <p className={styles.muted}>Loading…</p> : null}
          {handoffs !== null && handoffs.length === 0 ? (
            <p className={styles.muted}>No open handoffs</p>
          ) : null}
          {handoffs !== null && handoffs.length > 0 ? (
            <ul className={styles.handoffList}>
              {handoffs.map((h) => (
                <li
                  key={h.case_id}
                  className={styles.handoffItem}
                  data-testid={`handoff-${h.case_id}`}
                >
                  <div className={styles.handoffMeta}>
                    <p className={styles.handoffRef}>{h.short_ref}</p>
                    <p className={styles.handoffReason}>{h.reason_label}</p>
                    <p className={styles.handoffSummary}>{h.summary}</p>
                    <p className={styles.handoffWhen}>{formatCreatedAt(h.created_at)}</p>
                  </div>
                  <button
                    type="button"
                    className={styles.secondaryBtn}
                    disabled={busyCaseId !== null}
                    onClick={() => void openCase(h.case_id)}
                  >
                    {busyCaseId === h.case_id ? 'Opening…' : 'Open'}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </PageShell>
  )
}

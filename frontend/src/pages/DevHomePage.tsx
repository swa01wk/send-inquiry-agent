import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  advanceClock,
  clockToMorning,
  getClock,
  resetDemo,
  type ClockState,
  type TickResult,
} from '../api/dev'
import { listReviewers, type Reviewer } from '../api/review'
import { PageShell } from '../components/layout/PageShell'
import { REVIEWER_CONSOLE } from '../config'
import { ROLE_LABELS, regionLabel } from '../review/reviewerSession'
import styles from './devHome.module.css'

function clockText(clock: ClockState): string {
  const local = new Date(clock.now).toLocaleString('en-GB', {
    timeZone: clock.timezone,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
  const offset = clock.offset_hours > 0 ? ` (+${clock.offset_hours} h)` : ''
  return `${local} ${clock.timezone.split('/').pop()} time${offset}`
}

/** `/dev`: every persona in one click, the simulated clock and a clean reset (spec §14). */
export function DevHomePage() {
  const [clock, setClock] = useState<ClockState | null>(null)
  const [reviewers, setReviewers] = useState<Reviewer[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)

  const refresh = useCallback(async () => {
    try {
      setClock(await getClock())
    } catch {
      setMessage('The dev API isn’t available (is DEV_TOOLS on?).')
    }
  }, [])

  useEffect(() => {
    void refresh()
    if (REVIEWER_CONSOLE) {
      listReviewers()
        .then(setReviewers)
        .catch(() => setReviewers([]))
    }
  }, [refresh])

  const tickMessage = (result: TickResult) =>
    `Clock moved. ${result.raised} raised, ${result.sent} sent, ${result.resolved} resolved.`

  const run = async (work: () => Promise<string>) => {
    setBusy(true)
    try {
      setMessage(await work())
      await refresh()
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'That didn’t work.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <PageShell title="Demo" intro="Every persona, the clock and a clean start." showPanels={false}>
      <div className={styles.page} data-testid="dev-home">
        <section className={styles.panel} aria-labelledby="personas-title">
          <h2 id="personas-title" className={styles.title}>
            Personas
          </h2>
          <ul className={styles.links}>
            <li>
              <Link className={styles.link} to="/">
                Applicant chat (Send an inquiry)
              </Link>
            </li>
            <li>
              <Link className={styles.link} to="/dev/inbox">
                Dev inbox (emails and SMS)
              </Link>
            </li>
            {REVIEWER_CONSOLE ? (
              <li>
                <Link className={styles.link} to="/review/attention">
                  Needs attention (signed-in reviewer)
                </Link>
              </li>
            ) : null}
          </ul>
          {REVIEWER_CONSOLE && reviewers.length > 0 ? (
            <>
              <h3 className={styles.subtitle}>Reviewer console</h3>
              <ul className={styles.links} data-testid="dev-reviewers">
                {reviewers.map((r) => (
                  <li key={r.id}>
                    <Link className={styles.link} to={`/review?as=${encodeURIComponent(r.id)}`}>
                      {r.name} — {ROLE_LABELS[r.role] ?? r.role},{' '}
                      {r.manager ? 'manager, all regions' : r.regions.map(regionLabel).join(', ')}
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>

        <section className={styles.panel} aria-labelledby="clock-title">
          <h2 id="clock-title" className={styles.title}>
            Clock
          </h2>
          <p className={styles.muted} data-testid="dev-clock">
            {clock ? clockText(clock) : 'Loading…'}
          </p>
          <div className={styles.buttons}>
            <button
              type="button"
              className={styles.button}
              disabled={busy || !clock?.simulated}
              onClick={() => void run(async () => tickMessage(await advanceClock(24)))}
            >
              +24 h
            </button>
            <button
              type="button"
              className={styles.button}
              disabled={busy || !clock?.simulated}
              onClick={() => void run(async () => tickMessage(await advanceClock(48)))}
            >
              +48 h
            </button>
            <button
              type="button"
              className={styles.button}
              disabled={busy || !clock?.simulated}
              onClick={() => void run(async () => tickMessage(await clockToMorning()))}
            >
              To morning (08:00)
            </button>
          </div>
        </section>

        <section className={styles.panel} aria-labelledby="reset-title">
          <h2 id="reset-title" className={styles.title}>
            Reset
          </h2>
          <p className={styles.muted}>
            Deletes every session, case, message, invitation and Yardi lead, and resets the clock.
          </p>
          <div className={styles.buttons}>
            {confirmReset ? (
              <>
                <button
                  type="button"
                  className={styles.danger}
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await resetDemo()
                      setConfirmReset(false)
                      return 'Demo reset. Everything starts clean.'
                    })
                  }
                >
                  Yes, reset everything
                </button>
                <button
                  type="button"
                  className={styles.button}
                  onClick={() => setConfirmReset(false)}
                >
                  Cancel
                </button>
              </>
            ) : (
              <button
                type="button"
                className={styles.danger}
                disabled={busy}
                onClick={() => setConfirmReset(true)}
              >
                Reset demo
              </button>
            )}
          </div>
        </section>
        {message ? (
          <p className={styles.muted} role="status" data-testid="dev-message">
            {message}
          </p>
        ) : null}
      </div>
    </PageShell>
  )
}

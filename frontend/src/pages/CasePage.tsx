import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { openCase } from '../api/client'
import { PageShell } from '../components/layout/PageShell'
import styles from './flowPage.module.css'

type CaseOpenState = { kind: 'loading' } | { kind: 'error'; code: string; message: string }

/** One in-flight POST per token (StrictMode runs effects twice in dev). */
const openInflight = new Map<string, ReturnType<typeof openCase>>()

function openCaseOnce(token: string) {
  let pending = openInflight.get(token)
  if (!pending) {
    pending = openCase(token)
    openInflight.set(token, pending)
  }
  return pending
}

export function CasePage() {
  const [params] = useSearchParams()
  const token = params.get('t') ?? ''
  const navigate = useNavigate()
  const [state, setState] = useState<CaseOpenState>({ kind: 'loading' })

  useEffect(() => {
    if (!token) {
      setState({
        kind: 'error',
        code: 'token_invalid',
        message: "This link isn't valid.",
      })
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const session = await openCaseOnce(token)
        if (!cancelled) {
          navigate('/', { replace: true, state: { resumed: session } })
        }
      } catch (err) {
        if (cancelled) return
        const code =
          err && typeof err === 'object' && 'code' in err
            ? String((err as { code: string }).code)
            : 'request_failed'
        const message = err instanceof Error ? err.message : 'Something went wrong.'
        setState({ kind: 'error', code, message })
      }
    })()

    return () => {
      cancelled = true
    }
  }, [token, navigate])

  return (
    <PageShell title="Your inquiry" intro={null} showPanels={false}>
      <div className={styles.card} data-testid="case-page">
        {state.kind === 'loading' ? <p className={styles.body}>Opening your inquiry…</p> : null}
        {state.kind === 'error' ? (
          <>
            <h2 className={styles.headline}>Couldn&apos;t open your inquiry</h2>
            <p className={styles.error}>{state.message}</p>
            {state.code === 'token_expired' || state.code === 'token_invalid' ? (
              <p className={styles.body}>
                Use the <strong>Track your inquiry</strong> link from your submission email or SMS
                to open your case in chat.
              </p>
            ) : null}
            <div className={styles.actions}>
              <Link to="/" className={styles.textLink}>
                Back to inquiry chat
              </Link>
            </div>
          </>
        ) : null}
      </div>
    </PageShell>
  )
}

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { resumeSession, verifyEmailLink } from '../api/client'
import { PageShell } from '../components/layout/PageShell'
import type { VerifyEmailResponse } from '../types/contracts'
import styles from './flowPage.module.css'

type VerifyState =
  | { kind: 'loading' }
  | { kind: 'verified'; data: VerifyEmailResponse }
  | { kind: 'error'; code: string; message: string }

/** One in-flight POST per token (StrictMode runs effects twice in dev). */
const verifyInflight = new Map<string, Promise<VerifyEmailResponse>>()

function verifyOnce(token: string): Promise<VerifyEmailResponse> {
  let pending = verifyInflight.get(token)
  if (!pending) {
    pending = verifyEmailLink(token)
    verifyInflight.set(token, pending)
  }
  return pending
}

export function VerifyPage() {
  const [params] = useSearchParams()
  const token = params.get('t') ?? ''
  const navigate = useNavigate()
  const [state, setState] = useState<VerifyState>({ kind: 'loading' })
  const [continuing, setContinuing] = useState(false)

  useEffect(() => {
    if (!token) {
      setState({
        kind: 'error',
        code: 'token_invalid',
        message: "This verification link isn't valid.",
      })
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const data = await verifyOnce(token)
        if (!cancelled) setState({ kind: 'verified', data })
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
  }, [token])

  const continueInquiry = useCallback(async () => {
    if (state.kind !== 'verified') return
    setContinuing(true)
    try {
      const session = await resumeSession(state.data.resume_token)
      navigate('/', { replace: true, state: { resumed: session } })
    } catch {
      setContinuing(false)
      setState({
        kind: 'error',
        code: 'resume_failed',
        message: "We couldn't reopen your inquiry. Try the link from your email again.",
      })
    }
  }, [navigate, state])

  return (
    <PageShell title="Verify your email" intro={null} showPanels={false}>
      <div className={styles.card} data-testid="verify-page">
        {state.kind === 'loading' ? <p className={styles.body}>Checking your link…</p> : null}
        {state.kind === 'verified' ? (
          <>
            <h2 className={styles.headline}>Email verified</h2>
            <p className={styles.body}>
              {state.data.email_masked
                ? `${state.data.email_masked} is confirmed. You can continue your inquiry in the chat.`
                : 'Your email is confirmed. You can continue your inquiry in the chat.'}
            </p>
            <div className={styles.actions}>
              <button
                type="button"
                className={styles.primaryBtn}
                disabled={continuing}
                onClick={() => void continueInquiry()}
              >
                Continue your inquiry
              </button>
            </div>
          </>
        ) : null}
        {state.kind === 'error' ? (
          <>
            <h2 className={styles.headline}>Couldn&apos;t verify your email</h2>
            <p className={styles.error}>{state.message}</p>
            {state.code === 'token_expired' ? (
              <p className={styles.body}>
                Open your inquiry in the chat and tap <strong>Resend link</strong> on the
                verification card for a fresh link.
              </p>
            ) : null}
            {state.code === 'token_used' ? (
              <p className={styles.body}>
                If you still need to verify, use the newest link we emailed you, or resend from the
                verification card in your chat.
              </p>
            ) : null}
            {state.code === 'email_changed' ? (
              <p className={styles.body}>
                Update your email in the chat if needed, then request a new verification link.
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

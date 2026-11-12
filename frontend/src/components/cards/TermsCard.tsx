import { useEffect, useRef, useState } from 'react'
import type { TermsPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './TermsCard.module.css'

interface TermsCardProps {
  payload: TermsPayload
  /** Resolves false when the action did not complete; void means success. */
  onAccept: () => void | boolean | Promise<void | boolean>
}

export function TermsCard({ payload, onAccept }: TermsCardProps) {
  const [optimistic, setOptimistic] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const postedRef = useRef(false)

  const accepted = payload.accepted || optimistic

  useEffect(() => {
    if (payload.accepted) {
      setOptimistic(false)
      setError(null)
      setBusy(false)
      postedRef.current = false
    }
  }, [payload.accepted])

  const tryAccept = async () => {
    if (accepted || busy || postedRef.current) return
    postedRef.current = true
    setBusy(true)
    setOptimistic(true)
    setError(null)
    try {
      const result = onAccept()
      if (result && typeof (result as Promise<void | boolean>).then === 'function') {
        const ok = await (result as Promise<void | boolean>)
        if (ok === false) {
          setOptimistic(false)
          postedRef.current = false
          setError("We couldn't save your acceptance. Please try again.")
        }
      }
    } catch {
      setOptimistic(false)
      postedRef.current = false
      setError("We couldn't save your acceptance. Please try again.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="terms-card">
      <p className={styles.text}>{payload.text}</p>
      <label className={styles.consent}>
        <input
          type="checkbox"
          checked={accepted}
          disabled={accepted || busy}
          onChange={(e) => {
            if (e.target.checked) void tryAccept()
          }}
        />
        <span>
          I agree to the terms &amp; conditions and the{' '}
          <a href={payload.privacy_url}>privacy policy</a>.
        </span>
      </label>
      {accepted ? (
        <p className={styles.accepted} data-testid="terms-accepted">
          Terms accepted
        </p>
      ) : null}
      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

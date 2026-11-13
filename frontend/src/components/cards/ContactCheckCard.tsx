import { useState } from 'react'
import type { ContactCheckPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './ContactCheckCard.module.css'

interface ContactCheckCardProps {
  payload: ContactCheckPayload
  onCheck: (email: string) => void
}

/** Flow v2 (§3.4): call centre, existing CR → is the caller's contact already a user? */
export function ContactCheckCard({ payload, onCheck }: ContactCheckCardProps) {
  const [email, setEmail] = useState('')
  const trimmed = email.trim()

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="contact-check-card">
      <p className={styles.prompt}>{payload.prompt}</p>

      {payload.error ? (
        <p className={styles.error} role="alert">
          {payload.error}
        </p>
      ) : null}

      {payload.state === 'existing' ? (
        <p className={styles.doneLine}>
          {payload.email_masked} already has a Tenant Central login.
        </p>
      ) : null}

      {payload.state === 'new' ? (
        <p className={styles.doneLine}>
          {payload.email_masked} is a new contact — capture the inquiry fresh.
        </p>
      ) : null}

      {payload.state === 'open' ? (
        <div className={styles.fieldRow}>
          <label className={styles.label} htmlFor="contact-check-email">
            {payload.input_placeholder}
          </label>
          <input
            id="contact-check-email"
            className={styles.input}
            type="email"
            inputMode="email"
            autoComplete="off"
            placeholder={payload.input_placeholder}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && trimmed) onCheck(trimmed)
            }}
          />
          <button
            type="button"
            className={shared.primaryBtnFull}
            disabled={!trimmed}
            onClick={() => onCheck(trimmed)}
          >
            {payload.check_label}
          </button>
        </div>
      ) : null}
    </div>
  )
}

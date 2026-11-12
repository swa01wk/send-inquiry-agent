import { useState } from 'react'
import type { CompanyRegistrationPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './CompanyRegistrationCard.module.css'

interface CompanyRegistrationCardProps {
  payload: CompanyRegistrationPayload
  onVerify: (crNumber: string) => void
  onSkip: () => void
  onConfirmSkip: () => void
  onDismissSkipConfirm: () => void
}

export function CompanyRegistrationCard({
  payload,
  onVerify,
  onSkip,
  onConfirmSkip,
  onDismissSkipConfirm,
}: CompanyRegistrationCardProps) {
  const [cr, setCr] = useState('')
  const [dismissedConfirm, setDismissedConfirm] = useState(false)

  const showConfirm = payload.state === 'confirm_skip' && !dismissedConfirm
  const locked = payload.state === 'registered' || payload.state === 'skipped'

  const handleDismissConfirm = () => {
    setDismissedConfirm(true)
    onDismissSkipConfirm()
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="company-registration-card">
      <p className={styles.prompt}>{payload.prompt}</p>

      {payload.cr_masked ? (
        <p className={styles.masked} data-testid="cr-masked">
          CR {payload.cr_masked}
        </p>
      ) : null}

      {payload.error ? (
        <p className={styles.error} role="alert">
          {payload.error}
        </p>
      ) : null}

      {payload.state === 'registered' ? (
        <p className={styles.doneLine}>Already registered — sign in below.</p>
      ) : null}

      {payload.state === 'skipped' ? (
        <p className={styles.doneLine}>Continuing without a CR number.</p>
      ) : null}

      {payload.state === 'not_registered' ? (
        <p className={styles.doneLine}>CR checked — not registered yet. Let&apos;s continue.</p>
      ) : null}

      {showConfirm ? (
        <div className={styles.confirmBlock} data-testid="skip-confirm">
          <p className={styles.confirmPrompt}>{payload.skip_confirm.prompt}</p>
          <div className={styles.actions}>
            <button type="button" className={shared.primaryBtnFull} onClick={onConfirmSkip}>
              {payload.skip_confirm.yes_label}
            </button>
            <button type="button" className={shared.secondaryBtn} onClick={handleDismissConfirm}>
              {payload.skip_confirm.no_label}
            </button>
          </div>
        </div>
      ) : null}

      {!locked && !showConfirm ? (
        <div className={styles.fieldRow}>
          <label className={styles.label} htmlFor="company-reg-cr">
            {payload.input_placeholder}
          </label>
          <input
            id="company-reg-cr"
            className={styles.input}
            inputMode="numeric"
            autoComplete="off"
            placeholder={payload.input_placeholder}
            value={cr}
            onChange={(e) => setCr(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && cr.trim()) onVerify(cr.trim())
            }}
          />
          <div className={styles.actions}>
            <button
              type="button"
              className={shared.primaryBtnFull}
              onClick={() => onVerify(cr.trim())}
              disabled={!cr.trim()}
            >
              {payload.verify_label}
            </button>
            <button type="button" className={shared.textLink} onClick={onSkip}>
              {payload.skip_label}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

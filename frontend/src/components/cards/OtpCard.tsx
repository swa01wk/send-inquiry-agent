import { useState } from 'react'
import type { OtpInputPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './OtpCard.module.css'

interface OtpCardProps {
  payload: OtpInputPayload
  onVerify: (code: string) => void
  onResend: () => void
}

function sentToCaption(sentTo: OtpInputPayload['sent_to']): string {
  const parts: string[] = []
  if (sentTo.mobile_masked) parts.push(sentTo.mobile_masked)
  if (sentTo.email_masked) parts.push(sentTo.email_masked)
  return parts.length ? `Sent to ${parts.join(' and ')}` : ''
}

export function OtpCard({ payload, onVerify, onResend }: OtpCardProps) {
  const [code, setCode] = useState('')
  const maxLen = payload.code_length
  const showError = !payload.verified && payload.attempts_left < 3

  const onChange = (raw: string) => {
    const digits = raw.replace(/\D/g, '').slice(0, maxLen)
    setCode(digits)
  }

  const verify = () => {
    if (!code) return
    onVerify(code)
    setCode('')
  }

  if (payload.verified) {
    return (
      <div className={`${shared.shellPad} ${styles.verified}`} data-testid="otp-card">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M5 12l5 5L20 7"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span>Phone and email verified</span>
      </div>
    )
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="otp-card">
      <label className={styles.label} htmlFor="otp-code">
        Verification code
      </label>
      <div className={styles.row}>
        <input
          id="otp-code"
          className={styles.input}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={maxLen}
          placeholder="4-digit code"
          value={code}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className={shared.primaryBtn} onClick={verify}>
          Verify
        </button>
      </div>
      {showError ? (
        <p className={shared.captionError}>
          That code didn&apos;t match. {payload.attempts_left} attempts left.
        </p>
      ) : (
        <p className={shared.caption}>{sentToCaption(payload.sent_to)}</p>
      )}
      <button type="button" className={shared.textLink} onClick={onResend}>
        Resend code
      </button>
    </div>
  )
}

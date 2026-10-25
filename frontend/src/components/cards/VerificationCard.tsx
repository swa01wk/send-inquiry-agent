import { useState } from 'react'
import type { VerificationMobile, VerificationPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './VerificationCard.module.css'

interface VerificationCardProps {
  payload: VerificationPayload
  onVerifyEmail: (token: string) => void
  onResendEmailLink: () => void
  onVerifyCode: (code: string) => void
  onResendCode: () => void
}

function CheckIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M5 12l5 5L20 7"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function Verified({ label }: { label: string }) {
  return (
    <div className={styles.verified}>
      <CheckIcon />
      <span>{label}</span>
    </div>
  )
}

interface MobileCodeProps {
  mobile: VerificationMobile
  onVerifyCode: (code: string) => void
  onResendCode: () => void
}

function MobileCode({ mobile, onVerifyCode, onResendCode }: MobileCodeProps) {
  const [code, setCode] = useState('')
  const maxLen = mobile.code_length
  const showError = mobile.attempts_left < 3

  const onChange = (raw: string) => {
    setCode(raw.replace(/\D/g, '').slice(0, maxLen))
  }

  const verify = () => {
    if (!code) return
    onVerifyCode(code)
    setCode('')
  }

  return (
    <div className={styles.section}>
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
          placeholder={`${maxLen}-digit code`}
          value={code}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className={shared.primaryBtn} onClick={verify}>
          Verify
        </button>
      </div>
      {showError ? (
        <p className={shared.captionError}>
          That code didn&apos;t match. {mobile.attempts_left} attempts left.
        </p>
      ) : (
        <p className={shared.caption}>
          {mobile.masked ? `Sent by SMS to ${mobile.masked}` : 'Sent by SMS'}
        </p>
      )}
      <button type="button" className={shared.textLink} onClick={onResendCode}>
        Resend code
      </button>
    </div>
  )
}

/**
 * Email is verified by a one-time link; the mobile, when given, by an SMS code.
 * A landline-only applicant sees just the email section.
 */
export function VerificationCard({
  payload,
  onVerifyEmail,
  onResendEmailLink,
  onVerifyCode,
  onResendCode,
}: VerificationCardProps) {
  const { email, mobile } = payload

  if (payload.all_verified) {
    return (
      <div className={shared.shellPad} data-testid="verification-card">
        <Verified label={mobile ? 'Email and mobile verified' : 'Email verified'} />
      </div>
    )
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="verification-card">
      <div className={styles.section}>
        <span className={styles.label}>Email</span>
        {email.verified ? (
          <Verified label="Email verified" />
        ) : (
          <>
            <p className={shared.caption}>
              {email.masked
                ? `We sent a verification link to ${email.masked}. Open it to confirm your email.`
                : 'We sent you a verification link. Open it to confirm your email.'}
            </p>
            {email.demo_token ? (
              <button
                type="button"
                className={shared.secondaryBtn}
                onClick={() => onVerifyEmail(email.demo_token ?? '')}
              >
                Open verification link (demo)
              </button>
            ) : null}
            <button type="button" className={shared.textLink} onClick={onResendEmailLink}>
              Resend link
            </button>
          </>
        )}
      </div>
      {mobile ? (
        mobile.verified ? (
          <div className={styles.section}>
            <span className={styles.label}>Mobile</span>
            <Verified label="Mobile verified" />
          </div>
        ) : (
          <MobileCode mobile={mobile} onVerifyCode={onVerifyCode} onResendCode={onResendCode} />
        )
      ) : null}
    </div>
  )
}

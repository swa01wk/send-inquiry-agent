import { useRef, useState } from 'react'
import type { CompanyRegistrationPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './CompanyRegistrationCard.module.css'
import { fileExtension } from './documentFileCheck'

interface CompanyRegistrationCardProps {
  payload: CompanyRegistrationPayload
  onVerify: (crNumber: string) => void
  onSkip: () => void
  onConfirmSkip: () => void
  onDismissSkipConfirm: () => void
  /** M1: upload the CR certificate instead of typing; the server reads the number. */
  onUploadCertificate?: (file: File) => Promise<void>
}

export function CompanyRegistrationCard({
  payload,
  onVerify,
  onSkip,
  onConfirmSkip,
  onDismissSkipConfirm,
  onUploadCertificate,
}: CompanyRegistrationCardProps) {
  const [cr, setCr] = useState('')
  const [dismissedConfirm, setDismissedConfirm] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const showConfirm = payload.state === 'confirm_skip' && !dismissedConfirm
  const locked =
    payload.state === 'registered' ||
    payload.state === 'skipped' ||
    payload.state === 'continued_no_login'
  const allowed = payload.allowed_extensions ?? []

  const handleFile = async (file: File | undefined) => {
    if (!file || !onUploadCertificate) return
    if (allowed.length > 0 && !allowed.includes(fileExtension(file.name))) {
      setUploadError("That file type isn't supported.")
      return
    }
    setUploadError(null)
    setUploading(true)
    try {
      await onUploadCertificate(file)
    } catch {
      setUploadError("We couldn't upload that file. Please try again, or type the number.")
    } finally {
      setUploading(false)
    }
  }

  // Skip again after "No" must show the confirm again.
  const handleSkip = () => {
    setDismissedConfirm(false)
    onSkip()
  }

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

      {payload.certificate_name ? (
        <p className={styles.masked} data-testid="cr-certificate-name">
          CR certificate: {payload.certificate_name}
        </p>
      ) : null}

      {payload.error || uploadError ? (
        <p className={styles.error} role="alert">
          {uploadError ?? payload.error}
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

      {payload.state === 'continued_no_login' ? (
        <p className={styles.doneLine}>
          Registered company — continuing as a new inquiry without a login.
        </p>
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
            <button type="button" className={shared.textLink} onClick={handleSkip}>
              {payload.skip_label}
            </button>
          </div>
          {onUploadCertificate ? (
            <div className={styles.uploadRow}>
              <span className={styles.orLine}>or</span>
              <input
                ref={fileRef}
                className={styles.hiddenInput}
                type="file"
                accept={allowed.join(',')}
                data-testid="cr-certificate-input"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  e.target.value = ''
                  void handleFile(f)
                }}
              />
              <button
                type="button"
                className={shared.secondaryBtn}
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
              >
                {uploading ? 'Uploading…' : (payload.upload_label ?? 'Upload CR certificate')}
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

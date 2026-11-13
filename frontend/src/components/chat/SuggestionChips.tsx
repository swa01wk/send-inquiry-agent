import { useState } from 'react'
import type { QuickReplyOption } from '../../types/contracts'
import styles from './SuggestionChips.module.css'

interface SuggestionChipsProps {
  options: QuickReplyOption[]
  onSelect: (text: string) => void
  onFocusInput?: (placeholder: string) => void
  onResumePending?: (email: string) => void
  hidden: boolean
}

export function SuggestionChips({
  options,
  onSelect,
  onFocusInput,
  onResumePending,
  hidden,
}: SuggestionChipsProps) {
  const [resumeOpen, setResumeOpen] = useState(false)
  const [resumeEmail, setResumeEmail] = useState('')

  if (hidden || (options.length === 0 && !resumeOpen)) return null

  const resumeOption = options.find((o) => o.action === 'resume_pending')

  if (resumeOpen && resumeOption) {
    return (
      <div className={styles.wrap} data-testid="resume-pending-inline">
        <label className={styles.resumeLabel} htmlFor="resume-pending-email">
          {resumeOption.placeholder ?? 'Your email address'}
        </label>
        <div className={styles.resumeRow}>
          <input
            id="resume-pending-email"
            className={styles.resumeInput}
            type="email"
            autoComplete="email"
            value={resumeEmail}
            onChange={(e) => setResumeEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && resumeEmail.trim()) {
                onResumePending?.(resumeEmail.trim())
                setResumeOpen(false)
                setResumeEmail('')
              }
            }}
          />
          <button
            type="button"
            className={styles.resumeSend}
            disabled={!resumeEmail.trim()}
            onClick={() => {
              onResumePending?.(resumeEmail.trim())
              setResumeOpen(false)
              setResumeEmail('')
            }}
          >
            Continue
          </button>
          <button
            type="button"
            className={styles.resumeCancel}
            onClick={() => {
              setResumeOpen(false)
              setResumeEmail('')
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      {options.map((option) => (
        <button
          key={option.label}
          type="button"
          className={styles.chip}
          onClick={() => {
            if (option.action === 'focus_input') {
              onFocusInput?.(option.placeholder ?? 'Type your 10-digit CR number')
              return
            }
            if (option.action === 'resume_pending') {
              setResumeOpen(true)
              return
            }
            onSelect(option.text)
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

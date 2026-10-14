import { useState, type FormEvent, type KeyboardEvent } from 'react'
import styles from './Composer.module.css'

interface ComposerProps {
  disabled: boolean
  onSend: (text: string) => void
}

export function Composer({ disabled, onSend }: ComposerProps) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit()
  }

  return (
    <form className={styles.composer} onSubmit={onSubmit}>
      <textarea
        className={styles.input}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="Type a message…"
        disabled={disabled}
        rows={1}
        aria-label="Message"
      />
      <button
        type="submit"
        className={styles.send}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M5 12h12m0 0-5-5m5 5-5 5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
    </form>
  )
}

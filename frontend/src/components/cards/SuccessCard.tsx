import { useEffect, useState } from 'react'
import { API_BASE } from '../../config'
import type { SuccessPayload, SuccessStep } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './SuccessCard.module.css'

interface SuccessCardProps {
  payload: SuccessPayload
}

function stepMarkClass(state: SuccessStep['state']): string {
  if (state === 'done') return styles.stepDone
  if (state === 'current') return styles.stepCurrent
  return styles.stepUpcoming
}

function trackingHref(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/')) {
    if (typeof window !== 'undefined') return `${window.location.origin}${url}`
    return `${API_BASE}${url}`
  }
  return url
}

export function SuccessCard({ payload }: SuccessCardProps) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!copied) return
    const t = window.setTimeout(() => setCopied(false), 2000)
    return () => window.clearTimeout(t)
  }, [copied])

  const copyRef = async () => {
    try {
      await navigator.clipboard.writeText(payload.reference)
      setCopied(true)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="success-card">
      <div className={styles.head}>
        <div className={styles.iconTile} aria-hidden="true">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path
              d="M5 12l5 5L20 7"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <span className={styles.headline}>Your inquiry has been sent</span>
      </div>
      <div className={styles.refBox}>
        <div>
          <div className={styles.refLabel}>Reference number</div>
          <div className={styles.refValue}>{payload.reference}</div>
        </div>
        <button type="button" className={shared.secondaryBtn} onClick={() => void copyRef()}>
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <ol className={styles.timeline}>
        {payload.steps.map((step, index) => (
          <li key={step.label} className={styles.step}>
            <span className={stepMarkClass(step.state)} aria-hidden="true">
              {index + 1}
            </span>
            <span className={styles.stepBody}>
              <span className={styles.stepLabel}>{step.label}</span>
              <span className={styles.stepDetail}>{step.detail}</span>
            </span>
          </li>
        ))}
      </ol>
      <a className={styles.trackLink} href={trackingHref(payload.tracking_url)}>
        Track your inquiry
      </a>
    </div>
  )
}

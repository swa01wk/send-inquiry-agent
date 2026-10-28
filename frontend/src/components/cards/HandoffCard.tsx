import type { HandoffPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './HandoffCard.module.css'

interface HandoffCardProps {
  payload: HandoffPayload
}

function telHref(phone: string): string {
  const digits = phone.replace(/[^\d+]/g, '')
  return `tel:${digits}`
}

function mailHref(email: string): string {
  return `mailto:${email}`
}

export function HandoffCard({ payload }: HandoffCardProps) {
  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="handoff-card">
      <p className={styles.lead}>Our leasing team can call you back.</p>
      <div className={styles.contactRow}>
        <a className={styles.contactLink} href={telHref(payload.phone)}>
          {payload.phone}
        </a>
        <a className={styles.contactLink} href={mailHref(payload.email)}>
          {payload.email}
        </a>
      </div>
      <p className={styles.hours}>{payload.hours}</p>
      <p className={styles.ref}>Your reference: {payload.short_ref}</p>
      {payload.case_id ? <p className={styles.caseId}>Case {payload.case_id}</p> : null}
    </div>
  )
}

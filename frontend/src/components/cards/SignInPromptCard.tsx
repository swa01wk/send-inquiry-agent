import type { SignInPromptPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './SignInPromptCard.module.css'

interface SignInPromptCardProps {
  payload: SignInPromptPayload
  /** S4, M2: "I don't have a login" → the inquiry goes on as new. */
  onNoLogin?: () => void
}

export function SignInPromptCard({ payload, onNoLogin }: SignInPromptCardProps) {
  if (payload.continued_without_login) {
    return (
      <div className={`${shared.shellPad} ${styles.layout}`} data-testid="sign-in-prompt-card">
        <p className={styles.message}>{payload.message}</p>
        <p className={styles.continued} data-testid="continued-without-login">
          Continuing without a login: we&apos;ll raise your inquiry here.
        </p>
      </div>
    )
  }
  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="sign-in-prompt-card">
      <p className={styles.message}>{payload.message}</p>
      <a className={styles.signInBtn} href={payload.sign_in_url}>
        {payload.button_label}
      </a>
      {payload.no_login_label && onNoLogin ? (
        <button type="button" className={shared.secondaryBtn} onClick={onNoLogin}>
          {payload.no_login_label}
        </button>
      ) : null}
    </div>
  )
}

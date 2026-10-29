import type { SignInPromptPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './SignInPromptCard.module.css'

interface SignInPromptCardProps {
  payload: SignInPromptPayload
}

export function SignInPromptCard({ payload }: SignInPromptCardProps) {
  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="sign-in-prompt-card">
      <p className={styles.message}>{payload.message}</p>
      <a className={styles.signInBtn} href={payload.sign_in_url}>
        {payload.button_label}
      </a>
    </div>
  )
}

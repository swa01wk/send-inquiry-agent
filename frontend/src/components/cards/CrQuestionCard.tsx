import type { CrQuestionPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './CrQuestionCard.module.css'

interface CrQuestionCardProps {
  payload: CrQuestionPayload
  onAnswer: (hasCr: boolean) => void
}

export function CrQuestionCard({ payload, onAnswer }: CrQuestionCardProps) {
  const answered = payload.answered ?? null
  const chosenLabel =
    answered === 'yes' ? payload.yes_label : answered === 'no' ? payload.no_label : undefined

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="cr-question-card">
      <p className={styles.prompt}>{payload.prompt}</p>
      {answered && chosenLabel ? (
        <p className={styles.doneLine}>{chosenLabel}</p>
      ) : (
        <div className={styles.actions}>
          <button type="button" className={shared.primaryBtnFull} onClick={() => onAnswer(true)}>
            {payload.yes_label}
          </button>
          <button type="button" className={shared.primaryBtnFull} onClick={() => onAnswer(false)}>
            {payload.no_label}
          </button>
        </div>
      )}
    </div>
  )
}

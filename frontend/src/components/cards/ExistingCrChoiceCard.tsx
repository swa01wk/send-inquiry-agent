import type { ExistingCrChoicePayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './ExistingCrChoiceCard.module.css'

interface ExistingCrChoiceCardProps {
  payload: ExistingCrChoicePayload
  onChoose: (choice: 'sign_in' | 'continue') => void
}

export function ExistingCrChoiceCard({ payload, onChoose }: ExistingCrChoiceCardProps) {
  const chosen = payload.chosen ?? null
  const chosenLabel = chosen ? payload.options.find((o) => o.value === chosen)?.label : undefined

  const headline = payload.company_name
    ? `${payload.company_name} (CR ${payload.cr_number}) already has a Tenant Central account`
    : `(CR ${payload.cr_number}) already has a Tenant Central account`

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="existing-cr-choice-card">
      <p className={styles.headline}>{headline}</p>
      {chosen && chosenLabel ? (
        <p className={styles.doneLine}>{chosenLabel}</p>
      ) : (
        <div className={styles.actions}>
          {payload.options.map((option) => (
            <button
              key={option.value}
              type="button"
              className={shared.primaryBtnFull}
              onClick={() => onChoose(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

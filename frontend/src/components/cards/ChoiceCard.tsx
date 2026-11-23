import { useState } from 'react'
import type { ChoicePayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './ChoiceCard.module.css'

interface ChoiceCardProps {
  payload: ChoicePayload
  /** Sends `choose_option {card_id, key, value}`. */
  onChoose: (value: string) => void
}

/**
 * A value picked from a list (18 Nov B1 §3.2): the sales category today. Labels come from
 * master data in the chat's language; once one is picked the others are disabled.
 */
export function ChoiceCard({ payload, onChoose }: ChoiceCardProps) {
  const [picked, setPicked] = useState<string | null>(null)
  const arabic = payload.lang === 'ar'
  const chosen = payload.chosen ?? picked

  return (
    <div
      className={`${shared.shellPad} ${styles.layout}`}
      data-testid={`choice-card-${payload.key}`}
      dir={arabic ? 'rtl' : 'ltr'}
      lang={payload.lang}
    >
      <p className={styles.prompt} id={`choice-prompt-${payload.key}`}>
        {payload.prompt}
      </p>
      <div className={styles.options} role="group" aria-labelledby={`choice-prompt-${payload.key}`}>
        {payload.options.map((option) => {
          const label = arabic ? option.label_ar || option.label : option.label
          const isChosen = chosen === option.value
          return (
            <button
              key={option.value}
              type="button"
              data-testid={`choice-option-${option.value}`}
              className={`${isChosen ? shared.primaryBtn : shared.secondaryBtn} ${styles.option}`}
              aria-pressed={isChosen}
              disabled={chosen !== null}
              onClick={() => {
                setPicked(option.value)
                onChoose(option.value)
              }}
            >
              {isChosen ? (
                <span className={styles.tick} aria-hidden="true">
                  ✓{' '}
                </span>
              ) : null}
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}

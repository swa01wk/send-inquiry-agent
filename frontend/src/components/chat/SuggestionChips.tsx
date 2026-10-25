import type { QuickReplyOption } from '../../types/contracts'
import styles from './SuggestionChips.module.css'

interface SuggestionChipsProps {
  options: QuickReplyOption[]
  onSelect: (text: string) => void
  onFocusInput?: (placeholder: string) => void
  hidden: boolean
}

export function SuggestionChips({ options, onSelect, onFocusInput, hidden }: SuggestionChipsProps) {
  if (hidden || options.length === 0) return null

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
            onSelect(option.text)
          }}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

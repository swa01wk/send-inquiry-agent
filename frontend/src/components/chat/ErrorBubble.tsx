import styles from './ErrorBubble.module.css'

interface ErrorBubbleProps {
  message: string
  actionLabel: string
  onAction: () => void
}

export function ErrorBubble({ message, actionLabel, onAction }: ErrorBubbleProps) {
  return (
    <div className={styles.wrap} role="alert">
      <div className={styles.bubble}>
        <p className={styles.text}>{message}</p>
        <button type="button" className={styles.action} onClick={onAction}>
          {actionLabel}
        </button>
      </div>
    </div>
  )
}

import styles from './BotBubble.module.css'

interface BotBubbleProps {
  text: string
  showAvatar: boolean
}

export function BotBubble({ text, showAvatar }: BotBubbleProps) {
  return (
    <div className={styles.row}>
      {showAvatar ? (
        <div className={styles.avatar} aria-hidden="true" data-testid="bot-avatar">
          C
        </div>
      ) : (
        <div className={styles.avatarSpacer} aria-hidden="true" />
      )}
      <div className={styles.bubble} data-testid="bot-bubble-text">
        {text}
      </div>
    </div>
  )
}

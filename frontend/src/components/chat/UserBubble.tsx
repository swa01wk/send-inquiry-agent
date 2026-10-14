import styles from './UserBubble.module.css'

interface UserBubbleProps {
  text: string
}

export function UserBubble({ text }: UserBubbleProps) {
  return (
    <div className={styles.row}>
      <div className={styles.bubble}>{text}</div>
    </div>
  )
}

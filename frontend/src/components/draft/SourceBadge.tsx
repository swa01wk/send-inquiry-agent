import type { Source } from '../../types/contracts'
import styles from './SourceBadge.module.css'

interface SourceBadgeProps {
  source: Source | null
  confirmed: boolean
}

function badgeMeta(source: Source, confirmed: boolean): { text: string; variant: keyof typeof styles } {
  if (source === 'user') return { text: 'You said', variant: 'neutral' }
  if (source === 'verified') {
    return confirmed
      ? { text: 'From your CR', variant: 'success' }
      : { text: 'From CR · confirm', variant: 'pending' }
  }
  if (source === 'derived') {
    return confirmed
      ? { text: 'Suggested · confirmed', variant: 'derived' }
      : { text: 'Suggested · confirm', variant: 'pending' }
  }
  return { text: 'Default', variant: 'defaultVariant' }
}

export function SourceBadge({ source, confirmed }: SourceBadgeProps) {
  if (!source) return null
  const { text, variant } = badgeMeta(source, confirmed)
  return (
    <span className={`${styles.badge} ${styles[variant]}`} data-testid="source-badge">
      {text}
    </span>
  )
}

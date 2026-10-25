import type { ReactNode } from 'react'
import styles from './BotBubble.module.css'

function renderInline(text: string): ReactNode[] {
  const parts = text.split(/\*\*(.+?)\*\*/g)
  return parts.map((part, index) =>
    index % 2 === 1 ? (
      <strong key={`b-${index}`}>{part}</strong>
    ) : (
      <span key={`t-${index}`}>{part}</span>
    ),
  )
}

function renderParagraph(text: string, key: string): ReactNode {
  const lines = text.split('\n')
  const bulletLines = lines.filter((line) => line.trim().startsWith('- '))
  const allBullets =
    bulletLines.length > 0 && bulletLines.length === lines.filter((l) => l.trim()).length

  if (allBullets) {
    return (
      <ul key={key} className={styles.list}>
        {lines
          .filter((line) => line.trim())
          .map((line, i) => (
            <li key={`${key}-${i}`}>{renderInline(line.replace(/^\s*-\s*/, ''))}</li>
          ))}
      </ul>
    )
  }

  return (
    <p key={key} className={styles.paragraph}>
      {renderInline(text)}
    </p>
  )
}

/** Safe subset: paragraphs, line breaks, `-` bullets, `**bold**`. No HTML. */
export function BotMessageContent({ text }: { text: string }) {
  const blocks = text.split(/\n\n+/).filter((block) => block.trim().length > 0)
  if (blocks.length === 0) return null
  return <>{blocks.map((block, index) => renderParagraph(block, `p-${index}`))}</>
}

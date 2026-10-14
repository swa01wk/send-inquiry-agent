import type { DraftFieldRow } from '../../types/contracts'
import { DraftRow } from './DraftRow'
import styles from './DraftGroup.module.css'

interface DraftGroupProps {
  title: string
  fields: DraftFieldRow[]
  flashKeys: Set<string>
}

export function DraftGroup({ title, fields, flashKeys }: DraftGroupProps) {
  if (fields.length === 0) return null
  return (
    <section className={styles.group} aria-label={title}>
      <h3 className={styles.title}>{title}</h3>
      {fields.map((field) => (
        <DraftRow key={field.key} field={field} flash={flashKeys.has(field.key)} />
      ))}
    </section>
  )
}

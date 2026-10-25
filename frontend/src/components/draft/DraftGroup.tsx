import type { DraftFieldRow } from '../../types/contracts'
import { type DraftGroupId, fieldsForDraftGroup } from './draftGroups'
import { DraftRow } from './DraftRow'
import styles from './DraftGroup.module.css'

interface DraftGroupProps {
  groupId: DraftGroupId
  title: string
  fields: DraftFieldRow[]
  flashKeys: Set<string>
}

export function DraftGroup({ groupId, title, fields, flashKeys }: DraftGroupProps) {
  const rows = fieldsForDraftGroup(groupId, fields)
  if (rows.length === 0) return null
  return (
    <section className={styles.group} aria-label={title}>
      <h3 className={styles.title}>{title}</h3>
      {rows.map((field) => (
        <DraftRow
          key={field.key}
          field={field}
          flash={flashKeys.has(field.key) || (field.key === 'phone' && flashKeys.has('mobile'))}
          phoneKind={field.phoneKind}
        />
      ))}
    </section>
  )
}

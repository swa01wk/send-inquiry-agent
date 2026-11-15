import type { BriefContact } from '../api/review'
import styles from './review.module.css'

/** The tenant's contacts, read-only: contacts aren't approved one by one (flow v2 V7, M15);
 * the final reviewer sees them inside "Approve Lead". */
export function ContactList({ contacts }: { contacts: BriefContact[] }) {
  return (
    <ul className={styles.decisionList} data-testid="contact-list">
      {contacts.map((contact) => (
        <li
          key={`${contact.role}-${contact.contact_id ?? ''}`}
          className={styles.decisionRow}
          data-testid={`contact-row-${contact.role}`}
        >
          {contact.label}: {contact.name ?? '—'}, {contact.email ?? '—'}, {contact.phone ?? '—'}
          {contact.same_as_primary ? ' (primary contact)' : ''}
        </li>
      ))}
    </ul>
  )
}

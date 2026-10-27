import { useCallback, useEffect, useState } from 'react'
import { clearOutbox, fetchOutbox } from '../api/client'
import { PageShell } from '../components/layout/PageShell'
import type { OutboxMessage } from '../types/contracts'
import styles from './devInbox.module.css'

export function DevInboxPage() {
  const [filter, setFilter] = useState('')
  const [messages, setMessages] = useState<OutboxMessage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (to?: string) => {
    setLoading(true)
    setError(null)
    try {
      const rows = await fetchOutbox(to?.trim() || undefined)
      setMessages(rows)
    } catch (err) {
      setMessages([])
      setError(err instanceof Error ? err.message : 'Could not load the outbox.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(filter)
  }, [filter, load])

  const onClear = async () => {
    await clearOutbox()
    await load(filter)
  }

  return (
    <PageShell
      title="Dev inbox"
      intro="Simulated emails and SMS from the POC (newest first)."
      showPanels={false}
    >
      <div className={styles.wrap} data-testid="dev-inbox-page">
        <div className={styles.toolbar}>
          <label className={styles.filterLabel}>
            Recipient
            <input
              className={styles.filterInput}
              type="search"
              placeholder="Filter by email or phone"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </label>
          <button type="button" className={styles.clearBtn} onClick={() => void onClear()}>
            Clear
          </button>
        </div>
        {loading ? <p className={styles.muted}>Loading…</p> : null}
        {error ? <p className={styles.error}>{error}</p> : null}
        {!loading && !error && messages.length === 0 ? (
          <p className={styles.muted}>No messages yet.</p>
        ) : null}
        <ul className={styles.list}>
          {messages.map((msg) => (
            <li key={msg.id} className={styles.item}>
              <div className={styles.meta}>
                <span className={styles.badge}>{msg.channel}</span>
                <span className={styles.template}>{msg.template}</span>
                <span className={styles.to}>{msg.to}</span>
                <time className={styles.time} dateTime={msg.created_at}>
                  {new Date(msg.created_at).toLocaleString()}
                </time>
              </div>
              {msg.subject ? <div className={styles.subject}>{msg.subject}</div> : null}
              <pre className={styles.body}>{msg.body}</pre>
              {msg.links.length > 0 ? (
                <ul className={styles.links}>
                  {msg.links.map((href) => (
                    <li key={href}>
                      <a href={href} className={styles.link}>
                        {href}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </PageShell>
  )
}

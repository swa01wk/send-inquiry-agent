import { useEffect, useState } from 'react'
import type { MallPickerPayload } from '../../types/contracts'
import shared from './cards.module.css'
import styles from './MallPickerCard.module.css'

interface MallPickerCardProps {
  payload: MallPickerPayload
  locked: boolean
  onDone: (mallIds: string[]) => void
}

export function MallPickerCard({ payload, locked, onDone }: MallPickerCardProps) {
  const [selected, setSelected] = useState<string[]>(payload.selected)

  useEffect(() => {
    setSelected(payload.selected)
  }, [payload.selected])

  const countLabel =
    selected.length === 0 ? 'Select one or more' : `${selected.length} selected`

  const toggle = (id: string) => {
    if (locked) return
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  return (
    <div className={`${shared.shellPad} ${styles.layout}`} data-testid="mall-picker-card">
      <div className={styles.header}>
        <span className={styles.title}>Malls in {payload.city.label}</span>
        <span className={styles.count}>{countLabel}</span>
      </div>
      <div className={styles.grid}>
        {payload.malls.map((mall) => {
          const pressed = selected.includes(mall.id)
          return (
            <button
              key={mall.id}
              type="button"
              className={pressed ? styles.tileSelected : styles.tile}
              aria-pressed={pressed}
              disabled={locked}
              onClick={() => toggle(mall.id)}
            >
              <span className={styles.tileName}>{mall.name}</span>
              <span className={pressed ? styles.markSelected : styles.mark} aria-hidden="true">
                {pressed ? '✓' : '+'}
              </span>
            </button>
          )
        })}
      </div>
      {!locked ? (
        <button
          type="button"
          className={shared.primaryBtnFull}
          disabled={selected.length < payload.min_select}
          onClick={() => onDone(selected)}
        >
          Done
        </button>
      ) : null}
    </div>
  )
}

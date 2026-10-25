import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { draftMidway } from '../../mocks/fixtures'
import { DraftPanelView } from './DraftPanel'
import styles from './DraftRow.module.css'

describe('DraftPanelView', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders field values and badges from fixture', () => {
    render(<DraftPanelView draft={{ ...draftMidway, changed_keys: [] }} />)
    expect(screen.getByText('Bean Street Trading Co.')).toBeInTheDocument()
    expect(screen.getAllByText('From CR · confirm').length).toBeGreaterThan(0)
    expect(screen.getByTestId('draft-progress-count')).toHaveTextContent('4 of 11')
  })

  it('matches progress bar width to required_filled ratio', () => {
    render(<DraftPanelView draft={{ ...draftMidway, changed_keys: [] }} />)
    const fill = screen.getByTestId('draft-progress-fill')
    expect(fill).toHaveStyle({ width: `${(4 / 11) * 100}%` })
  })

  it('flashes changed rows then clears after 1.8s', () => {
    render(<DraftPanelView draft={{ ...draftMidway, changed_keys: ['company_name'] }} />)
    const row = screen.getByTestId('draft-row-company_name')
    expect(row.className).toContain(styles.flash)
    act(() => {
      vi.advanceTimersByTime(1800)
    })
    expect(row.className).not.toContain(styles.flash)
  })

  it('scrolls the body to the first changed row offset', () => {
    const { rerender } = render(<DraftPanelView draft={{ ...draftMidway, changed_keys: [] }} />)
    const body = screen.getByTestId('draft-scroll-body')
    const scrollTo = vi.fn()
    body.scrollTo = scrollTo
    const row = document.getElementById('draft-company_name') as HTMLElement
    Object.defineProperty(row, 'offsetTop', { value: 200, configurable: true })

    rerender(<DraftPanelView draft={{ ...draftMidway, changed_keys: ['company_name'] }} />)

    expect(scrollTo).toHaveBeenCalledWith({ top: 188, behavior: 'smooth' })
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { draftEmpty, draftMidway } from '../../mocks/fixtures'
import { ProgressStages } from './ProgressStages'

describe('ProgressStages', () => {
  it('marks gate phase with Company current', () => {
    render(<ProgressStages phase="gate" draft={draftEmpty} />)
    expect(screen.getByTestId('stage-company')).toHaveAttribute('data-state', 'current')
    expect(screen.getByTestId('stage-brand')).toHaveAttribute('data-state', 'upcoming')
  })

  it('marks submitted phase with all stages done', () => {
    render(<ProgressStages phase="submitted" draft={draftMidway} />)
    for (const key of ['company', 'brand', 'space', 'contact', 'documents', 'review']) {
      expect(screen.getByTestId(`stage-${key}`)).toHaveAttribute('data-state', 'done')
    }
  })

  it('derives collecting stage from first missing group', () => {
    render(<ProgressStages phase="collecting" draft={draftMidway} />)
    expect(screen.getByTestId('stage-company')).toHaveAttribute('data-state', 'done')
    expect(screen.getByTestId('stage-space')).toHaveAttribute('data-state', 'current')
  })
})

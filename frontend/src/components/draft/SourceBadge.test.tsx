import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SourceBadge } from './SourceBadge'

describe('SourceBadge', () => {
  it('renders user source', () => {
    render(<SourceBadge source="user" confirmed />)
    expect(screen.getByText('You said')).toBeInTheDocument()
  })

  it('renders verified unconfirmed', () => {
    render(<SourceBadge source="verified" confirmed={false} />)
    expect(screen.getByText('From CR · confirm')).toBeInTheDocument()
  })

  it('renders derived confirmed', () => {
    render(<SourceBadge source="derived" confirmed />)
    expect(screen.getByText('Suggested · confirmed')).toBeInTheDocument()
  })
})

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BotMessageContent } from './botMessageContent'

describe('BotMessageContent', () => {
  it('renders paragraph and bullet list', () => {
    render(<BotMessageContent text={'Line one\n\n- a\n- b'} />)
    expect(screen.getByText('Line one')).toBeInTheDocument()
    expect(screen.getByText('a')).toBeInTheDocument()
    expect(screen.getByText('b')).toBeInTheDocument()
  })

  it('renders script tags as plain text', () => {
    render(<BotMessageContent text="<script>alert(1)</script>" />)
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument()
  })
})

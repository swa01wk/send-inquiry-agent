import { renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useResendCountdown } from './useResendCountdown'

describe('useResendCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-28T12:00:00.000Z'))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('allows resend when no throttle time is set', () => {
    const { result } = renderHook(() => useResendCountdown(null))
    expect(result.current.throttled).toBe(false)
    expect(result.current.waitLabel).toBeNull()
  })

  it('counts down until resend is available', () => {
    const until = '2026-10-28T12:00:45.000Z'
    const { result } = renderHook(() => useResendCountdown(until))
    expect(result.current.throttled).toBe(true)
    expect(result.current.waitLabel).toBe('45s')

    act(() => {
      vi.advanceTimersByTime(30_000)
    })
    expect(result.current.waitLabel).toBe('15s')

    act(() => {
      vi.advanceTimersByTime(20_000)
    })
    expect(result.current.throttled).toBe(false)
  })
})

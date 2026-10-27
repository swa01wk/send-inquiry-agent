import { useEffect, useState } from 'react'

function secondsUntil(iso: string): number {
  const target = Date.parse(iso)
  if (Number.isNaN(target)) return 0
  return Math.max(0, Math.ceil((target - Date.now()) / 1000))
}

function formatWait(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m > 0) return `${m}:${String(s).padStart(2, '0')}`
  return `${s}s`
}

/** Resend is blocked until `resend_available_at` (ISO) passes. */
export function useResendCountdown(resendAvailableAt: string | null | undefined): {
  throttled: boolean
  waitLabel: string | null
} {
  const [secondsLeft, setSecondsLeft] = useState(() =>
    resendAvailableAt ? secondsUntil(resendAvailableAt) : 0,
  )

  useEffect(() => {
    if (!resendAvailableAt) {
      setSecondsLeft(0)
      return
    }
    const tick = () => setSecondsLeft(secondsUntil(resendAvailableAt))
    tick()
    const id = window.setInterval(tick, 1000)
    return () => window.clearInterval(id)
  }, [resendAvailableAt])

  if (!resendAvailableAt || secondsLeft <= 0) {
    return { throttled: false, waitLabel: null }
  }
  return { throttled: true, waitLabel: formatWait(secondsLeft) }
}

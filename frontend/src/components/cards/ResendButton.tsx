import { useResendCountdown } from '../../hooks/useResendCountdown'
import shared from './cards.module.css'

interface ResendButtonProps {
  label: string
  resendAvailableAt: string | null | undefined
  onResend: () => void
}

export function ResendButton({ label, resendAvailableAt, onResend }: ResendButtonProps) {
  const { throttled, waitLabel } = useResendCountdown(resendAvailableAt)

  if (throttled && waitLabel) {
    return (
      <span className={shared.caption} aria-live="polite">
        {label} in {waitLabel}
      </span>
    )
  }

  return (
    <button type="button" className={shared.textLink} onClick={onResend}>
      {label}
    </button>
  )
}

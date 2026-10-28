import { useCallback, useState } from 'react'

const KEY = 'cenomi.reviewerId'

function read(): string | null {
  try {
    return window.sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

/** The mock sign-in (L4 §3.3): which reviewer this browser tab acts as. */
export function useReviewerId(): [string | null, (id: string | null) => void] {
  const [reviewerId, setState] = useState<string | null>(() => read())
  const set = useCallback((id: string | null) => {
    try {
      if (id) window.sessionStorage.setItem(KEY, id)
      else window.sessionStorage.removeItem(KEY)
    } catch {
      /* private mode: keep it in memory only */
    }
    setState(id)
  }, [])
  return [reviewerId, set]
}

export const ROLE_LABELS: Record<string, string> = {
  rlm_store: 'Regional Leasing Manager (Store)',
  rplm_media: 'Regional Property Leasing Manager (Media)',
  rplm_specialty: 'Regional Property Leasing Manager (Specialty)',
}

export function regionLabel(region: string | null): string {
  if (!region) return '—'
  return region.charAt(0).toUpperCase() + region.slice(1)
}

export function waitingOnLabel(waitingOn: string): string {
  if (waitingOn === 'reviewer') return 'You'
  if (waitingOn === 'applicant') return 'Applicant'
  if (waitingOn === 'system') return 'System'
  return '—'
}

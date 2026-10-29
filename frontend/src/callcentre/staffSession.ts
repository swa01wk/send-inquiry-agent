import { useCallback, useState } from 'react'

const KEY = 'cenomi.staffId'

function read(): string | null {
  try {
    return window.sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

/** Mock sign-in (spec §15): which call-centre staff member this browser tab acts as. */
export function useStaffId(): [string | null, (id: string | null) => void] {
  const [staffId, setState] = useState<string | null>(() => read())
  const set = useCallback((id: string | null) => {
    try {
      if (id) window.sessionStorage.setItem(KEY, id)
      else window.sessionStorage.removeItem(KEY)
    } catch {
      /* private mode: keep it in memory only */
    }
    setState(id)
  }, [])
  return [staffId, set]
}

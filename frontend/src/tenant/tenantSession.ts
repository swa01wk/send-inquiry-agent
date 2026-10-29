import { useCallback, useState } from 'react'

const KEY = 'cenomi.tenantId'

function read(): string | null {
  try {
    return window.sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

/** The mock Tenant Central sign-in (assumption D3): which tenant this tab acts as. */
export function useTenantId(): [string | null, (id: string | null) => void] {
  const [tenantId, setState] = useState<string | null>(() => read())
  const set = useCallback((id: string | null) => {
    try {
      if (id) window.sessionStorage.setItem(KEY, id)
      else window.sessionStorage.removeItem(KEY)
    } catch {
      /* private mode: keep it in memory only */
    }
    setState(id)
  }, [])
  return [tenantId, set]
}

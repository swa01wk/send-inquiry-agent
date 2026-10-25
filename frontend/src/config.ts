const DEFAULT_API_BASE = 'http://localhost:8000'

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? DEFAULT_API_BASE

export const MOCK_MODE = import.meta.env.VITE_MOCK === '1'

export const DEMO_MODE = import.meta.env.VITE_DEMO === '1'

export const E2E_MODE = import.meta.env.VITE_E2E === '1'

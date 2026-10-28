const DEFAULT_API_BASE = 'http://localhost:8000'

export const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? DEFAULT_API_BASE

export const MOCK_MODE = import.meta.env.VITE_MOCK === '1'

export const DEMO_MODE = import.meta.env.VITE_DEMO === '1'

export const E2E_MODE = import.meta.env.VITE_E2E === '1'

/** Dev inbox route and `/api/dev/*` (must match backend DEV_TOOLS). */
export const DEV_TOOLS = import.meta.env.VITE_DEV_TOOLS === '1'

/** Reviewer console routes (must match backend REVIEWER_CONSOLE). */
export const REVIEWER_CONSOLE = import.meta.env.VITE_REVIEWER_CONSOLE === '1'

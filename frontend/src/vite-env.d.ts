/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_MOCK?: string
  readonly VITE_DEMO?: string
  readonly VITE_E2E?: string
  readonly VITE_DEV_TOOLS?: string
  readonly VITE_REVIEWER_CONSOLE?: string
  readonly VITE_CALLCENTRE_CONSOLE?: string
  readonly VITE_TENANT_PORTAL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

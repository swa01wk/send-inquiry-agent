/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_MOCK?: string
  readonly VITE_DEMO?: string
  readonly VITE_E2E?: string
  readonly VITE_DEV_TOOLS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

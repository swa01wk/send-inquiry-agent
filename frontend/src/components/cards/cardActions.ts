export interface ChatCardActions {
  sendAction: (action: string, payload: Record<string, unknown>) => void
  uploadDocument: (docType: string, file: File) => Promise<void>
  removeDocument: (docType: string) => Promise<void>
  mallsConfirmed: boolean
}

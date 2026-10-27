export interface ChatCardActions {
  sendAction: (action: string, payload: Record<string, unknown>) => void
  editReviewField: (key: string, value: string) => Promise<boolean>
  uploadDocument: (docType: string, file: File) => Promise<void>
  removeDocument: (docType: string) => Promise<void>
  setDocumentNumber: (key: string, value: string) => void
  mallsConfirmed: boolean
}

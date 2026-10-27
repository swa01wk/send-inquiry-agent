import { useRef, useState } from 'react'
import type { DocumentNumberRow, DocumentUploadPayload } from '../../types/contracts'
import shared from './cards.module.css'
import { formatFileSize, validateDocumentFile } from './documentFileCheck'
import styles from './DocumentChecklistCard.module.css'

interface DocumentChecklistCardProps {
  payload: DocumentUploadPayload
  onUpload: (docType: string, file: File) => Promise<void>
  onRemove: (docType: string) => Promise<void>
  onSetNumber: (key: string, value: string) => void
}

const FOOTER_COPY =
  'PDF, JPG, PNG, DOC, XLSX, ZIP · up to 5 MB each · we only check that files are uploaded'

const NUMBER_BY_DOC: Record<string, string> = {
  cr_certificate: 'cr_number',
  vat_certificate: 'vat_number',
  national_id: 'national_id_number',
  national_address: 'national_address',
}

function numberForDoc(
  docType: string,
  numbers: DocumentNumberRow[] | undefined,
): DocumentNumberRow | undefined {
  const key = NUMBER_BY_DOC[docType]
  if (!key || !numbers) return undefined
  return numbers.find((row) => row.key === key)
}

export function DocumentChecklistCard({
  payload,
  onUpload,
  onRemove,
  onSetNumber,
}: DocumentChecklistCardProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const pendingTypeRef = useRef<string | null>(null)
  const [uploadingType, setUploadingType] = useState<string | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({})
  const [numberDrafts, setNumberDrafts] = useState<Record<string, string>>({})

  const numbers = payload.numbers ?? []

  const openPicker = (docType: string) => {
    pendingTypeRef.current = docType
    setRowErrors((e) => {
      const next = { ...e }
      delete next[docType]
      return next
    })
    inputRef.current?.click()
  }

  const onFileChange = async (file: File | undefined) => {
    const docType = pendingTypeRef.current
    pendingTypeRef.current = null
    if (!docType || !file) return

    const err = validateDocumentFile(file, payload.allowed_extensions, payload.max_mb)
    if (err) {
      setRowErrors((e) => ({ ...e, [docType]: err }))
      return
    }

    setUploadingType(docType)
    try {
      await onUpload(docType, file)
    } finally {
      setUploadingType(null)
    }
  }

  const accept = payload.allowed_extensions.join(',')

  const displayValue = (row: DocumentNumberRow) => numberDrafts[row.key] ?? row.value ?? ''

  return (
    <div className={`${shared.shell} ${styles.shell}`} data-testid="document-checklist-card">
      <div className={styles.header}>
        <span className={styles.title}>Documents</span>
        <span className={shared.caption}>
          {payload.required_uploaded} of {payload.required_total} required uploaded
        </span>
      </div>
      <input
        ref={inputRef}
        className={styles.hiddenInput}
        type="file"
        accept={accept}
        onChange={(e) => {
          const f = e.target.files?.[0]
          e.target.value = ''
          void onFileChange(f)
        }}
      />
      {payload.docs.map((doc) => {
        const uploading = uploadingType === doc.doc_type
        const numberRow = numberForDoc(doc.doc_type, numbers)
        return (
          <div key={doc.doc_type} className={styles.row}>
            <div className={styles.info}>
              <div className={styles.labelRow}>
                <span className={styles.docLabel}>{doc.label}</span>
                <span className={doc.required ? styles.tagRequired : styles.tagOptional}>
                  {doc.required ? 'Required' : 'Optional'}
                </span>
              </div>
              <span className={doc.uploaded ? styles.statusOk : styles.statusMuted}>
                {doc.uploaded && doc.file_name
                  ? `Uploaded · ${doc.file_name}${doc.size_bytes != null ? ` · ${formatFileSize(doc.size_bytes)}` : ''}`
                  : 'Not uploaded'}
              </span>
              {numberRow ? (
                <label className={styles.numberField}>
                  <span className={shared.caption}>{numberRow.label}</span>
                  <input
                    className={styles.numberInput}
                    type="text"
                    readOnly={!numberRow.editable}
                    value={displayValue(numberRow)}
                    aria-label={numberRow.label}
                    data-testid={`doc-number-${numberRow.key}`}
                    onChange={(e) => {
                      if (!numberRow.editable) return
                      setNumberDrafts((d) => ({ ...d, [numberRow.key]: e.target.value }))
                    }}
                    onBlur={() => {
                      if (!numberRow.editable) return
                      const value = displayValue(numberRow).trim()
                      if (value && value !== (numberRow.value ?? '')) {
                        onSetNumber(numberRow.key, value)
                      }
                    }}
                  />
                </label>
              ) : null}
              {rowErrors[doc.doc_type] ? (
                <span className={shared.captionError}>{rowErrors[doc.doc_type]}</span>
              ) : null}
            </div>
            <div className={styles.actionWrap}>
              {uploading ? (
                <span className={styles.spinner} aria-label="Uploading" />
              ) : doc.uploaded ? (
                <button
                  type="button"
                  className={shared.secondaryBtn}
                  onClick={() => void onRemove(doc.doc_type)}
                >
                  Remove
                </button>
              ) : (
                <button
                  type="button"
                  className={shared.brandBtn}
                  onClick={() => openPicker(doc.doc_type)}
                >
                  Upload
                </button>
              )}
            </div>
          </div>
        )
      })}
      <p className={styles.footer}>{FOOTER_COPY}</p>
    </div>
  )
}

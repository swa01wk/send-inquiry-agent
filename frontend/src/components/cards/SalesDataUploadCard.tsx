import { useRef, useState } from 'react'
import type { SalesDataPayload } from '../../types/contracts'
import shared from './cards.module.css'
import { formatFileSize, validateDocumentFile } from './documentFileCheck'
import styles from './SalesDataUploadCard.module.css'

const DOC_TYPE = 'sales_data'

interface SalesDataUploadCardProps {
  payload: SalesDataPayload
  onUpload: (docType: string, file: File) => Promise<void>
  onRemove: (docType: string) => Promise<void>
  onSubmit: () => void
}

export function SalesDataUploadCard({
  payload,
  onUpload,
  onRemove,
  onSubmit,
}: SalesDataUploadCardProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const openPicker = () => {
    setError(null)
    inputRef.current?.click()
  }

  const onFileChange = async (file: File | undefined) => {
    if (!file) return
    const err = validateDocumentFile(file, payload.allowed_extensions, payload.max_mb)
    if (err) {
      setError(err)
      return
    }
    setUploading(true)
    try {
      await onUpload(DOC_TYPE, file)
    } finally {
      setUploading(false)
    }
  }

  const accept = payload.allowed_extensions.join(',')
  const extHint = payload.allowed_extensions
    .map((e) => e.replace(/^\./, '').toUpperCase())
    .join(', ')

  return (
    <div className={`${shared.shell} ${styles.shell}`} data-testid="sales-data-upload-card">
      <div className={styles.header}>
        <span className={styles.title}>Estimated sales data</span>
        {payload.remarks ? <p className={styles.remarks}>{payload.remarks}</p> : null}
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
      <div className={styles.row}>
        <div className={styles.info}>
          <span className={payload.uploaded ? styles.statusOk : styles.statusMuted}>
            {payload.uploaded && payload.file_name
              ? `Uploaded · ${payload.file_name}${payload.size_bytes != null ? ` · ${formatFileSize(payload.size_bytes)}` : ''}`
              : 'Upload one file with your estimated sales figures'}
          </span>
          {error ? <span className={shared.captionError}>{error}</span> : null}
        </div>
        <div className={styles.actionWrap}>
          {uploading ? (
            <span className={styles.spinner} aria-label="Uploading" />
          ) : payload.uploaded ? (
            <button
              type="button"
              className={shared.secondaryBtn}
              onClick={() => void onRemove(DOC_TYPE)}
            >
              Remove
            </button>
          ) : (
            <button type="button" className={shared.brandBtn} onClick={openPicker}>
              Upload
            </button>
          )}
        </div>
      </div>
      <p className={styles.footer}>
        {extHint} · up to {payload.max_mb} MB · we only check that a file is uploaded
      </p>
      <div className={styles.footerActions}>
        <button
          type="button"
          className={shared.primaryBtnFull}
          disabled={!payload.uploaded}
          onClick={onSubmit}
        >
          Send
        </button>
      </div>
    </div>
  )
}

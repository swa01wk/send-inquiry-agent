export function fileExtension(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

function normaliseExtension(ext: string): string {
  const lower = ext.toLowerCase()
  if (!lower) return ''
  return lower.startsWith('.') ? lower : `.${lower}`
}

export function validateDocumentFile(
  file: File,
  allowedExtensions: string[],
  maxMb: number,
): string | null {
  const ext = fileExtension(file.name)
  const allowed = new Set(allowedExtensions.map(normaliseExtension))
  if (!allowed.has(ext)) {
    return "That file type isn't supported."
  }
  if (file.size > maxMb * 1024 * 1024) {
    return `That file is over ${maxMb} MB.`
  }
  return null
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

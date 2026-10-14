import { describe, expect, it } from 'vitest'
import { validateDocumentFile } from './documentFileCheck'

function file(name: string, sizeBytes: number): File {
  return new File([new Uint8Array(sizeBytes)], name, { type: 'application/octet-stream' })
}

describe('validateDocumentFile', () => {
  it('accepts PDF with dotted or undotted allow lists', () => {
    const pdf = file('Company_Profile.PDF', 1000)
    expect(validateDocumentFile(pdf, ['pdf'], 5)).toBeNull()
    expect(validateDocumentFile(pdf, ['.pdf'], 5)).toBeNull()
  })

  it('rejects unsupported types', () => {
    const txt = file('notes.txt', 100)
    expect(validateDocumentFile(txt, ['.pdf'], 5)).toBe("That file type isn't supported.")
  })

  it('rejects files over max size', () => {
    const big = file('big.pdf', 6 * 1024 * 1024)
    expect(validateDocumentFile(big, ['.pdf'], 5)).toBe('That file is over 5 MB.')
  })
})

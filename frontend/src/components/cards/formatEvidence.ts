/** Document-derived evidence: `"<label>: <file>, uploaded <time>"` (demo feedback §3.7). */
const DOCUMENT_EVIDENCE_RE = /^([^:]+):\s*([^,]+),\s*uploaded\s+(.+)$/

export type FormattedEvidence =
  | { kind: 'chat'; text: string }
  | { kind: 'document'; label: string; fileName: string; uploadedAt?: string }

export function parseEvidence(evidence: string): FormattedEvidence {
  const match = DOCUMENT_EVIDENCE_RE.exec(evidence.trim())
  if (!match) return { kind: 'chat', text: evidence }
  return {
    kind: 'document',
    label: match[1].trim(),
    fileName: match[2].trim(),
    uploadedAt: match[3].trim(),
  }
}

import type { DraftChecks } from '../../types/contracts'

export interface DraftCheckRow {
  ok: boolean
  label: string
}

/** Check labels for the draft panel (terms from server draft only). */
export function draftCheckRows(checks: DraftChecks): DraftCheckRow[] {
  const unconfirmed = checks.unconfirmed
  const suggestedOk = unconfirmed === 0 && checks.required_filled >= checks.required_total
  return [
    {
      ok: suggestedOk,
      label:
        unconfirmed > 0
          ? `${unconfirmed} suggested value${unconfirmed === 1 ? '' : 's'} to confirm`
          : 'All suggested values confirmed',
    },
    {
      ok: checks.contact_verified,
      label: checks.contact_verified ? 'Contact verified' : 'Contact not verified yet',
    },
    {
      ok: checks.required_docs_uploaded >= checks.required_docs_total,
      label: `${checks.required_docs_uploaded} of ${checks.required_docs_total} required documents uploaded`,
    },
    {
      ok: checks.terms_accepted,
      label: checks.terms_accepted ? 'Terms accepted' : 'Terms not accepted yet',
    },
  ]
}

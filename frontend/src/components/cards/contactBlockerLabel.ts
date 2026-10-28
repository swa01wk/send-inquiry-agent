/** Plain-language labels for `contacts_blockers` codes from the API. */
export function contactBlockerLabel(code: string, roleLabel?: string): string {
  const [kind, role = ''] = code.split(':')
  const label = roleLabel ?? role.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
  if (kind === 'missing_contact') return `${label} is missing`
  if (kind === 'incomplete_contact') return `${label} is incomplete`
  if (kind === 'unconfirmed_contact') return `${label} needs confirmation`
  return code
}

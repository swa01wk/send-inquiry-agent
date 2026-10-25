export function submitBlockerHint(blockers: string[], consentChecked: boolean): string {
  if (blockers.length === 0) return ''

  const missingFields = blockers.filter((b) => b.startsWith('missing_field:'))
  if (missingFields.length > 0) {
    const n = missingFields.length
    return `${n} required field${n === 1 ? '' : 's'} still missing.`
  }

  const first = blockers[0]
  if (first === 'terms_not_accepted' && !consentChecked) {
    return 'Accept the terms to submit.'
  }
  if (first === 'email_not_verified') return 'Verify your email with the link we sent to submit.'
  if (first === 'mobile_not_verified') return 'Verify your mobile with the SMS code to submit.'
  if (first.startsWith('unconfirmed_field:')) return 'Confirm suggested values to submit.'
  if (first.startsWith('missing_document:')) return 'Upload required documents to submit.'
  if (first === 'cr_existing') return 'This CR number already has an account.'
  if (first === 'cr_pending') return 'Complete CR verification to submit.'
  if (first === 'terms_not_accepted') return 'Accept the terms to submit.'
  return 'Complete the remaining steps to submit.'
}

export function canSubmitWithConsent(blockers: string[], consentChecked: boolean): boolean {
  return consentChecked && blockers.length === 1 && blockers[0] === 'terms_not_accepted'
}

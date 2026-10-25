import { describe, expect, it } from 'vitest'
import { canSubmitWithConsent } from './blockerHint'

describe('canSubmitWithConsent', () => {
  it('allows submit only when terms are the sole blocker and consent is checked', () => {
    expect(canSubmitWithConsent(['terms_not_accepted'], true)).toBe(true)
    expect(canSubmitWithConsent(['terms_not_accepted'], false)).toBe(false)
    expect(canSubmitWithConsent(['terms_not_accepted', 'email_not_verified'], true)).toBe(false)
  })
})

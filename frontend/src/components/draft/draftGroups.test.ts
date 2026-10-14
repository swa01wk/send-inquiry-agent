import { describe, expect, it } from 'vitest'
import { draftMidway } from '../../mocks/fixtures'
import { contactReviewRows, fieldsForDraftGroup, firstChangedKeyInPanelOrder } from './draftGroups'

describe('contactFieldsForPanel', () => {
  it('shows one phone row with mobile hint', () => {
    const rows = fieldsForDraftGroup('contact', [
      {
        key: 'mobile',
        label: 'Mobile',
        group: 'contact',
        display: '+966501234567',
        source: 'user',
        confirmed: true,
        required: true,
      },
      {
        key: 'landline',
        label: 'Office landline',
        group: 'contact',
        display: null,
        source: null,
        confirmed: false,
        required: false,
      },
    ])
    expect(rows.map((r) => r.key)).toEqual(['phone'])
    expect(rows[0].phoneKind).toBe('Mobile')
    expect(rows[0].label).toBe('Phone')
  })
})

describe('contactReviewRows', () => {
  it('merges mobile and landline into phone', () => {
    const rows = contactReviewRows([
      {
        key: 'mobile',
        label: 'Mobile',
        display: '+966501234567',
        source: 'user',
        confirmed: true,
        required: true,
      },
      {
        key: 'landline',
        label: 'Office landline',
        display: null,
        source: null,
        confirmed: false,
        required: false,
      },
    ])
    expect(rows.map((r) => r.key)).toEqual(['phone'])
    expect(rows[0].label).toBe('Phone')
  })
})

describe('firstChangedKeyInPanelOrder', () => {
  it('returns the first changed key in group order', () => {
    const key = firstChangedKeyInPanelOrder(draftMidway.fields, [
      'email',
      'company_name',
      'brand_name_en',
    ])
    expect(key).toBe('company_name')
  })
})

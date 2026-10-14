import { describe, expect, it } from 'vitest'
import { draftMidway } from '../../mocks/fixtures'
import { firstChangedKeyInPanelOrder } from './draftGroups'

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

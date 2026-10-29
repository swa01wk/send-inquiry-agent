import { describe, expect, it } from 'vitest'
import { channelLabel } from './reviewerSession'

describe('channelLabel', () => {
  it('labels Guest Service assisted intake', () => {
    expect(channelLabel('assisted', 'guest_service')).toBe('Started by Guest Service')
  })

  it('labels call-centre assisted intake', () => {
    expect(channelLabel('assisted', 'customer_care')).toBe('Started by the call centre')
    expect(channelLabel('assisted')).toBe('Started by the call centre')
  })

  it('labels existing tenant and hides self-service', () => {
    expect(channelLabel('existing_tenant')).toBe('Existing tenant')
    expect(channelLabel('self_service')).toBeNull()
  })
})

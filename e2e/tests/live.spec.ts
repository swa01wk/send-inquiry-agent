import { test } from '@playwright/test'
import { InquiryPage } from '../pages/inquiry'
import { assertPlainLanguageReply } from '../support/plainLanguage'

test.describe('Live OpenAI personas @live', () => {
  test.skip(!process.env.OPENAI_API_KEY, 'OPENAI_API_KEY required')

  test('01 shop owner live', async ({ page }) => {
    const inquiry = new InquiryPage(page)
    await inquiry.open()
    await inquiry.say('hi')
    await inquiry.say('1010123456')
    await inquiry.say('coffee kiosk riyadh mall a')
    await inquiry.say('sara ali sara@beanstreet.example 0501234567')
    const reply = await inquiry.lastReply()
    assertPlainLanguageReply(reply, inquiry.userContext())
    const draft = await inquiry.draft()
    const fields = draft.fields as { key: string; display: string | null }[]
    expect(fields.find((f) => f.key === 'mobile')?.display).toContain('966')
  })
})

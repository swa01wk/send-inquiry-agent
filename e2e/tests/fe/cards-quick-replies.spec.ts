import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'
import { finishA11yOnPage } from '../../support/turnChecks'

test.describe('Quick replies @fe', () => {
  test('chip sends message to mock', async ({ page }, testInfo) => {
    const inquiry = new FeInquiryPage(page)
    await inquiry.openMock('quick-replies')
    await inquiry.tapChip('I have my CR number')
    const text = await inquiry.lastBotText()
    expect(text).toMatch(/CR/i)
    const requests = await inquiry.mockRequests()
    expect(
      requests.some(
        (r) =>
          (r as { type?: string; text?: string }).type === 'message' &&
          (r as { text?: string }).text === 'I have my CR number',
      ),
    ).toBeTruthy()
    await finishA11yOnPage(page, testInfo.project.name)
  })
})

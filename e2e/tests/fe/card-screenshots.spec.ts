import { expect, test } from '@playwright/test'
import { FeInquiryPage } from '../../pages/feInquiry'

const cardScenarios: Array<{ scenario: string; card: string }> = [
  { scenario: 'confirm-fields', card: 'confirm_fields' },
  { scenario: 'mall-picker', card: 'mall_picker' },
  { scenario: 'verification', card: 'verification' },
  { scenario: 'documents-partial', card: 'document_upload' },
  { scenario: 'review', card: 'review' },
  { scenario: 'success', card: 'success' },
  { scenario: 'basic-info-review', card: 'basic_info_review' },
  { scenario: 'send-link', card: 'send_link' },
  { scenario: 'existing-cr-choice', card: 'existing_cr_choice' },
  { scenario: 'sign-in-prompt', card: 'sign_in_prompt' },
]

test.describe('Card screenshots @fe', () => {
  for (const { scenario, card } of cardScenarios) {
    test(`${scenario} ${card}`, async ({ page }, testInfo) => {
      test.skip(!process.env.GITHUB_ACTIONS, 'screenshot baselines run in GitHub CI only')
      const inquiry = new FeInquiryPage(page)
      await inquiry.openMock(scenario)
      const locator = inquiry.cards(card)
      await expect(locator).toBeVisible()
      await expect(locator).toHaveScreenshot(`${scenario}-${testInfo.project.name}.png`, {
        maxDiffPixels: 100,
      })
    })
  }
})

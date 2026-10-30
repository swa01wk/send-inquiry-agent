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

// The chat panel has a fixed height with overflow hidden, so a tall card (review) is clipped
// and the composer shows under it. For the screenshot, let the panel grow and hide the composer.
const SCREENSHOT_CSS = `
  :root { --panel-height: 2400px !important; }
  textarea[aria-label="Message"], button[aria-label="Send message"] { visibility: hidden !important; }
`

test.describe('Card screenshots @fe', () => {
  for (const { scenario, card } of cardScenarios) {
    test(`${scenario} ${card}`, async ({ page }, testInfo) => {
      test.skip(!process.env.GITHUB_ACTIONS, 'screenshot baselines run in GitHub CI only')
      // Desktop only: on mobile the element crop lands off the card (nested scroll area).
      test.skip(testInfo.project.name !== 'desktop-chrome', 'screenshot baselines are desktop only')
      const inquiry = new FeInquiryPage(page)
      await inquiry.openMock(scenario)
      const locator = inquiry.cards(card)
      await expect(locator).toBeVisible()
      await page.addStyleTag({ content: SCREENSHOT_CSS })
      await expect(locator).toHaveScreenshot(`${scenario}-${testInfo.project.name}.png`, {
        maxDiffPixels: 100,
      })
    })
  }
})

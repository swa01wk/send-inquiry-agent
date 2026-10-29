import { expect, test } from '@playwright/test'
import { clearDevOutbox } from '../support/outbox'
import { reviewerFor } from '../support/submit'
import {
  completeApplicationFromLink,
  openReviewerCase,
  signInReviewer,
  staffSendApplicationLink,
  startCallCentreInquiry,
} from '../support/stories'

/** Day 5 C2: Guest Service desk — same A2 scripted path, different staff role label. */
test.describe('Story A2 Guest Service @scripted', () => {
  test('Dana sends link; applicant sees Guest Service greeting; reviewer channel label', async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000)
    await clearDevOutbox(request)

    const staffChat = await startCallCentreInquiry(page, 'Dana Al Rashid', 'a2-call-centre')
    const verifyPath = await staffSendApplicationLink(staffChat, request)
    const reference = await completeApplicationFromLink(
      browser,
      request,
      verifyPath,
      page,
      undefined,
      async (applicantPage) => {
        await expect(
          applicantPage.getByTestId('bot-bubble-text').filter({
            hasText: /Guest Service desk started this inquiry/i,
          }),
        ).toBeVisible({ timeout: 60_000 })
      },
    )

    const viewport = page.viewportSize()
    const reviewerContext = await browser.newContext(viewport ? { viewport } : {})
    try {
      const reviewer = await reviewerFor(request, reference)
      const reviewerPage = await reviewerContext.newPage()
      await signInReviewer(reviewerPage, reviewer)
      await openReviewerCase(reviewerPage, reference)
      await expect(reviewerPage.getByTestId('case-channel')).toHaveText(
        'Started by the call centre',
      )
    } finally {
      await reviewerContext.close()
    }
  })
})

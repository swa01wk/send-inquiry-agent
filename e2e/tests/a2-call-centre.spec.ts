import { expect, test } from "@playwright/test";
import { clearDevOutbox } from "../support/outbox";
import { reviewerFor } from "../support/submit";
import {
  completeApplicationFromLink,
  openReviewerCase,
  signInReviewer,
  staffSendApplicationLink,
  startCallCentreInquiry,
} from "../support/stories";

/** Day 5 B5b / C2: call-centre assisted intake → application link → applicant completes → reviewer channel. */
test.describe("Story A2 call centre @scripted", () => {
  test("staff sends link; applicant finishes; reviewer sees call-centre channel", async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000);
    await clearDevOutbox(request);

    const staffChat = await startCallCentreInquiry(
      page,
      "Sami Al Anazi",
      "a2-call-centre",
    );
    const verifyPath = await staffSendApplicationLink(staffChat, request);
    const reference = await completeApplicationFromLink(
      browser,
      request,
      verifyPath,
      page,
    );

    const reviewer = await reviewerFor(request, reference);
    const viewport = page.viewportSize();
    const reviewerContext = await browser.newContext(
      viewport ? { viewport } : {},
    );
    try {
      const reviewerPage = await reviewerContext.newPage();
      await signInReviewer(reviewerPage, reviewer);
      await openReviewerCase(reviewerPage, reference);
      await expect(reviewerPage.getByTestId("case-channel")).toHaveText(
        "Started by the call centre",
      );
    } finally {
      await reviewerContext.close();
    }
  });
});

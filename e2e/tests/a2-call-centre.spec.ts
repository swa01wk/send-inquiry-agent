import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { A2_CALL_CENTRE_TURNS } from "../support/channelScripts";
import {
  clearDevOutbox,
  completeVerifyLink,
  fetchDevOutbox,
  latestByTemplate,
  withE2eScenario,
} from "../support/outbox";
import {
  APPLICANT_EMAIL,
  completeApplicationLinkFlow,
  reviewerFor,
} from "../support/submit";

/** Day 5 B5b: call-centre assisted intake → application link → applicant completes → reviewer channel. */
test.describe("Story A2 call centre @scripted", () => {
  test("staff sends link; applicant finishes; reviewer sees call-centre channel", async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000);
    await clearDevOutbox(request);

    await page.goto("/dev");
    await page.getByTestId("dev-staff").getByRole("link").first().click();
    await expect(page.getByTestId("callcentre-signed-in")).toBeVisible();

    await page.goto("/callcentre?e2eScenario=a2-call-centre");
    await expect(page.getByTestId("callcentre-new-inquiry")).toBeVisible();
    await page.getByTestId("callcentre-new-inquiry").click();
    await expect(
      page.getByRole("region", { name: /leasing assistant chat/i }),
    ).toBeVisible({
      timeout: 60_000,
    });

    const staffChat = new InquiryPage(page);
    await staffChat.waitForChatReady();
    for (const turn of A2_CALL_CENTRE_TURNS) {
      await staffChat.say(turn);
    }

    await expect(staffChat.cards("send_link")).toBeVisible({ timeout: 60_000 });
    await staffChat.sendApplicationLink();
    await expect(
      staffChat.cards("send_link").getByText(/Link sent to/i),
    ).toBeVisible();

    await expect
      .poll(async () =>
        latestByTemplate(
          await fetchDevOutbox(request, APPLICANT_EMAIL),
          "complete_application",
        ),
      )
      .toBeTruthy();
    const verifyPath = withE2eScenario(
      completeVerifyLink(await fetchDevOutbox(request, APPLICANT_EMAIL)),
      "a2-applicant",
    );

    const viewport = page.viewportSize();
    const applicantContext = await browser.newContext(
      viewport ? { viewport } : {},
    );
    const reviewerContext = await browser.newContext(
      viewport ? { viewport } : {},
    );
    try {
      const applicantPage = await applicantContext.newPage();
      const applicant = new InquiryPage(applicantPage);
      await applicant.openApplicationVerifyLink(verifyPath);
      const reference = await completeApplicationLinkFlow(applicant, request);

      const reviewer = await reviewerFor(request, reference);
      const reviewerPage = await reviewerContext.newPage();
      await reviewerPage.goto("/review");
      await reviewerPage.getByLabel("Reviewer").selectOption(reviewer.id);
      await reviewerPage.getByRole("button", { name: "Sign in" }).click();
      await expect(
        reviewerPage.getByTestId("signed-in-reviewer"),
      ).toContainText(reviewer.name);
      await reviewerPage
        .getByTestId(`queue-row-${reference}`)
        .getByRole("link", { name: reference })
        .click();
      await expect(reviewerPage.getByTestId("case-channel")).toHaveText(
        "Started by the call centre",
      );
    } finally {
      await applicantContext.close();
      await reviewerContext.close();
    }
  });
});

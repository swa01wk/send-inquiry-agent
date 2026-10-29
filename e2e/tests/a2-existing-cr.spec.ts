import { expect, test } from "@playwright/test";
import { readDoneEventCount } from "../support/events";
import { draftFields, fieldDisplay } from "../support/draft";
import {
  clearDevOutbox,
  fetchDevOutbox,
  latestByTemplate,
} from "../support/outbox";
import { reviewerFor } from "../support/submit";
import {
  C1_EXISTING_CR_TURN,
  OASIS_APPLICANT_EMAIL,
  OASIS_APPLICANT_MOBILE,
  completeApplicationFromLink,
  openCallCentreChat,
  openReviewerCase,
  signInReviewer,
  staffSendApplicationLink,
} from "../support/stories";

/** Day 5 C2: assisted mode when the caller's CR matches an existing tenant (c1-existing-cr). */
test.describe("Story A2 existing CR @scripted", () => {
  test.beforeEach(async ({ request }) => {
    await clearDevOutbox(request);
  });

  test("ask them to sign in: choice recorded and no application link", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    const chat = await openCallCentreChat(
      page,
      "Sami Al Anazi",
      "c1-existing-cr-sign-in",
    );
    await chat.say(C1_EXISTING_CR_TURN);

    const choice = chat.cards("existing_cr_choice");
    await expect(choice).toBeVisible({ timeout: 60_000 });
    await expect(choice).toContainText("Oasis Coffee Company");
    const doneBefore = await readDoneEventCount(page);
    await choice.getByRole("button", { name: "Ask them to sign in" }).click();
    await chat.waitForTurnDone(doneBefore);

    await expect(choice.getByText("Ask them to sign in")).toBeVisible();
    await expect(chat.cards("send_link")).toHaveCount(0);
  });

  test("continue for them: tenant record on draft, link, applicant submits", async ({
    page,
    browser,
    request,
  }) => {
    test.setTimeout(240_000);
    const chat = await openCallCentreChat(
      page,
      "Sami Al Anazi",
      "c1-existing-cr",
    );
    await chat.say(C1_EXISTING_CR_TURN);

    const choice = chat.cards("existing_cr_choice");
    await expect(choice).toBeVisible({ timeout: 60_000 });
    await expect(choice).toContainText("Oasis Coffee Company");
    await choice.getByRole("button", { name: "Continue for them" }).click();
    await expect(choice.getByText("Continue for them")).toBeVisible();

    const draft = await chat.draft();
    expect(fieldDisplay(draft, "company_name")).toBe("Oasis Coffee Company");
    const companyField = draftFields(draft).find(
      (f) => f.key === "company_name",
    );
    expect(companyField?.source).toBe("verified");

    const verifyPath = await staffSendApplicationLink(
      chat,
      request,
      OASIS_APPLICANT_EMAIL,
    );
    const reference = await completeApplicationFromLink(
      browser,
      request,
      verifyPath,
      page,
      { email: OASIS_APPLICANT_EMAIL, mobile: OASIS_APPLICANT_MOBILE },
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

    expect(
      latestByTemplate(
        await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL),
        "complete_application",
      ),
    ).toBeTruthy();
  });
});

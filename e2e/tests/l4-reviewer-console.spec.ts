import { expect, test } from "@playwright/test";
import { clearDevOutbox } from "../support/outbox";
import { reviewerFor, submitScriptedInquiry } from "../support/submit";

/** Day 4: the console offers only the actions the state machine allows (L4 §3.3). */
test.describe("Reviewer console @scripted", () => {
  test("first review → approve first level → second review shows only its legal actions", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    await clearDevOutbox(request);
    const reference = await submitScriptedInquiry(
      page,
      request,
      "s1-happy-path",
    );
    const reviewer = await reviewerFor(request, reference);

    await page.goto("/review");
    await page.getByLabel("Reviewer").selectOption(reviewer.id);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page.getByTestId("signed-in-reviewer")).toContainText(
      reviewer.name,
    );
    await page
      .getByTestId(`queue-row-${reference}`)
      .getByRole("link", { name: reference })
      .click();

    // First review: decide the first level, ask for a re-upload or reject.
    await expect(page.getByTestId("case-stage")).toHaveText("First review");
    await expect(page.getByTestId("action-approve_first")).toBeVisible();
    await expect(page.getByTestId("action-request_reupload")).toBeVisible();
    await expect(page.getByTestId("action-reject")).toBeVisible();
    await expect(page.getByTestId("action-approve")).toHaveCount(0);
    await expect(page.getByTestId("action-yardi")).toHaveCount(0);
    await expect(page.getByTestId("action-requests")).toHaveCount(0);

    await page
      .getByTestId("action-approve_first")
      .getByRole("button", { name: "Approve first level" })
      .click();

    // Second review: the contacts request opened automatically, so final approval is blocked.
    await expect(page.getByTestId("case-stage")).toHaveText(
      "Lead — second review",
    );
    await expect(page.getByTestId("action-approve_first")).toHaveCount(0);
    await expect(page.getByTestId("action-approve")).toHaveCount(0);
    await expect(page.getByTestId("approval-blockers")).toContainText(
      "Contacts request still open",
    );
    await expect(page.getByTestId("action-yardi")).toBeVisible();
    await expect(page.getByTestId("action-withdraw_request")).toBeVisible();
    const requests = page.getByTestId("action-requests");
    await expect(
      requests.getByRole("button", { name: "Request sales data" }),
    ).toBeVisible();
    await expect(
      requests.getByRole("button", { name: "Request contacts" }),
    ).toHaveCount(0);
    await expect(page.getByTestId("requests")).toContainText("contacts · open");
    await expect(page.getByTestId("timeline")).toContainText(/approved/i);

    // Back on the queue, the case now waits on the applicant.
    await page.getByRole("link", { name: "← Back to the queue" }).click();
    await expect(page.getByTestId(`queue-row-${reference}`)).toContainText(
      "Applicant",
    );
  });
});

import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { clearDevOutbox } from "../support/outbox";

/** Day 5 B5b: existing tenant raises from Leasing Opportunities and submits with prefilled data. */
test.describe("Story A1 existing tenant @scripted", () => {
  test("Oasis raises on OPP-101, proceeds and submits; inquiry appears in My inquiries", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    await clearDevOutbox(page.request);

    await page.goto("/dev");
    await page
      .getByTestId("dev-tenants")
      .getByRole("link", { name: /Oasis Coffee Company/ })
      .click();
    await expect(page.getByTestId("tenant-signed-in")).toContainText(
      "Oasis Coffee Company",
    );

    await page.goto("/tenant/opportunities?e2eScenario=a1-existing-tenant");
    await expect(page.getByTestId("opportunity-OPP-101")).toBeVisible({
      timeout: 30_000,
    });
    await page
      .getByTestId("opportunity-OPP-101")
      .getByRole("button", { name: "Raise inquiry" })
      .click();
    await expect(
      page.getByRole("region", { name: /leasing assistant chat/i }),
    ).toBeVisible({
      timeout: 60_000,
    });

    const inquiry = new InquiryPage(page);
    await inquiry.waitForChatReady();
    const greeting = page
      .getByTestId("bot-bubble-text")
      .filter({ hasText: /Welcome back, Layla/ });
    await expect(greeting).toBeVisible({ timeout: 30_000 });

    await expect(inquiry.cards("basic_info_review")).toBeVisible({
      timeout: 60_000,
    });
    await inquiry.proceedBasicInfo();
    await expect(
      inquiry
        .cards("basic_info_review")
        .getByText("Basic information confirmed"),
    ).toBeVisible();
    await expect(inquiry.cards("review")).toBeVisible({ timeout: 60_000 });
    await inquiry.acceptAndSubmit();
    await expect(inquiry.cards("success")).toBeVisible({ timeout: 60_000 });
    const reference = await inquiry.successReference();

    await page.goto("/tenant/inquiries");
    await expect(page.getByTestId("my-inquiries")).toContainText(reference);
  });
});

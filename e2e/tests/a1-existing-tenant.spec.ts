import { expect, test } from "@playwright/test";
import { raiseTenantInquiry } from "../support/stories";

/** Day 5 B5b / C2: existing tenant raises from Leasing Opportunities and submits with prefilled data. */
test.describe("Story A1 existing tenant @scripted", () => {
  test("Oasis raises on OPP-101, proceeds and submits; inquiry appears in My inquiries", async ({
    page,
  }) => {
    test.setTimeout(240_000);

    const { reference } = await raiseTenantInquiry(
      page,
      /Oasis Coffee Company/,
      "OPP-101",
      "a1-existing-tenant",
      /Welcome back, Layla/,
    );

    await page.goto("/tenant/inquiries");
    await expect(page.getByTestId("my-inquiries")).toContainText(reference);
  });
});

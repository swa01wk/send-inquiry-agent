import { expect, test, type Page } from "@playwright/test";
import { fetchDevOutbox } from "../support/outbox";
import { advanceClockToLocalHour } from "../support/stories";
import {
  APPLICANT_EMAIL,
  reviewerFor,
  submitScriptedInquiry,
} from "../support/submit";

const API = "http://127.0.0.1:8000";

async function advanceFromDevPage(
  page: Page,
  button: "+24 h" | "+48 h" | "To morning (08:00)",
) {
  await page.goto("/dev");
  await expect(page.getByTestId("dev-clock")).not.toHaveText("Loading…");
  await page.getByRole("button", { name: button }).click();
  await expect(page.getByTestId("dev-message")).toBeVisible();
}

async function countTemplate(
  request: Parameters<typeof fetchDevOutbox>[0],
  template: string,
) {
  return (await fetchDevOutbox(request)).filter((m) => m.template === template)
    .length;
}

/** Day 5 L5 core: stalled → escalated → drafted reminder → approved → sent once. */
test.describe("Needs attention (L5) @scripted", () => {
  test.afterEach(async ({ request }) => {
    await request.post(`${API}/api/dev/reset`); // leave the clock and data clean for others
  });

  test("the clock surfaces stuck cases and drafted reminders under the policy", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    await request.post(`${API}/api/dev/reset`);
    const reference = await submitScriptedInquiry(
      page,
      request,
      "s1-happy-path",
    );
    const reviewer = await reviewerFor(request, reference);

    // 48 h in first review → flagged to the queue, one email to its reviewers.
    await advanceFromDevPage(page, "+48 h");
    await expect(page.getByTestId("dev-message")).toContainText("1 raised");
    expect(await countTemplate(request, "review_stalled")).toBe(1);

    await page.goto("/dev");
    await page
      .getByTestId("dev-reviewers")
      .getByRole("link", { name: reviewer.name })
      .click();
    await expect(page.getByTestId("attention-badge")).toHaveText("1");
    await page.getByTestId("attention-link").click();
    await expect(
      page.getByTestId(`attention-stalled_review-${reference}`),
    ).toBeVisible();

    // 96 h → escalated to the region manager for that role.
    await advanceFromDevPage(page, "+48 h");
    expect(await countTemplate(request, "review_escalated")).toBe(1);
    await page.goto("/dev");
    const managerId = `${reviewer.id.split("-")[0]}-manager`; // the role's region manager
    await page.locator(`a[href="/review?as=${managerId}"]`).click();
    await page.getByTestId("attention-link").click();
    await expect(
      page.getByTestId(`attention-escalation-${reference}`),
    ).toBeVisible();

    // First approval opens a contacts request; 72 h unanswered → a drafted reminder.
    await page.goto(`/review?as=${encodeURIComponent(reviewer.id)}`);
    await page
      .getByTestId(`queue-row-${reference}`)
      .getByRole("link", { name: reference })
      .click();
    await page.getByRole("button", { name: "Approve first level" }).click();
    await expect(page.getByTestId("case-stage")).toHaveText(
      "Lead — second review",
    );
    await advanceFromDevPage(page, "+48 h");
    await advanceFromDevPage(page, "+24 h");
    expect(await countTemplate(request, "applicant_reminder")).toBe(0); // waits for approval

    await page.goto(
      `/review/attention?as=${encodeURIComponent(reviewer.id)}&e2eScenario=r2-tenant-reminder`,
    );
    const reminder = page.getByTestId(
      `attention-applicant_reminder-${reference}`,
    );
    await expect(reminder.getByLabel("Reminder to the applicant")).toHaveValue(
      /company contacts/,
    );
    await reminder.getByTestId("attention-draft-assistant").click();
    const draftCard = reminder.getByTestId("attention-assistant-draft");
    await expect(draftCard).toBeVisible({ timeout: 60_000 });
    await reminder.getByTestId("attention-use-draft").click();
    await expect(reminder.getByLabel("Reminder to the applicant")).toHaveValue(
      /contacts/,
    );

    await advanceClockToLocalHour(request, 23);
    await reminder.getByRole("button", { name: "Approve and send" }).click();
    await expect(reminder.getByTestId("attention-held")).toContainText(
      "held until",
    );
    expect(
      (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
        (m) => m.template === "applicant_reminder",
      ),
    ).toHaveLength(0);

    await advanceFromDevPage(page, "To morning (08:00)");
    const sent = (await fetchDevOutbox(request, APPLICANT_EMAIL)).filter(
      (m) => m.template === "applicant_reminder",
    );
    expect(sent).toHaveLength(1);
    expect(sent[0].links.some((l) => l.includes("/inquiry/case?t="))).toBe(
      true,
    );
  });
});

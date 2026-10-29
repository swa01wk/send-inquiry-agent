import {
  expect,
  type APIRequestContext,
  type Browser,
  type Page,
} from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { A2_CALL_CENTRE_TURNS, C1_EXISTING_CR_TURN } from "./channelScripts";
import {
  clearDevOutbox,
  completeVerifyLink,
  fetchDevOutbox,
  latestByTemplate,
  withE2eScenario,
} from "./outbox";
import {
  APPLICANT_EMAIL,
  APPLICANT_MOBILE,
  completeApplicationLinkFlow,
  type ContactOutbox,
} from "./submit";

export { A2_CALL_CENTRE_TURNS, C1_EXISTING_CR_TURN };

export const OASIS_APPLICANT_EMAIL = "layla.hassan@oasiscoffee.example";
export const OASIS_APPLICANT_MOBILE = "+966551110001";

/** Mock sign-in as call-centre or Guest Service staff and open a blank assisted chat. */
export async function openCallCentreChat(
  page: Page,
  staffName: string,
  scenario: string,
): Promise<InquiryPage> {
  await page.goto("/dev");
  await page
    .getByTestId("dev-staff")
    .getByRole("link", { name: new RegExp(staffName) })
    .click();
  await expect(page.getByTestId("callcentre-signed-in")).toBeVisible();

  await page.goto(`/callcentre?e2eScenario=${encodeURIComponent(scenario)}`);
  await expect(page.getByTestId("callcentre-new-inquiry")).toBeVisible();
  await page.getByTestId("callcentre-new-inquiry").click();
  await expect(
    page.getByRole("region", { name: /leasing assistant chat/i }),
  ).toBeVisible({ timeout: 60_000 });

  const staffChat = new InquiryPage(page);
  await staffChat.waitForChatReady();
  return staffChat;
}

/** A2 scripted staff turns through to the send-link card. */
export async function startCallCentreInquiry(
  page: Page,
  staffName: string,
  scenario: string,
): Promise<InquiryPage> {
  const staffChat = await openCallCentreChat(page, staffName, scenario);
  for (const turn of A2_CALL_CENTRE_TURNS) {
    await staffChat.say(turn);
  }
  return staffChat;
}

export async function staffSendApplicationLink(
  staffChat: InquiryPage,
  request: APIRequestContext,
  applicantEmail: string = APPLICANT_EMAIL,
  applicantScenario = "a2-applicant",
): Promise<string> {
  await expect(staffChat.cards("send_link")).toBeVisible({ timeout: 60_000 });
  await staffChat.sendApplicationLink();
  await expect(
    staffChat.cards("send_link").getByText(/Link sent to/i),
  ).toBeVisible();

  await expect
    .poll(async () =>
      latestByTemplate(
        await fetchDevOutbox(request, applicantEmail),
        "complete_application",
      ),
    )
    .toBeTruthy();

  return withE2eScenario(
    completeVerifyLink(await fetchDevOutbox(request, applicantEmail)),
    applicantScenario,
  );
}

/** Applicant completes from the emailed verify link; returns the inquiry reference. */
export async function completeApplicationFromLink(
  browser: Browser,
  request: APIRequestContext,
  verifyPath: string,
  viewportPage: Page,
  contact: ContactOutbox = {
    email: APPLICANT_EMAIL,
    mobile: APPLICANT_MOBILE,
  },
  onApplicantReady?: (page: Page) => Promise<void>,
): Promise<string> {
  const viewport = viewportPage.viewportSize();
  const applicantContext = await browser.newContext(
    viewport ? { viewport } : {},
  );
  try {
    const applicantPage = await applicantContext.newPage();
    const applicant = new InquiryPage(applicantPage);
    await applicant.openApplicationVerifyLink(verifyPath);
    if (onApplicantReady) await onApplicantReady(applicantPage);
    return await completeApplicationLinkFlow(applicant, request, contact);
  } finally {
    await applicantContext.close();
  }
}

export async function signInReviewer(
  page: Page,
  reviewer: { id: string; name: string },
): Promise<void> {
  await page.goto("/review");
  await page.getByLabel("Reviewer").selectOption(reviewer.id);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("signed-in-reviewer")).toContainText(
    reviewer.name,
  );
}

export async function openReviewerCase(
  page: Page,
  reference: string,
): Promise<void> {
  await page
    .getByTestId(`queue-row-${reference}`)
    .getByRole("link", { name: reference })
    .click();
}

/** Existing tenant: sign in, raise on an opportunity, confirm prefilled info, submit. */
export async function raiseTenantInquiry(
  page: Page,
  tenantName: RegExp | string,
  opportunityId: string,
  scenario: string,
  welcomePattern?: RegExp,
): Promise<{ inquiry: InquiryPage; reference: string }> {
  await clearDevOutbox(page.request);

  await page.goto("/dev");
  await page
    .getByTestId("dev-tenants")
    .getByRole("link", { name: tenantName })
    .click();
  await expect(page.getByTestId("tenant-signed-in")).toBeVisible();

  await page.goto(
    `/tenant/opportunities?e2eScenario=${encodeURIComponent(scenario)}`,
  );
  await expect(page.getByTestId(`opportunity-${opportunityId}`)).toBeVisible({
    timeout: 30_000,
  });
  await page
    .getByTestId(`opportunity-${opportunityId}`)
    .getByRole("button", { name: "Raise inquiry" })
    .click();
  await expect(
    page.getByRole("region", { name: /leasing assistant chat/i }),
  ).toBeVisible({ timeout: 60_000 });

  const inquiry = new InquiryPage(page);
  await inquiry.waitForChatReady();
  if (welcomePattern) {
    await expect(
      page.getByTestId("bot-bubble-text").filter({ hasText: welcomePattern }),
    ).toBeVisible({ timeout: 30_000 });
  }

  await expect(inquiry.cards("basic_info_review")).toBeVisible({
    timeout: 60_000,
  });
  await inquiry.proceedBasicInfo();
  await expect(
    inquiry.cards("basic_info_review").getByText("Basic information confirmed"),
  ).toBeVisible();
  await expect(inquiry.cards("review")).toBeVisible({ timeout: 60_000 });
  await inquiry.acceptAndSubmit();
  await expect(inquiry.cards("success")).toBeVisible({ timeout: 60_000 });
  const reference = await inquiry.successReference();
  return { inquiry, reference };
}

const API = "http://127.0.0.1:8000";

/** Advance the simulated clock until local time in `timezone` is `targetHour` (0–23). */
export async function advanceClockToLocalHour(
  request: APIRequestContext,
  targetHour: number,
): Promise<void> {
  const clock = (await (await request.get(`${API}/api/dev/clock`)).json()) as {
    now: string;
    timezone: string;
  };
  const hours = hoursUntilLocalHour(clock.now, clock.timezone, targetHour);
  const res = await request.post(`${API}/api/dev/clock/advance`, {
    data: { hours },
  });
  expect(res.ok()).toBeTruthy();
}

function hoursUntilLocalHour(
  isoNow: string,
  timeZone: string,
  targetHour: number,
): number {
  const now = new Date(isoNow);
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).formatToParts(now);
  const n = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((p) => p.type === type)?.value ?? 0);
  const h = n("hour");
  const m = n("minute");
  const s = n("second");
  let diffHours = targetHour - h;
  if (diffHours <= 0) diffHours += 24;
  return diffHours - m / 60 - s / 3600;
}

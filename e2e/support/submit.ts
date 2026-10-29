import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import {
  fetchDevOutbox,
  latestByTemplate,
  referenceFromReviewAssigned,
  smsOtpCode,
} from "./outbox";

const API = "http://127.0.0.1:8000";

async function ensureDocumentReady(
  inquiry: InquiryPage,
  docLabel: string,
  fileName: string,
) {
  const card = inquiry.cards("document_upload");
  const row = card
    .locator('[data-testid^="doc-row-"]')
    .filter({ hasText: docLabel });
  await expect(row).toHaveCount(1);
  const status = row.getByTestId("doc-status");
  const text = ((await status.textContent()) ?? "").trim();
  if (text === "On file" || text.startsWith("Uploaded")) return;
  await inquiry.upload(docLabel, fileName);
}

export const APPLICANT_EMAIL = "sara@beanstreet.example";
export const APPLICANT_MOBILE = "+966501234567";

export type ContactOutbox = { email: string; mobile: string };

/** The S1 scripted path (`scenario` must be a script in `backend/tests/e2e_scripts/`, e.g.
 * `s1-happy-path`) to a submitted inquiry, without per-turn checks. Returns the reference. */
export async function submitScriptedInquiry(
  page: Page,
  request: APIRequestContext,
  scenario: string,
): Promise<string> {
  const inquiry = new InquiryPage(page);
  await inquiry.open(scenario);
  await inquiry.say("1010123456");
  await inquiry.confirmCard();
  await inquiry.say(
    "Bean Street kiosk Riyadh Mall A 30 sqm Sara Ali sara@beanstreet.example 0501234567",
  );
  await inquiry.confirmCard();
  await expect(inquiry.cards("verification")).toBeVisible({ timeout: 60_000 });
  await inquiry.verifyEmailFromInbox(APPLICANT_EMAIL);
  await inquiry.enterCode(
    smsOtpCode(await fetchDevOutbox(request, APPLICANT_MOBILE)),
  );
  await expect(inquiry.cards("document_upload")).toBeVisible({
    timeout: 90_000,
  });
  await inquiry.upload("Company Profile", "company_profile.pdf");
  await inquiry.upload("Brand Profile", "brand_profile.pdf");
  await expect(inquiry.cards("review")).toBeVisible({ timeout: 60_000 });
  await inquiry.acceptAndSubmit();
  await expect(inquiry.cards("success")).toBeVisible({ timeout: 60_000 });

  return referenceFromReviewAssigned(await fetchDevOutbox(request));
}

/** Applicant path after opening the call-centre `complete_application` link (scripted `a2-applicant`). */
export async function completeApplicationLinkFlow(
  inquiry: InquiryPage,
  request: APIRequestContext,
  contact: ContactOutbox = {
    email: APPLICANT_EMAIL,
    mobile: APPLICANT_MOBILE,
  },
): Promise<string> {
  await expect(inquiry.cards("basic_info_review")).toBeVisible({
    timeout: 60_000,
  });
  await inquiry.proceedBasicInfo();
  await expect(
    inquiry.cards("basic_info_review").getByText("Basic information confirmed"),
  ).toBeVisible();
  await expect(inquiry.cards("verification")).toBeVisible({ timeout: 60_000 });
  await inquiry.enterCode(
    smsOtpCode(await fetchDevOutbox(request, contact.mobile)),
  );
  await expect(inquiry.cards("document_upload")).toBeVisible({
    timeout: 90_000,
  });
  await ensureDocumentReady(inquiry, "Company Profile", "company_profile.pdf");
  await ensureDocumentReady(inquiry, "Brand Profile", "brand_profile.pdf");
  await expect(inquiry.cards("review")).toBeVisible({ timeout: 60_000 });
  await inquiry.acceptAndSubmit();
  await expect(inquiry.cards("success")).toBeVisible({ timeout: 60_000 });
  return inquiry.successReference();
}

/** The (non-manager) reviewer whose queue holds the case, from the review API. */
export async function reviewerFor(
  request: APIRequestContext,
  reference: string,
): Promise<{ id: string; name: string }> {
  const reviewers = (await (
    await request.get(`${API}/api/review/reviewers`)
  ).json()) as {
    id: string;
    name: string;
    manager: boolean;
  }[];
  for (const reviewer of reviewers.filter((r) => !r.manager)) {
    const res = await request.get(`${API}/api/review/cases`, {
      headers: { "X-Reviewer-Id": reviewer.id },
    });
    const cases = (await res.json()) as { reference: string }[];
    if (cases.some((c) => c.reference === reference)) return reviewer;
  }
  throw new Error(`No reviewer has ${reference} in their queue`);
}

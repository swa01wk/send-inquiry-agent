import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { readCapturedEvents } from "../support/events";
import {
  clearDevOutbox,
  fetchDevOutbox,
  latestByTemplate,
} from "../support/outbox";

const EMAIL = "sara@beanstreet.example";
const MOBILE = "+966501234567";
const CLAIMS_SUCCESS =
  /\b(has been|was) (submitted|sent|received)\b|your reference(?: number)? is/i;

// Story S3 (L3 §3.13): the first Submit times out (`X-Mock-Faults: submit:timeout:1`).
// Nothing claims success until the reference arrives; Submit again returns it.
test.describe("Story S3 @scripted", () => {
  test("submit times out, nothing claims success, the retry gets the reference", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    await clearDevOutbox(request);

    const inquiry = new InquiryPage(page);
    await inquiry.open("s3-submit-timeout", { faults: "submit:timeout:1" });
    await inquiry.say("1010123456");
    await inquiry.confirmCard();
    await inquiry.say(
      "Bean Street kiosk Riyadh Mall A 30 sqm Sara Ali sara@beanstreet.example 0501234567",
    );
    await inquiry.confirmCard();
    await expect(inquiry.cards("verification")).toBeVisible({
      timeout: 60_000,
    });
    expect(
      latestByTemplate(
        await fetchDevOutbox(request, EMAIL),
        "email_verification_link",
      ),
    ).toBeTruthy();
    await inquiry.verifyEmailFromInbox(EMAIL);
    const sms = latestByTemplate(
      await fetchDevOutbox(request, MOBILE),
      "sms_otp",
    );
    await inquiry.enterCode(sms!.body.match(/\b(\d{4})\b/)![1]);
    await expect(inquiry.cards("document_upload")).toBeVisible({
      timeout: 90_000,
    });
    await inquiry.upload("Company Profile", "company_profile.pdf");
    await inquiry.upload("Brand Profile", "brand_profile.pdf");

    // First press: the submit service times out.
    await inquiry.acceptAndSubmit();
    await expect(inquiry.cards("success")).toHaveCount(0);
    const afterFirst = await readCapturedEvents(page);
    expect(
      afterFirst.some(
        (e) => e.event === "ui_card" && e.data.card_type === "success",
      ),
    ).toBe(false);
    expect((await inquiry.draft()).phase).toBe("review");
    expect(await inquiry.lastReply()).not.toMatch(CLAIMS_SUCCESS);
    expect(
      latestByTemplate(
        await fetchDevOutbox(request, EMAIL),
        "submission_email",
      ),
    ).toBeFalsy();

    // Second press: the same inquiry goes through once and the reference arrives.
    const review = inquiry.cards("review");
    await review.getByRole("button", { name: "Submit inquiry" }).click();
    await expect(inquiry.cards("success")).toBeVisible({ timeout: 60_000 });
    await expect(
      inquiry.cards("success").getByText(/GEO-[A-Z]{3}-\d{6}/),
    ).toBeVisible();
    await expect
      .poll(async () => (await inquiry.draft()).phase)
      .toBe("submitted");
    const mails = (await fetchDevOutbox(request, EMAIL)).filter(
      (m) => m.template === "submission_email",
    );
    expect(mails).toHaveLength(1);
  });
});

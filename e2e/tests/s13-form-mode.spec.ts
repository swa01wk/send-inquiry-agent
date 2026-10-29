import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import {
  clearDevOutbox,
  fetchDevOutbox,
  latestByTemplate,
} from "../support/outbox";

const MOBILE = "+966501234567";

// Story S13 (L3 §3.14): with the model down (`X-Mock-Faults: llm:unavailable:2`, two
// failures in the first turn), the user finishes the inquiry in form mode from the cards
// and submits; when the model answers again, the chat carries on.
test.describe("Story S13 @scripted", () => {
  test("finishes in form mode, then the chat carries on", async ({
    page,
    request,
  }) => {
    test.setTimeout(240_000);
    await clearDevOutbox(request);

    const inquiry = new InquiryPage(page);
    await inquiry.open("s13-form-mode", { faults: "llm:unavailable:2" });
    await inquiry.say("Hi, we want a kiosk at Riyadh Mall A");

    const form = inquiry.cards("form_mode");
    await expect(form).toBeVisible({ timeout: 60_000 });
    await expect(
      page
        .getByTestId("bot-bubble-text")
        .filter({ hasText: /assistant isn't available right now/i }),
    ).toBeVisible();
    await expect(
      form.getByRole("button", { name: /ask us to call you/i }),
    ).toBeVisible();

    await inquiry.formSkipCr();
    await inquiry.formSave("Company name", "Bean Street Trading Co.");
    await inquiry.formSave(
      "Company address",
      "King Fahd Road, Al Olaya, Riyadh",
    );
    await inquiry.formSave("Brand name (EN)", "Bean Street");
    await inquiry.formSave("Brand name (AR)", "بين ستريت");
    await inquiry.formSave("Unit type", "specialty");
    await inquiry.formSave("Sales category", "fnb_cafe");
    await inquiry.formSave("First name", "Sara");
    await inquiry.formSave("Last name", "Ali");
    await inquiry.formSave("Email", "sara@beanstreet.example");
    await inquiry.formSave("Mobile or landline", "0501234567");
    await inquiry.pickMallStartingWith("Riyadh Mall A");

    await expect(inquiry.cards("verification")).toBeVisible({
      timeout: 60_000,
    });
    await inquiry.verifyEmail();
    const sms = latestByTemplate(
      await fetchDevOutbox(request, MOBILE),
      "sms_otp",
    );
    await inquiry.enterCode(sms!.body.match(/\b(\d{4})\b/)![1]);

    await expect(inquiry.cards("document_upload")).toBeVisible({
      timeout: 60_000,
    });
    await inquiry.upload("Company Profile", "company_profile.pdf");
    await inquiry.upload("Brand Profile", "brand_profile.pdf");
    await inquiry.acceptAndSubmit();
    await expect(inquiry.cards("success")).toBeVisible({ timeout: 60_000 });

    // The model is back: the chat carries on and the card says so.
    await inquiry.say("Thanks! Can I ask one more thing?");
    expect(await inquiry.lastReply()).toMatch(/welcome back/i);
    await expect(form.getByText(/assistant is back/i)).toBeVisible();
    await expect(form.getByRole("button")).toHaveCount(0);
  });
});

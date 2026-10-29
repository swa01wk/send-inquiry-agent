import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { fieldDisplay, fieldSource } from "../support/draft";
import { countRetractions } from "../support/events";
import { afterTurnChecks, finishA11y } from "../support/turnChecks";

test.describe("Mistakes and changes @scripted", () => {
  test("04 typos still save mall", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("04-typos");
    await inquiry.say("1010123456");
    await afterTurnChecks(inquiry);
    await inquiry.say("beanstreet cofee kiosk in riyad mall a");
    await afterTurnChecks(inquiry);
    if (await inquiry.cards("mall_picker").count()) {
      await inquiry.pickMalls(["Riyadh Mall A"]);
    }
    const draft = await inquiry.draft();
    expect(fieldDisplay(draft, "malls")).toMatch(/Riyadh Mall A/i);
    const replies = await inquiry.allReplies();
    expect(replies.join(" ").toLowerCase()).not.toMatch(/invalid|error|failed/);
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("09 changes mind to full store", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("09-changes-mind");
    await inquiry.say("1010123456");
    await afterTurnChecks(inquiry);
    await inquiry.say("Bean Street kiosk riyadh mall a");
    await afterTurnChecks(inquiry);
    await inquiry.say("actually make it a full shop not kiosk");
    await afterTurnChecks(inquiry);
    const draft = await inquiry.draft();
    expect(fieldSource(draft, "unit_type")).toBe("user");
    expect(fieldDisplay(draft, "unit_type")).toMatch(/store/i);
    expect(await inquiry.cards("confirm_fields").count()).toBeLessThanOrEqual(
      2,
    );
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("12 wrong SMS code then success", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("12-wrong-code");
    await inquiry.say("1010123456");
    await afterTurnChecks(inquiry);
    await inquiry.say(
      "Bean Street kiosk riyadh mall a Sara Ali sara@beanstreet.example 0501234567",
    );
    await afterTurnChecks(inquiry);
    await inquiry.enterCode("0000");
    await inquiry.enterCode("0000");
    await inquiry.enterCode("1234");
    const replies = await inquiry.allReplies();
    const botText = replies.join("\n");
    expect(botText).not.toContain("1234");
    expect(botText).not.toContain("0000");
    const draft = await inquiry.draft();
    expect((draft.checks as { mobile_verified: boolean }).mobile_verified).toBe(
      true,
    );
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("13 wrong files then valid PDFs", async ({ page }, testInfo) => {
    test.setTimeout(120_000);
    const inquiry = new InquiryPage(page);
    await inquiry.open("13-wrong-files");
    await inquiry.say("1010123456");
    await afterTurnChecks(inquiry);
    await inquiry.say(
      "Bean Street kiosk riyadh mall a Sara Ali sara@beanstreet.example 0501234567",
    );
    await afterTurnChecks(inquiry);
    await inquiry.verifyEmail();
    await inquiry.enterCode("1234");
    await expect(inquiry.cards("document_upload")).toBeVisible({
      timeout: 90_000,
    });
    await inquiry.pickFile("Company Profile", "notes.txt");
    await inquiry.expectUploadError(
      "Company Profile",
      "That file type isn't supported.",
    );
    await inquiry.pickFile("Company Profile", "too_big.pdf");
    await inquiry.expectUploadError(
      "Company Profile",
      "That file is over 5 MB.",
    );
    await inquiry.upload("Company Profile", "company_profile.pdf");
    await inquiry.upload("Brand Profile", "brand_profile.pdf");
    const card = inquiry.cards("document_upload");
    await expect(card.getByText("Company Profile")).toBeVisible();
    await expect(card.getByText("Brand Profile")).toBeVisible();
    await expect(
      inquiry.page.getByText("2 of 2 required uploaded"),
    ).toBeVisible();
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("23 guard missed save retracts once", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("23-guard-missed-save");
    await inquiry.say("1010123456");
    await afterTurnChecks(inquiry);
    await expect
      .poll(async () => countRetractions(await inquiry.events()), {
        timeout: 10_000,
      })
      .toBe(1);
    await finishA11y(inquiry, testInfo.project.name);
  });
});

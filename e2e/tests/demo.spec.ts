import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { readDoneEventCount } from "../support/events";
import { draftFields, fieldDisplay } from "../support/draft";
import { beat, caption, demoTestTimeoutMs } from "../support/demoPace";
import { fetchDevOutbox, latestByTemplate } from "../support/outbox";
import {
  APPLICANT_EMAIL,
  reviewerFor,
  submitScriptedInquiry,
} from "../support/submit";
import {
  A2_CALL_CENTRE_TURNS,
  assertCleanAfterDemoReset,
  assertDevPersonasOpenInOneClick,
  C1_EXISTING_CR_TURN,
  completeApplicationFromLink,
  OASIS_APPLICANT_EMAIL,
  OASIS_APPLICANT_MOBILE,
  openCallCentreChat,
  openReviewerCase,
  raiseTenantInquiry,
  resetDemoFromDevPage,
  runL5AttentionFlow,
  signInReviewer,
  staffSendApplicationLink,
} from "../support/stories";

const API = "http://127.0.0.1:8000";
const LAYLA_EMAIL = "layla.hassan@oasiscoffee.example";
const OMAR_EMAIL = "omar@beanstreet.example";

test.use({ video: "on", trace: "on" });

/** Day 5 C3: full demo-script rehearsal and end-of-day check (desktop only). */
test.describe("Demo script @demo", () => {
  test("runs the Mon 2 Nov walkthrough in order", async ({
    page,
    browser,
    request,
  }, testInfo) => {
    test.skip(
      testInfo.project.name !== "desktop-chrome",
      "Demo is desktop-only",
    );
    test.setTimeout(demoTestTimeoutMs());

    await request.post(`${API}/api/dev/reset`);

    await test.step("/dev personas open in one click", async () => {
      await caption(page, "/dev personas open in one click");
      await assertDevPersonasOpenInOneClick(page);
    });

    await test.step("self-service", async () => {
      await caption(page, "self-service");
      const reference = await submitScriptedInquiry(
        page,
        request,
        "s1-happy-path",
        beat,
      );
      expect(reference).toMatch(/GEO-/);
    });

    await test.step("call centre", async () => {
      await caption(page, "call centre");
      const staffChat = await openCallCentreChat(
        page,
        "Sami Al Anazi",
        "a2-call-centre",
      );
      for (const turn of A2_CALL_CENTRE_TURNS) {
        await staffChat.say(turn);
        await beat(page);
      }
      const verifyPath = await staffSendApplicationLink(
        staffChat,
        request,
        APPLICANT_EMAIL,
        "a2-applicant",
        beat,
      );
      const reference = await completeApplicationFromLink(
        browser,
        request,
        verifyPath,
        page,
        undefined,
        undefined,
        beat,
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
        await beat(reviewerPage);
      } finally {
        await reviewerContext.close();
      }
    });

    await test.step("Guest Service", async () => {
      await caption(page, "Guest Service");
      const staffChat = await openCallCentreChat(
        page,
        "Dana Al Rashid",
        "a2-call-centre",
      );
      for (const turn of A2_CALL_CENTRE_TURNS) {
        await staffChat.say(turn);
        await beat(page);
      }
      const verifyPath = await staffSendApplicationLink(
        staffChat,
        request,
        undefined,
        "a2-applicant",
        beat,
      );
      const reference = await completeApplicationFromLink(
        browser,
        request,
        verifyPath,
        page,
        undefined,
        async (applicantPage) => {
          await expect(
            applicantPage.getByTestId("bot-bubble-text").filter({
              hasText: /Guest Service desk started this inquiry/i,
            }),
          ).toBeVisible({ timeout: 60_000 });
          await beat(applicantPage);
        },
        beat,
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
        await beat(reviewerPage);
      } finally {
        await reviewerContext.close();
      }
    });

    await test.step("call centre with an existing CR (both choices)", async () => {
      await caption(page, "call centre with an existing CR (both choices)");
      const signInChat = await openCallCentreChat(
        page,
        "Sami Al Anazi",
        "c1-existing-cr-sign-in",
      );
      await signInChat.say(C1_EXISTING_CR_TURN);
      await beat(page);
      const signInChoice = signInChat.cards("existing_cr_choice");
      await expect(signInChoice).toBeVisible({ timeout: 60_000 });
      await beat(page);
      const doneBeforeSignIn = await readDoneEventCount(page);
      await signInChoice
        .getByRole("button", { name: "Ask them to sign in" })
        .click();
      await signInChat.waitForTurnDone(doneBeforeSignIn);
      await beat(page);
      await expect(signInChoice.getByText("Ask them to sign in")).toBeVisible();
      await expect(signInChat.cards("send_link")).toHaveCount(0);

      const continueChat = await openCallCentreChat(
        page,
        "Sami Al Anazi",
        "c1-existing-cr",
      );
      await continueChat.say(C1_EXISTING_CR_TURN);
      await beat(page);
      const continueChoice = continueChat.cards("existing_cr_choice");
      await expect(continueChoice).toBeVisible({ timeout: 60_000 });
      await beat(page);
      const doneBeforeContinue = await readDoneEventCount(page);
      await continueChoice
        .getByRole("button", { name: "Continue for them" })
        .click();
      await continueChat.waitForTurnDone(doneBeforeContinue);
      await beat(page);
      await expect(continueChoice.getByText("Continue for them")).toBeVisible();

      const draft = await continueChat.draft();
      expect(fieldDisplay(draft, "company_name")).toBe("Oasis Coffee Company");
      const companyField = draftFields(draft).find(
        (f) => f.key === "company_name",
      );
      expect(companyField?.source).toBe("verified");

      const verifyPath = await staffSendApplicationLink(
        continueChat,
        request,
        OASIS_APPLICANT_EMAIL,
        "a2-applicant",
        beat,
      );
      await completeApplicationFromLink(
        browser,
        request,
        verifyPath,
        page,
        { email: OASIS_APPLICANT_EMAIL, mobile: OASIS_APPLICANT_MOBILE },
        undefined,
        beat,
      );
    });

    await test.step("Tenant Central and My inquiries", async () => {
      await caption(page, "Tenant Central and My inquiries");
      const { reference } = await raiseTenantInquiry(
        page,
        /Oasis Coffee Company/,
        "OPP-101",
        "a1-existing-tenant",
        /Welcome back, Layla/,
        beat,
      );
      await page.goto("/tenant/inquiries");
      await expect(page.getByTestId("my-inquiries")).toContainText(reference);
      await beat(page);
    });

    await test.step("public-page sign-in", async () => {
      await caption(page, "public-page sign-in");
      const inquiry = new InquiryPage(page);
      await inquiry.open("16-existing-tenant");
      await inquiry.say("1010000000");
      await beat(page);
      const signInCard = inquiry.cards("sign_in_prompt");
      await expect(signInCard).toBeVisible({ timeout: 60_000 });
      await beat(page);
      await expect(
        signInCard.getByRole("link", { name: "Sign in to Tenant Central" }),
      ).toHaveAttribute("href", /\/tenant\/?$/);
      const draft = await inquiry.draft();
      expect(draft.can_submit).toBe(false);
    });

    await test.step(
      "approvals to Yardi (prefilled contacts, remove one, assistant Use, no invite for existing accounts)",
      async () => {
        await caption(
          page,
          "approvals to Yardi (prefilled contacts, remove one, assistant Use, no invite for existing accounts)",
        );
        const { reference } = await raiseTenantInquiry(
          page,
          /Oasis Coffee Company/,
          "OPP-101",
          "a1-existing-tenant",
          /Welcome back, Layla/,
          beat,
        );
        const reviewer = await reviewerFor(request, reference);

        const viewport = page.viewportSize();
        const reviewerContext = await browser.newContext(
          viewport ? { viewport } : {},
        );
        const applicantContext = await browser.newContext(
          viewport ? { viewport } : {},
        );
        try {
          const reviewerPage = await reviewerContext.newPage();
          await signInReviewer(reviewerPage, reviewer);
          await openReviewerCase(reviewerPage, reference);

          await reviewerPage
            .getByTestId("action-approve_first")
            .getByRole("button", { name: "Approve first level" })
            .click();
          await expect(reviewerPage.getByTestId("case-stage")).toHaveText(
            "Lead — second review",
          );
          await beat(reviewerPage);

          const removeBlock = reviewerPage.getByTestId("action-remove_contact");
          await expect(removeBlock).toBeVisible();
          await removeBlock
            .getByLabel("Contact")
            .selectOption("billing_contact");
          await removeBlock.getByRole("button", { name: "Remove" }).click();
          await beat(reviewerPage);

          await expect
            .poll(async () =>
              latestByTemplate(
                await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL),
                "contacts_request",
              ),
            )
            .toBeTruthy();
          const contactsMail = latestByTemplate(
            await fetchDevOutbox(request, OASIS_APPLICANT_EMAIL),
            "contacts_request",
          )!;
          const casePath = contactsMail.links.find((l) =>
            l.includes("/inquiry/case"),
          );
          expect(casePath).toBeTruthy();
          const caseUrl = new URL(casePath!);
          caseUrl.searchParams.set("e2eCaseScenario", "t1-contacts");

          const applicantPage = await applicantContext.newPage();
          const applicant = new InquiryPage(applicantPage);
          await applicantPage.goto(caseUrl.toString());
          await applicant.waitForChatReady();
          await applicant.say(
            "I'm the signatory; billing is Omar Saleh, omar@beanstreet.example, +966551234567",
          );
          await beat(applicantPage);
          await expect(applicant.cards("contacts")).toBeVisible({
            timeout: 60_000,
          });
          await beat(applicantPage);
          await applicant.submitContacts();
          await beat(applicantPage);

          await reviewerPage.goto(
            `/review/cases/${encodeURIComponent(reference)}?e2eScenario=r1-yardi-suggest`,
          );
          const assistant = reviewerPage.getByTestId(
            "reviewer-assistant-panel",
          );
          await assistant
            .getByLabel("Message")
            .fill("Find the Yardi company for Bean Street Trading.");
          await assistant.getByRole("button", { name: "Send" }).click();
          const suggestion = reviewerPage
            .getByTestId("reviewer-suggestion")
            .filter({ hasText: /Bean Street Trading Co\./ });
          await expect(suggestion).toBeVisible({ timeout: 60_000 });
          await beat(reviewerPage);
          await suggestion.getByRole("button", { name: "Use" }).click();
          const yardi = reviewerPage.getByTestId("action-yardi");
          await expect(yardi.getByLabel("Company")).toHaveValue("YC-1001");
          await beat(reviewerPage);
          await yardi.getByRole("button", { name: "Link company" }).click();
          await beat(reviewerPage);

          await reviewerPage.reload();
          await reviewerPage
            .getByTestId("action-approve")
            .getByRole("button", { name: "Approve" })
            .click();
          await expect(reviewerPage.getByTestId("case-stage")).toHaveText(
            "Approved and sent to Yardi",
          );
          await beat(reviewerPage);

          expect(
            (await fetchDevOutbox(request, LAYLA_EMAIL)).filter(
              (m) => m.template === "azure_ad_invitation",
            ),
          ).toHaveLength(0);
          await expect
            .poll(async () =>
              latestByTemplate(
                await fetchDevOutbox(request, OMAR_EMAIL),
                "azure_ad_invitation",
              ),
            )
            .toBeTruthy();
        } finally {
          await reviewerContext.close();
          await applicantContext.close();
        }
      },
    );

    await test.step(
      "L5 (+48 h stalled, +48 h escalation, reminder → draft → Use → 23:00 hold → 08:00 → sent once)",
      async () => {
        await caption(
          page,
          "L5 (+48 h stalled, +48 h escalation, reminder → draft → Use → 23:00 hold → 08:00 → sent once)",
        );
        await runL5AttentionFlow(page, request, beat);
      },
    );

    await test.step(
      "Reset demo leaves queues, attention, My inquiries and the inbox empty",
      async () => {
        await caption(
          page,
          "Reset demo leaves queues, attention, My inquiries and the inbox empty",
        );
        await resetDemoFromDevPage(page);
        await assertCleanAfterDemoReset(page);
      },
    );
  });
});

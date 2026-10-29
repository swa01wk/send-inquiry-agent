import AxeBuilder from "@axe-core/playwright";
import { expect } from "@playwright/test";
import type { InquiryPage } from "../pages/inquiry";
import {
  assertNoDuplicateConfirmCards,
  assertPlainLanguageReply,
  assertRetractionBudget,
} from "./plainLanguage";

export async function afterTurnChecks(inquiry: InquiryPage) {
  const reply = await inquiry.lastReply();
  assertPlainLanguageReply(reply, inquiry.userContext());
  const events = await inquiry.events();
  assertNoDuplicateConfirmCards(events);
  assertRetractionBudget(events);
}

export async function finishA11y(inquiry: InquiryPage, projectName: string) {
  const results = await new AxeBuilder({ page: inquiry.page })
    .include('section[aria-label="Leasing assistant chat"]')
    .disableRules(["scrollable-region-focusable"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious, "no serious axe violations").toEqual([]);
  if (projectName === "mobile") {
    const overflow = await inquiry.page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    );
    expect(overflow).toBeTruthy();
  }
}

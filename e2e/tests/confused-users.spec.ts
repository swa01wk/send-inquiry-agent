import { expect, test } from "@playwright/test";
import { InquiryPage } from "../pages/inquiry";
import { afterTurnChecks, finishA11y } from "../support/turnChecks";

test.describe("Confused users @scripted", () => {
  test("11 impatient before OTP", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("11-impatient");
    await inquiry.say("just submit it");
    await afterTurnChecks(inquiry);
    expect(await inquiry.cards("review").count()).toBe(0);
    expect(await inquiry.cards("success").count()).toBe(0);
    const reply = await inquiry.lastReply();
    expect(reply.length).toBeGreaterThan(10);
    expect(reply.toLowerCase()).toMatch(
      /verify|code|document|phone|otp|upload|still need/i,
    );
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("14 wants a person", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("14-wants-person");
    await inquiry.say("can i talk to someone?");
    await afterTurnChecks(inquiry);
    const reply = await inquiry.lastReply();
    expect(reply.toLowerCase()).toMatch(
      /team|help|continue|here|submit|happy|going/,
    );
    expect(reply.toLowerCase()).not.toMatch(
      /guarantee|promise|tomorrow|call you/i,
    );
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("21 very unclear user", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("21-unclear");
    const turns = ["i want shop", "?", "idk", "how"];
    const replies: string[] = [];
    for (const text of turns) {
      await inquiry.say(text);
      await afterTurnChecks(inquiry);
      replies.push(await inquiry.lastReply());
    }
    for (const r of replies) {
      const sentences = r.split(/[.!?]+/).filter((s) => s.trim());
      expect(sentences.length).toBeLessThanOrEqual(2);
    }
    expect(new Set(replies).size).toBe(replies.length);
    await finishA11y(inquiry, testInfo.project.name);
  });

  test("22 lost mid-way", async ({ page }, testInfo) => {
    const inquiry = new InquiryPage(page);
    await inquiry.open("22-lost-midway");
    await inquiry.say("1010123456");
    await afterTurnChecks(inquiry);
    await inquiry.say("Bean Street kiosk riyadh mall a");
    await afterTurnChecks(inquiry);
    const draftBefore = await inquiry.draft();
    await inquiry.say("what? i dont understand");
    await afterTurnChecks(inquiry);
    await inquiry.say("what do i do now");
    await afterTurnChecks(inquiry);
    const reply = await inquiry.lastReply();
    expect(
      reply.split(/[.!?]+/).filter((s) => s.trim()).length,
    ).toBeLessThanOrEqual(2);
    const draftAfter = await inquiry.draft();
    expect(JSON.stringify(draftAfter.fields)).toBe(
      JSON.stringify(draftBefore.fields),
    );
    await finishA11y(inquiry, testInfo.project.name);
  });
});

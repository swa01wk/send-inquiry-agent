import type { Page } from "@playwright/test";

export type CapturedSseEvent = { event: string; data: Record<string, unknown> };

export async function readCapturedEvents(
  page: Page,
): Promise<CapturedSseEvent[]> {
  return page.evaluate(() => {
    const w = window as Window & { __e2eEvents?: CapturedSseEvent[] };
    return w.__e2eEvents ?? [];
  });
}

export async function clearCapturedEvents(page: Page): Promise<void> {
  await page.evaluate(() => {
    const w = window as Window & { __e2eEvents?: CapturedSseEvent[] };
    w.__e2eEvents = [];
  });
}

export function countRetractions(events: CapturedSseEvent[]): number {
  return events.filter((e) => e.event === "message_remove").length;
}

export function countDoneEvents(events: CapturedSseEvent[]): number {
  return events.filter((e) => e.event === "done").length;
}

export async function readDoneEventCount(page: Page): Promise<number> {
  return countDoneEvents(await readCapturedEvents(page));
}

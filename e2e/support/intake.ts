import { expect, type APIRequestContext, type Page } from '@playwright/test'
import { fetchDevOutbox, referenceFromReviewAssigned } from './outbox'
import { scenario, type CatalogueStep } from './scenarios'
import { openEntryChat, runStep } from './steps'

/**
 * A submitted inquiry for the after-submit stories: the catalogue's S2 (a CR not in Tenant
 * Central → store → Riyadh Mall A → Sara Ali) through the public chat in the app's order,
 * with its scripted model (`flow-v2-s2`). Returns the reference.
 *
 * `files` picks the profile fixtures: the mock document review reads the expiry from the file
 * name (`company_expired.pdf`, `brand_soon.pdf`; demo feedback §3.3).
 */
export async function submitInquiry(
  page: Page,
  request: APIRequestContext,
  options: { files?: { company?: string; brand?: string } } = {},
): Promise<string> {
  const entry = scenario('S2')
  const steps: CatalogueStep[] = (entry.steps ?? []).map((step) =>
    'upload' in step
      ? {
          upload: {
            company_profile: options.files?.company ?? 'company_profile.pdf',
            brand_profile: options.files?.brand ?? 'brand_profile.pdf',
          },
        }
      : step,
  )
  const ctx = await openEntryChat(page, page.context().browser()!, request, entry, false)
  for (const step of steps) await runStep(ctx, step)
  await expect(ctx.chat.cards('success')).toBeVisible({ timeout: 60_000 })
  return referenceFromReviewAssigned(await fetchDevOutbox(request))
}
